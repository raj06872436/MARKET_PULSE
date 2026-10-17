from datetime import UTC, datetime

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import current_user, owned_workspace
from app.core import ratelimit
from app.core.config import Settings, get_settings
from app.db.models import IngestionRun, User
from app.db.session import get_db
from app.ingestion.csv_import import CsvFormatError, parse_csv, parse_timezone, source_name
from app.ingestion.matching import build_matchers
from app.analytics.pipeline import run_analysis
from app.ingestion.service import ingest_records
from app.ml.sentiment.registry import get_model
from app.schemas.ingestion import CsvImportResult, RowErrorRead, RunRead

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/csv", response_model=CsvImportResult, status_code=status.HTTP_201_CREATED)
async def import_csv(
    file: UploadFile = File(...),
    workspace_id: uuid.UUID = Form(..., description="The workspace the data belongs to; only its terms are matched"),
    dataset: str = Form(..., description="Short name for where this data came from, e.g. 'survey-2026'"),
    timezone: str = Form("UTC", description="Timezone for timestamps that have no offset"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(current_user),
) -> CsvImportResult:
    workspace = owned_workspace(db, user, workspace_id)
    ratelimit.enforce(ratelimit.IMPORT, str(user.id))
    raw = await file.read(settings.csv_max_bytes + 1)
    if len(raw) > settings.csv_max_bytes:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"File is larger than {settings.csv_max_bytes // 1_000_000} MB")
    try:
        source = source_name(dataset)
        parsed = parse_csv(raw, dataset, parse_timezone(timezone), settings.csv_max_rows)
    except CsvFormatError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None

    run = IngestionRun(source=source, trigger="csv", status="running", started_at=datetime.now(UTC), workspace_id=workspace.id)
    db.add(run)
    db.commit()
    ingest_records(db, parsed.records, run, build_matchers(db, workspace.id))
    run.rejected_count = parsed.rejected
    run.fetched_count = (run.fetched_count or 0) + parsed.rejected
    run.inserted_count = run.inserted_count or 0
    run.duplicate_count = run.duplicate_count or 0
    run.matched_count = run.matched_count or 0
    run.status = "partial" if parsed.rejected else "succeeded"
    run.coverage_json = {"file_name": file.filename, "unknown_columns": parsed.unknown_columns, "complete": not parsed.rejected}
    run.ended_at = datetime.now(UTC)
    db.commit()
    run_analysis(db, get_model(settings.sentiment_model))
    return CsvImportResult(
        run=RunRead.model_validate(run),
        errors=[RowErrorRead(row=e.row, column=e.column, message=e.message) for e in parsed.errors],
        unknown_columns=parsed.unknown_columns,
    )
