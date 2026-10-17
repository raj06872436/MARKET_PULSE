import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class InsightGenerate(BaseModel):
    watchlist_id: uuid.UUID
    end: date | None = None  # defaults to the last collected day
    use_llm: bool = True


class InsightOut(BaseModel):
    id: uuid.UUID
    watchlist_id: uuid.UUID | None
    entity_id: uuid.UUID | None
    period_start: date
    period_end: date
    observation: str
    interpretation: str | None
    caveat: str | None
    suggested_action: str | None
    evidence: dict
    generator: str
    model_version: str
    generated_at: datetime


class InsightBatch(BaseModel):
    generator: str
    llm_status: str
    llm_available: bool
    rejected: list[dict]
    insights: list[InsightOut]


Metric = Literal["daily_mentions", "weekly_change", "negative_share", "trend_score"]


class AlertRule(BaseModel):
    metric: Metric
    threshold: float = Field(ge=0, le=100_000)
    min_posts: int = Field(10, ge=1, le=10_000)


class AlertCreate(BaseModel):
    entity_id: uuid.UUID
    rule: AlertRule
    cooldown_minutes: int = Field(1440, ge=5, le=60 * 24 * 30)


class AlertUpdate(BaseModel):
    active: bool | None = None
    cooldown_minutes: int | None = Field(None, ge=5, le=60 * 24 * 30)
    rule: AlertRule | None = None


class AlertOut(BaseModel):
    id: uuid.UUID
    entity_id: uuid.UUID
    term: str
    rule: AlertRule
    cooldown_minutes: int
    active: bool
    last_triggered_at: datetime | None
    created_at: datetime


class AlertEventOut(BaseModel):
    id: uuid.UUID
    alert_id: uuid.UUID
    entity_id: uuid.UUID
    term: str
    triggered_at: datetime
    data_date: date
    value: float
    threshold: float
    message: str
