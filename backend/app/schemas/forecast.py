import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.ml.forecasting.service import DEFAULT_HORIZON, MAX_HORIZON


class ForecastCreate(BaseModel):
    entity_id: uuid.UUID
    horizon_days: int = Field(DEFAULT_HORIZON, ge=1, le=MAX_HORIZON)


class DataCheck(BaseModel):
    name: str
    passed: bool
    detail: str


class MethodScore(BaseModel):
    name: str
    label: str
    kind: Literal["baseline", "candidate"]
    mae: float | None = None
    rmse: float | None = None
    wape: float | None = None
    n: int = 0
    mae_by_horizon: list[float | None] = []


class Backtest(BaseModel):
    origins: list[date]
    horizon_days: int
    methods: list[MethodScore]


class ForecastPointOut(BaseModel):
    date: date
    predicted: float
    lower: float | None
    upper: float | None
    # Observed mentions once that day has been collected, so past forecasts can be checked.
    actual: int | None


class HistoryPoint(BaseModel):
    date: date
    mentions: int | None  # null = not collected


class ForecastOut(BaseModel):
    id: uuid.UUID
    entity_id: uuid.UUID
    term: str
    status: Literal["ready", "insufficient_data", "failed"]
    method: str | None
    method_label: str | None
    model_version: str
    horizon_days: int
    training_start: date | None
    training_end: date | None
    created_at: datetime
    checks: list[DataCheck]
    interval_level: float
    interval_coverage: float | None
    candidate_beats_baseline: bool | None
    backtest: Backtest | None
    history: list[HistoryPoint]
    points: list[ForecastPointOut]
