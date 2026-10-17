import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

Collection = Literal["complete", "incomplete", "missing"]


class SeriesPoint(BaseModel):
    date: date
    # "missing" means nothing was collected that day: mentions is null, not zero.
    collection: Collection
    mentions: int | None
    engagement: int | None
    positive_share: float | None
    neutral_share: float | None
    negative_share: float | None
    scored: int


class EntitySeries(BaseModel):
    entity_id: uuid.UUID
    term: str
    entity_type: str
    points: list[SeriesPoint]


class SeriesResponse(BaseModel):
    start: date
    end: date
    timezone: str = "UTC"
    sources: list[str]
    series: list[EntitySeries]


class AspectSummary(BaseModel):
    aspect: str
    mentions: int
    positive: int
    neutral: int
    negative: int


class EvidenceRecord(BaseModel):
    id: uuid.UUID
    source: str
    published_at: datetime
    text: str | None
    url: str | None
    sentiment: str | None
    confidence: float | None
    flags: list[str]


class Evidence(BaseModel):
    entity_id: uuid.UUID
    start: date
    end: date
    mentions: int
    scored: int
    sentiment: dict[str, int]
    aspects: list[AspectSummary]
    phrases: list[tuple[str, int]]
    phrases_note: str = "Frequent phrases, not reviewed themes"
    examples: list[EvidenceRecord]


class TrendCard(BaseModel):
    entity_id: uuid.UUID
    term: str
    entity_type: str
    competitor_group: str | None
    date: date | None
    score: float | None
    explanation_code: str | None
    details: dict | None
    sparkline: list[SeriesPoint]
    evidence: Evidence | None
