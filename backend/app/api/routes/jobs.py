import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import IngestionRun
from app.db.session import get_db
from app.schemas.ingestion import RunRead

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[RunRead])
def list_jobs(
    source: str | None = None, limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)
) -> list[IngestionRun]:
    query = select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(limit)
    if source is not None:
        query = query.where(IngestionRun.source == source)
    return list(db.scalars(query))


@router.get("/{job_id}", response_model=RunRead)
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> IngestionRun:
    run = db.get(IngestionRun, job_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return run
