"""Create and run ingestion jobs. Runs execute outside the request, each with its own DB session."""

import logging
import uuid
from collections.abc import Callable, Iterable, Iterator
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.analytics.pipeline import run_analysis
from app.connectors.base import ConnectorError, FetchCoverage, NormalizedRecord, SourceConnector
from app.db.models import IngestionRun, SourceConnection
from app.ingestion.matching import build_matchers, search_terms
from app.ingestion.service import IngestStats, ingest_records
from app.ml.sentiment.base import SentimentModel

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = ("queued", "running")
SUCCESS_STATUSES = ("succeeded", "partial")
# Overlap each incremental window so late-indexed posts aren't missed; dedupe absorbs the repeats.
INCREMENTAL_OVERLAP = timedelta(hours=1)
STALE_AFTER = timedelta(hours=2)


class SyncNotAllowed(Exception):
    pass


def _until_error(records: Iterable[NormalizedRecord], errors: list[ConnectorError]) -> Iterator[NormalizedRecord]:
    """Pass records through, stopping at a ConnectorError so every record that did arrive gets stored."""
    try:
        yield from records
    except ConnectorError as exc:
        errors.append(exc)


def now() -> datetime:
    return datetime.now(UTC)


def active_run(db: Session, source: str) -> IngestionRun | None:
    return db.scalar(
        select(IngestionRun)
        .where(
            IngestionRun.source == source,
            IngestionRun.status.in_(ACTIVE_STATUSES),
            IngestionRun.started_at > now() - STALE_AFTER,
        )
        .order_by(IngestionRun.started_at.desc())
    )


def last_successful_run(db: Session, source: str) -> IngestionRun | None:
    return db.scalar(
        select(IngestionRun)
        .where(IngestionRun.source == source, IngestionRun.status.in_(SUCCESS_STATUSES))
        .order_by(IngestionRun.started_at.desc())
    )


def queue_sync(db: Session, source: str, trigger: str) -> tuple[IngestionRun, bool]:
    """Return (run, created). An already-active run for the source is returned instead of a new one."""
    connection = db.scalar(select(SourceConnection).where(SourceConnection.source_name == source))
    if connection is None or connection.status != "enabled":
        raise SyncNotAllowed(f"{source} is not enabled")
    if connection.policy_reviewed_at is None:
        raise SyncNotAllowed(f"Record a terms and policy review for {source} before syncing")
    if existing := active_run(db, source):
        return existing, False
    run = IngestionRun(source=source, trigger=trigger, status="queued", started_at=now())
    db.add(run)
    db.commit()
    return run, True


def run_sync(
    run_id: uuid.UUID,
    session_factory: sessionmaker,
    connector_factory: Callable[[str], SourceConnector],
    sentiment_model: SentimentModel | None = None,
) -> None:
    with session_factory() as db:
        run = db.get(IngestionRun, run_id)
        if run is None or run.status != "queued":
            return
        run.status = "running"
        previous = last_successful_run(db, run.source)
        run.window_start = previous.started_at - INCREMENTAL_OVERLAP if previous else None
        db.commit()

        coverage = FetchCoverage()
        stats = IngestStats()
        connector = connector_factory(run.source)
        try:
            terms = search_terms(db)
            if terms:
                errors: list[ConnectorError] = []
                records = _until_error(connector.fetch(terms, run.window_start, coverage), errors)
                ingest_records(db, records, run, build_matchers(db), connector.version, stats)
                if errors:
                    raise errors[0]
            run.status = "succeeded" if coverage.complete else "partial"
        except ConnectorError as exc:
            db.rollback()
            run = db.get(IngestionRun, run_id)
            run.status = "failed"
            run.error_code = exc.code
            run.error_detail = str(exc)[:500]
        except Exception:
            logger.exception("Sync failed unexpectedly", extra={"job_id": str(run_id)})
            db.rollback()
            run = db.get(IngestionRun, run_id)
            run.status = "failed"
            run.error_code = "internal_error"
            run.error_detail = "Unexpected error; see server logs"

        run.fetched_count = stats.fetched
        run.inserted_count = stats.inserted
        run.duplicate_count = stats.duplicates
        run.matched_count = stats.matched
        run.coverage_json = {
            "queries": len(coverage.queries),
            "skipped_queries": coverage.skipped_queries,
            "truncated_queries": coverage.truncated_queries,
            "pages_fetched": coverage.pages_fetched,
            "schema_errors": coverage.schema_errors,
            "complete": coverage.complete and run.status != "failed",
            "no_terms": not coverage.queries and not coverage.skipped_queries,
        }
        run.ended_at = now()
        db.commit()
        if sentiment_model is not None:
            try:
                run_analysis(db, sentiment_model)
            except Exception:
                # Analysis can be re-run from /api/analysis/run; the sync itself succeeded.
                db.rollback()
                logger.exception("Analysis after sync failed", extra={"job_id": str(run_id)})
        logger.info("Sync %s finished: %s", run.source, run.status, extra={"job_id": str(run_id)})
