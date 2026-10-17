import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import current_user, workspace_ids
from app.db.models import IngestionRun, User
from app.db.session import get_db
from app.schemas.ingestion import RunRead

router = APIRouter(prefix="/jobs", tags=["jobs"])


def visible_runs(db: Session, user: User):
    """Runs of shared sources, plus uploads into the user's own workspaces."""
    return or_(IngestionRun.workspace_id.is_(None), IngestionRun.workspace_id.in_(workspace_ids(db, user)))


@router.get("", response_model=list[RunRead])
def list_jobs(
    source: str | None = None, limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[IngestionRun]:
    query = select(IngestionRun).where(visible_runs(db, user)).order_by(IngestionRun.started_at.desc()).limit(limit)
    if source is not None:
        query = query.where(IngestionRun.source == source)
    return list(db.scalars(query))


@router.get("/{job_id}", response_model=RunRead)
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)) -> IngestionRun:
    run = db.scalar(select(IngestionRun).where(IngestionRun.id == job_id, visible_runs(db, user)))
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return run
