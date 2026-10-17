"""Import every model so Base.metadata is complete for Alembic and tests."""

from app.db.models.account import AuditEvent, User, Workspace
from app.db.models.analytics import (
    DailyMetric,
    ForecastPoint,
    ForecastRun,
    InsightCard,
    ModelVersion,
    NlpResult,
    TrendSignal,
)
from app.db.models.ingestion import IngestionRun, RecordMatch, SocialRecord, SourceConnection
from app.db.models.watchlist import Alert, TrackedEntity, Watchlist

__all__ = [
    "Alert",
    "AuditEvent",
    "DailyMetric",
    "ForecastPoint",
    "ForecastRun",
    "IngestionRun",
    "ModelVersion",
    "InsightCard",
    "NlpResult",
    "RecordMatch",
    "SocialRecord",
    "SourceConnection",
    "TrackedEntity",
    "User",
    "Watchlist",
    "Workspace",
]
