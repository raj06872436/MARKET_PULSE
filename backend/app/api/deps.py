"""Who is asking, and what they may see.

Every data endpoint goes through these helpers. Anything outside the user's own workspaces answers
404, the same as something that doesn't exist, so IDs can't be probed.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import token_hash
from app.db.models import Alert, ForecastRun, TrackedEntity, User, UserSession, Watchlist, Workspace
from app.db.session import get_db

SESSION_COOKIE = "mp_session"
TOUCH_EVERY = timedelta(minutes=5)


def aware(value: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as the UTC they were written in."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def current_user(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue")
    session = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash(token)))
    now = datetime.now(UTC)
    if session is None or aware(session.expires_at) <= now:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session has ended. Sign in again.")
    user = db.get(User, session.user_id)
    if user is None or user.status != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This account can't sign in")
    if session.last_seen_at is None or now - aware(session.last_seen_at) > TOUCH_EVERY:
        # Sliding expiry, written at most every few minutes rather than on every request.
        session.last_seen_at = now
        session.expires_at = now + timedelta(days=settings.session_days)
        db.commit()
    request.state.user_id = str(user.id)
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an admin can change this")
    return user


def workspace_ids(db: Session, user: User) -> list[uuid.UUID]:
    return list(db.scalars(select(Workspace.id).where(Workspace.owner_user_id == user.id)))


def owned_workspace(db: Session, user: User, workspace_id: uuid.UUID) -> Workspace:
    workspace = db.get(Workspace, workspace_id)
    if workspace is None or workspace.owner_user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    return workspace


def owned_watchlist(db: Session, user: User, watchlist_id: uuid.UUID) -> Watchlist:
    watchlist = db.scalar(
        select(Watchlist).join(Workspace).where(Watchlist.id == watchlist_id, Workspace.owner_user_id == user.id)
    )
    if watchlist is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Watchlist not found")
    return watchlist


def owned_entity(db: Session, user: User, entity_id: uuid.UUID, label: str = "Entity") -> TrackedEntity:
    entity = db.scalar(
        select(TrackedEntity).join(Watchlist).join(Workspace)
        .where(TrackedEntity.id == entity_id, Workspace.owner_user_id == user.id)
    )
    if entity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{label} not found")
    return entity


def owned_entities(db: Session, user: User, entity_ids: list[uuid.UUID]) -> dict[uuid.UUID, TrackedEntity]:
    rows = db.scalars(
        select(TrackedEntity).join(Watchlist).join(Workspace)
        .where(TrackedEntity.id.in_(entity_ids), Workspace.owner_user_id == user.id)
    )
    return {e.id: e for e in rows}


def owned_alert(db: Session, user: User, alert_id: uuid.UUID) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    owned_entity(db, user, alert.entity_id, "Alert")
    return alert


def owned_forecast(db: Session, user: User, forecast_id: uuid.UUID) -> ForecastRun:
    run = db.get(ForecastRun, forecast_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Forecast not found")
    owned_entity(db, user, run.entity_id, "Forecast")
    return run
