from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import current_user, require_admin, workspace_ids
from app.connectors.registry import CONNECTORS, LABELS, build_connector
from app.core import ratelimit
from app.core.config import Settings, get_settings
from app.db.models import IngestionRun, SocialRecord, SourceConnection, User
from app.db.session import get_db, get_session_factory
from app.jobs.runner import SyncNotAllowed, last_successful_run, queue_sync, run_sync
from app.ml.sentiment.registry import get_model
from app.schemas.ingestion import RunRead, SourceRead, SourceUpdate

router = APIRouter(prefix="/sources", tags=["sources"])

STATUS_BY_RUN = {"queued": "running", "running": "running", "succeeded": "ok", "partial": "degraded", "failed": "failed"}


def _latest_run(db: Session, source: str, workspaces: list) -> IngestionRun | None:
    return db.scalar(
        select(IngestionRun).where(IngestionRun.source == source, _visible(IngestionRun, workspaces))
        .order_by(IngestionRun.started_at.desc())
    )


def _visible(model, workspaces: list):
    """Shared sources, plus uploads into the user's own workspaces. Other workspaces' uploads stay hidden."""
    return or_(model.workspace_id.is_(None), model.workspace_id.in_(workspaces))


def _describe(db: Session, source: str, settings: Settings, workspaces: list) -> SourceRead:
    kind = "api" if source in CONNECTORS else "csv"
    connection = db.scalar(select(SourceConnection).where(SourceConnection.source_name == source))
    enabled = kind == "csv" or (connection is not None and connection.status == "enabled")
    last_run = _latest_run(db, source, workspaces)
    last_success = last_successful_run(db, source, _visible(IngestionRun, workspaces))

    if not enabled:
        state = "not_connected"
    elif last_run is None:
        state = "never_run"
    else:
        state = STATUS_BY_RUN.get(last_run.status, "failed")

    notes = []
    if kind == "api":
        notes = build_connector(source, settings).health().notes
        if connection is None or connection.policy_reviewed_at is None:
            notes.append("Terms and policy review not recorded yet; syncing is blocked until it is.")

    return SourceRead(
        source=source,
        label=LABELS.get(source, source.removeprefix("csv:") + " (CSV)"),
        kind=kind,
        enabled=enabled,
        policy_reviewed_at=connection.policy_reviewed_at if connection else None,
        policy_notes=connection.policy_notes if connection else None,
        status=state,
        last_run=RunRead.model_validate(last_run) if last_run else None,
        last_success_at=(last_success.ended_at or last_success.started_at) if last_success else None,
        record_count=db.scalar(select(func.count()).select_from(SocialRecord).where(
            SocialRecord.source == source, _visible(SocialRecord, workspaces))) or 0,
        notes=notes,
    )


def _require_api_source(source: str) -> None:
    if source not in CONNECTORS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown source '{source}'")


@router.get("", response_model=list[SourceRead])
def list_sources(
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings), user: User = Depends(current_user)
) -> list[SourceRead]:
    workspaces = workspace_ids(db, user)
    csv_sources = db.scalars(
        select(IngestionRun.source).where(IngestionRun.source.like("csv:%"), _visible(IngestionRun, workspaces))
        .distinct().order_by(IngestionRun.source)
    ).all()
    return [_describe(db, source, settings, workspaces) for source in [*CONNECTORS, *csv_sources]]


@router.put("/{source}", response_model=SourceRead)
def update_source(
    source: str, body: SourceUpdate, db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
    user: User = Depends(require_admin),
) -> SourceRead:
    """Sources are shared by every workspace, so only an admin can enable them or record their review."""
    _require_api_source(source)
    connection = db.scalar(select(SourceConnection).where(SourceConnection.source_name == source))
    reviewed_at = connection.policy_reviewed_at if connection else None
    if body.policy_reviewed is not None:
        reviewed_at = datetime.now(UTC) if body.policy_reviewed else None
    if body.enabled and reviewed_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Record a terms and policy review before enabling this source")

    if connection is None:
        connection = SourceConnection(source_name=source, status="disabled")
        db.add(connection)
    connection.policy_reviewed_at = reviewed_at
    if body.policy_notes is not None:
        connection.policy_notes = body.policy_notes
    if body.enabled is not None:
        connection.status = "enabled" if body.enabled else "disabled"
    if reviewed_at is None:
        connection.status = "disabled"
    db.commit()
    return _describe(db, source, settings, workspace_ids(db, user))


@router.post("/{source}/sync", response_model=RunRead, status_code=status.HTTP_202_ACCEPTED)
def sync_source(
    source: str,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    session_factory: sessionmaker = Depends(get_session_factory),
    settings: Settings = Depends(get_settings),
    user: User = Depends(current_user),
) -> IngestionRun:
    _require_api_source(source)
    ratelimit.enforce(ratelimit.SYNC, str(user.id))
    try:
        run, created = queue_sync(db, source, trigger="manual")
    except SyncNotAllowed as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    if created:
        background.add_task(
            run_sync, run.id, session_factory, lambda s: build_connector(s, settings), get_model(settings.sentiment_model)
        )
    return run
