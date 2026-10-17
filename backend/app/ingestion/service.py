import hashlib
from collections.abc import Iterable
from dataclasses import dataclass, field
from itertools import islice

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.base import NormalizedRecord
from app.db.models import IngestionRun, RecordMatch, SocialRecord
from app.ingestion.matching import EntityMatcher, match_text

BATCH_SIZE = 500


@dataclass
class IngestStats:
    fetched: int = 0
    inserted: int = 0
    duplicates: int = 0
    matched: int = 0
    sources: set[str] = field(default_factory=set)


def content_hash(text: str | None) -> str | None:
    if not text:
        return None
    return hashlib.sha256(" ".join(text.split()).casefold().encode()).hexdigest()


def ingest_records(
    db: Session,
    records: Iterable[NormalizedRecord],
    run: IngestionRun,
    matchers: list[EntityMatcher],
    connector_version: str | None = None,
    stats: IngestStats | None = None,
) -> IngestStats:
    """Store new records and their watchlist matches. Records already stored are counted, not re-added.

    Dedupe key is (scope, source, source_record_id), so re-running a sync or re-uploading a file never
    inflates mention counts. Scope is "public" for shared sources and the workspace ID for uploads. Commits after each batch so a later source failure keeps earlier work.
    """
    stats = stats or IngestStats()
    scope = str(run.workspace_id) if run.workspace_id else "public"
    iterator = iter(records)
    while batch := list(islice(iterator, BATCH_SIZE)):
        stats.fetched += len(batch)
        unique: dict[tuple[str, str], NormalizedRecord] = {}
        for record in batch:
            key = (record.source, record.source_record_id)
            if key in unique:
                stats.duplicates += 1
            else:
                unique[key] = record

        existing: set[tuple[str, str]] = set()
        for source in {s for s, _ in unique}:
            ids = [rid for s, rid in unique if s == source]
            existing.update(
                (source, rid)
                for rid in db.scalars(
                    select(SocialRecord.source_record_id).where(
                        SocialRecord.scope == scope, SocialRecord.source == source, SocialRecord.source_record_id.in_(ids)
                    )
                )
            )
        stats.duplicates += len(existing)

        for key, record in unique.items():
            if key in existing:
                continue
            row = SocialRecord(
                scope=scope,
                workspace_id=run.workspace_id,
                source=record.source,
                source_record_id=record.source_record_id,
                published_at=record.published_at,
                ingestion_run_id=run.id,
                text_reference=record.text,
                permitted_url=record.permitted_url,
                language=record.language,
                content_hash=content_hash(record.text),
                connector_version=connector_version,
                engagement_json=record.engagement,
            )
            db.add(row)
            db.flush()
            entity_ids = match_text(record.text, matchers, run.workspace_id)
            for entity_id in entity_ids:
                db.add(RecordMatch(record_id=row.id, tracked_entity_id=entity_id, match_method="term"))
            stats.inserted += 1
            stats.matched += bool(entity_ids)
            stats.sources.add(record.source)

        run.fetched_count = stats.fetched
        run.inserted_count = stats.inserted
        run.duplicate_count = stats.duplicates
        run.matched_count = stats.matched
        db.commit()
    return stats
