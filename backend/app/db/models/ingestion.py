import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, JSONType, UUIDPk


class SourceConnection(UUIDPk, CreatedAt, Base):
    __tablename__ = "source_connections"

    source_name: Mapped[str] = mapped_column(String(64), unique=True)
    # A reference to a secret store entry, never the secret itself.
    credential_ref: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(32), default="disabled")
    # A connector may only sync once someone has recorded that its terms were reviewed.
    policy_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    policy_notes: Mapped[str | None] = mapped_column(Text)


class IngestionRun(UUIDPk, Base):
    """One sync or import. Status is one of: queued, running, succeeded, partial, failed.

    "partial" means data arrived but coverage is incomplete (rows rejected, page cap hit),
    so a dashboard can tell "no matching posts" apart from "we didn't look everywhere".
    """

    __tablename__ = "ingestion_runs"

    source: Mapped[str] = mapped_column(String(64), index=True)
    trigger: Mapped[str] = mapped_column(String(16), default="manual", server_default="manual")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="queued")
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_count: Mapped[int | None] = mapped_column(Integer)
    inserted_count: Mapped[int | None] = mapped_column(Integer)
    duplicate_count: Mapped[int | None] = mapped_column(Integer)
    rejected_count: Mapped[int | None] = mapped_column(Integer)
    matched_count: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(64))
    # Sanitized summary only: never tokens or raw record content.
    error_detail: Mapped[str | None] = mapped_column(Text)
    coverage_json: Mapped[dict | None] = mapped_column(JSONType)


class SocialRecord(UUIDPk, Base):
    __tablename__ = "social_records"
    __table_args__ = (UniqueConstraint("source", "source_record_id"),)

    source: Mapped[str] = mapped_column(String(64), index=True)
    source_record_id: Mapped[str] = mapped_column(String(256))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ingestion_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ingestion_runs.id", ondelete="SET NULL"))
    # Stored text or a reference to it, only where the source's terms allow retention.
    text_reference: Mapped[str | None] = mapped_column(Text)
    permitted_url: Mapped[str | None] = mapped_column(String(2048))
    language: Mapped[str | None] = mapped_column(String(16))
    # sha256 of the normalized text, for spotting copy-paste bursts. Dedupe itself is by source ID.
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    connector_version: Mapped[str | None] = mapped_column(String(32))
    # Missing engagement stays null; never coerce it to zero.
    engagement_json: Mapped[dict | None] = mapped_column(JSONType)


class RecordMatch(Base):
    __tablename__ = "record_matches"

    record_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("social_records.id", ondelete="CASCADE"), primary_key=True)
    tracked_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tracked_entities.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    match_method: Mapped[str] = mapped_column(String(32))
    matched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
