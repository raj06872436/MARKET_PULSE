import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, JSONType, UUIDPk


class NlpResult(Base):
    __tablename__ = "nlp_results"

    record_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("social_records.id", ondelete="CASCADE"), primary_key=True)
    model_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    model_version: Mapped[str] = mapped_column(String(50), primary_key=True)
    preprocessing_version: Mapped[str] = mapped_column(String(50))
    sentiment: Mapped[str | None] = mapped_column(String(16))
    confidence: Mapped[float | None] = mapped_column(Float)
    scores_json: Mapped[dict | None] = mapped_column(JSONType)
    # Reasons to trust the label less (mixed, sarcasm_cue, low_signal, low_confidence, unsupported_script).
    flags_json: Mapped[list | None] = mapped_column(JSONType)
    aspects_json: Mapped[list | None] = mapped_column(JSONType)
    topics_json: Mapped[list | None] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModelVersion(UUIDPk, CreatedAt, Base):
    """Every model that has produced stored outputs, with the evaluation that justified using it."""

    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("task", "name", "version"),)

    task: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(100))
    version: Mapped[str] = mapped_column(String(100))
    preprocessing_version: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(16), default="candidate")
    evaluation_json: Mapped[dict | None] = mapped_column(JSONType)
    notes: Mapped[str | None] = mapped_column(Text)


class DailyMetric(UUIDPk, Base):
    __tablename__ = "daily_metrics"
    __table_args__ = (UniqueConstraint("date", "tracked_entity_id", "source"),)

    date: Mapped[date] = mapped_column(Date, index=True)
    tracked_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tracked_entities.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(String(64))
    mentions: Mapped[int] = mapped_column(Integer)
    unique_records: Mapped[int] = mapped_column(Integer)
    engagement: Mapped[int | None] = mapped_column(Integer)
    positive_share: Mapped[float | None] = mapped_column(Float)
    neutral_share: Mapped[float | None] = mapped_column(Float)
    negative_share: Mapped[float | None] = mapped_column(Float)
    coverage_flags: Mapped[dict | None] = mapped_column(JSONType)


class TrendSignal(UUIDPk, Base):
    __tablename__ = "trend_signals"
    __table_args__ = (UniqueConstraint("tracked_entity_id", "date"),)

    tracked_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tracked_entities.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[date] = mapped_column(Date, index=True)
    score: Mapped[float] = mapped_column(Float)
    components_json: Mapped[dict] = mapped_column(JSONType)
    explanation_code: Mapped[str | None] = mapped_column(String(64))


class ForecastRun(UUIDPk, CreatedAt, Base):
    __tablename__ = "forecast_runs"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tracked_entities.id", ondelete="CASCADE"), index=True)
    model_version: Mapped[str] = mapped_column(String(50))
    # ready | insufficient_data | failed. Only "ready" runs have points.
    status: Mapped[str] = mapped_column(String(24), server_default="ready")
    # The method whose points were stored, e.g. "ets" or "seasonal_naive".
    method: Mapped[str | None] = mapped_column(String(50))
    horizon_days: Mapped[int] = mapped_column(Integer)
    training_start: Mapped[date | None] = mapped_column(Date)
    training_end: Mapped[date | None] = mapped_column(Date)
    # Data checks, back-test metrics for every method, interval level and coverage.
    metrics_json: Mapped[dict | None] = mapped_column(JSONType)


class ForecastPoint(Base):
    __tablename__ = "forecast_points"

    forecast_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("forecast_runs.id", ondelete="CASCADE"), primary_key=True
    )
    target_date: Mapped[date] = mapped_column(Date, primary_key=True)
    predicted_value: Mapped[float] = mapped_column(Float)
    lower_bound: Mapped[float | None] = mapped_column(Float)
    upper_bound: Mapped[float | None] = mapped_column(Float)


class InsightCard(UUIDPk, Base):
    __tablename__ = "insight_cards"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    claim: Mapped[str] = mapped_column(Text)
    evidence_json: Mapped[dict] = mapped_column(JSONType)
    caveat: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    model_version: Mapped[str] = mapped_column(String(50))
