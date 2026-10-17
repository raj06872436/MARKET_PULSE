from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.api.deps import SESSION_COOKIE, current_user
from app.core import ratelimit
from app.core.config import Settings, get_settings
from app.core.security import DUMMY_HASH, hash_password, new_session_token, token_hash, verify_password
from app.db.models import AuditEvent, User, UserSession, Workspace
from app.db.session import get_db
from app.schemas.auth import Credentials, Registration, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(user: User) -> UserRead:
    return UserRead(id=user.id, email=user.email, role=user.role, created_at=user.created_at)


def _start_session(db: Session, user: User, response: Response, settings: Settings) -> None:
    token = new_session_token()
    expires = datetime.now(UTC) + timedelta(days=settings.session_days)
    db.add(UserSession(user_id=user.id, token_hash=token_hash(token), expires_at=expires, last_seen_at=datetime.now(UTC)))
    # Expired sessions are cleared here rather than by a separate job.
    db.execute(delete(UserSession).where(UserSession.expires_at < datetime.now(UTC)))
    db.commit()
    response.set_cookie(SESSION_COOKIE, token, max_age=settings.session_days * 86400, httponly=True,
                        secure=settings.secure_cookies, samesite="lax", path="/")


def audit(db: Session, actor_id, event: str, **metadata) -> None:
    db.add(AuditEvent(actor_id=actor_id, event_type=event, metadata_=metadata or None))


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(body: Registration, request: Request, response: Response, db: Session = Depends(get_db),
             settings: Settings = Depends(get_settings)) -> UserRead:
    ratelimit.enforce(ratelimit.REGISTER, ratelimit.client_ip(request))
    first = db.scalar(select(func.count()).select_from(User).where(User.password_hash.is_not(None))) == 0
    if not settings.allow_registration and not first:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "New accounts are turned off here. Ask the admin for access.")
    if db.scalar(select(User.id).where(User.email == body.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists. Sign in instead.")
    user = User(email=body.email, password_hash=hash_password(body.password), role="admin" if first else "member", status="active")
    db.add(user)
    db.flush()
    if first:
        # The first account takes over workspaces made before sign-in existed, so an upgrade keeps its data.
        db.execute(update(Workspace).where(Workspace.owner_user_id.is_(None)).values(owner_user_id=user.id))
    if not db.scalar(select(Workspace.id).where(Workspace.owner_user_id == user.id)):
        db.add(Workspace(name="My workspace", owner_user_id=user.id))
    audit(db, user.id, "user.registered", role=user.role)
    _start_session(db, user, response, settings)
    return _user_out(user)


@router.post("/login", response_model=UserRead)
def login(body: Credentials, request: Request, response: Response, db: Session = Depends(get_db),
          settings: Settings = Depends(get_settings)) -> UserRead:
    ratelimit.enforce(ratelimit.LOGIN, f"{ratelimit.client_ip(request)}|{body.email}")
    user = db.scalar(select(User).where(User.email == body.email))
    ok = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not ok or user.status != "active":
        audit(db, user.id if user else None, "user.login_failed")
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is wrong")
    audit(db, user.id, "user.login")
    _start_session(db, user, response, settings)
    return _user_out(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    if token := request.cookies.get(SESSION_COOKIE):
        db.execute(delete(UserSession).where(UserSession.token_hash == token_hash(token)))
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(current_user)) -> UserRead:
    return _user_out(user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)) -> None:
    """Delete the account with its workspaces, watchlists, uploads and everything derived from them."""
    if user.role == "admin" and db.scalar(select(func.count()).select_from(User).where(User.role == "admin")) == 1 \
            and db.scalar(select(func.count()).select_from(User)) > 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "Make another account admin before deleting the only admin.")
    audit(db, None, "user.deleted", user_id=str(user.id))
    for workspace in db.scalars(select(Workspace).where(Workspace.owner_user_id == user.id)):
        db.delete(workspace)
    db.flush()  # workspaces first, so their uploads and watchlists go with them before the user row
    db.delete(user)
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
