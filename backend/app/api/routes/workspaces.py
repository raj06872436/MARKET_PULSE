from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.db.models import User, Workspace
from app.db.session import get_db
from app.schemas.watchlist import WorkspaceCreate, WorkspaceRead

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post("", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
def create_workspace(body: WorkspaceCreate, db: Session = Depends(get_db), user: User = Depends(current_user)) -> Workspace:
    workspace = Workspace(name=body.name, owner_user_id=user.id)
    db.add(workspace)
    db.commit()
    return workspace


@router.get("", response_model=list[WorkspaceRead])
def list_workspaces(db: Session = Depends(get_db), user: User = Depends(current_user)) -> list[Workspace]:
    return list(db.scalars(select(Workspace).where(Workspace.owner_user_id == user.id).order_by(Workspace.created_at)))
