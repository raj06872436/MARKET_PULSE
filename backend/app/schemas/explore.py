import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.metrics import AspectSummary, EvidenceRecord


class DataRange(BaseModel):
    """First and last collected day for a watchlist's terms, and the sources that cover them."""

    first: date | None
    last: date | None
    sources: list[str]


class RecordAspect(BaseModel):
    aspect: str
    sentiment: str


class RecordRow(BaseModel):
    id: uuid.UUID
    source: str
    published_at: datetime
    text: str | None
    url: str | None
    engagement: int | None  # null when the source gave no engagement fields
    sentiment: str | None  # null when not scored
    confidence: float | None
    flags: list[str]
    aspects: list[RecordAspect]
    terms: list[str]


class RecordPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[RecordRow]


class SentimentBreakdown(BaseModel):
    entity_id: uuid.UUID
    term: str
    start: date
    end: date
    sources: list[str]
    mentions: int
    scored: int
    counts: dict[Literal["positive", "neutral", "negative"], int]
    flagged: dict[str, int]  # posts carrying each quality flag
    aspects: list[AspectSummary]
    positive_phrases: list[tuple[str, int]]
    negative_phrases: list[tuple[str, int]]
    positive_examples: list[EvidenceRecord]
    negative_examples: list[EvidenceRecord]


class AspectShare(BaseModel):
    aspect: str
    mentions: int
    negative_share: float


class Scorecard(BaseModel):
    entity_id: uuid.UUID
    term: str
    entity_type: str
    competitor_group: str | None
    mentions: int
    share_of_voice: float | None
    collected_days: int
    engagement_per_post: float | None
    engagement_records: int
    scored: int
    net_sentiment: float | None  # (positive - negative) / scored
    positive_share: float | None
    negative_share: float | None
    aspects: list[AspectShare]


class AspectGap(BaseModel):
    aspect: str
    entity_id: uuid.UUID
    term: str
    mentions: int
    negative_share: float
    others_negative_share: float
    difference: float


class Comparison(BaseModel):
    start: date
    end: date
    days: int
    sources: list[str]
    scorecards: list[Scorecard]
    aspect_gaps: list[AspectGap]
