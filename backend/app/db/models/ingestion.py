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
    policy_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IngestionRun(UUIDPk, Base):
    __tablename__ = "ingestion_runs"

    source: Mapped[str] = mapped_column(String(64), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="queued")
    fetched_count: Mapped[int | None] = mapped_column(Integer)
    matched_count: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(64))


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
