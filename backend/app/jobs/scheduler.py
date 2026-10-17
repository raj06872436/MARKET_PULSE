import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.connectors.registry import build_connector
from app.core.config import get_settings
from app.db.models import SourceConnection
from app.db.session import SessionLocal
from app.jobs.runner import SyncNotAllowed, queue_sync, run_sync

logger = logging.getLogger(__name__)


def sync_enabled_sources() -> None:
    settings = get_settings()
    with SessionLocal() as db:
        sources = db.scalars(
            select(SourceConnection.source_name).where(
                SourceConnection.status == "enabled", SourceConnection.policy_reviewed_at.is_not(None)
            )
        ).all()
        queued = []
        for source in sources:
            try:
                run, created = queue_sync(db, source, trigger="scheduled")
            except SyncNotAllowed:
                continue
            if created:
                queued.append(run.id)
    for run_id in queued:
        run_sync(run_id, SessionLocal, lambda source: build_connector(source, settings))


def start_scheduler() -> BackgroundScheduler:
    settings = get_settings()
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        sync_enabled_sources, "interval", minutes=settings.sync_interval_minutes, id="sync", max_instances=1, coalesce=True
    )
    scheduler.start()
    logger.info("Scheduler started, syncing every %d minutes", settings.sync_interval_minutes)
    return scheduler
