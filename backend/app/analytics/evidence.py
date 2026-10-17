import uuid
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import NlpResult, RecordMatch, SocialRecord, TrackedEntity
from app.ml.sentiment.base import SentimentModel
from app.ml.topics.phrases import top_phrases
from app.schemas.metrics import AspectSummary, Evidence, EvidenceRecord

MAX_EXAMPLES = 5


def day_bounds(start: date, end: date) -> tuple[datetime, datetime]:
    return datetime.combine(start, time.min, UTC), datetime.combine(end + timedelta(days=1), time.min, UTC)


def gather_evidence(db: Session, entity: TrackedEntity, start: date, end: date, model: SentimentModel) -> Evidence:
    lo, hi = day_bounds(start, end)
    rows = db.execute(
        select(SocialRecord, NlpResult)
        .join(RecordMatch, RecordMatch.record_id == SocialRecord.id)
        .outerjoin(
            NlpResult,
            (NlpResult.record_id == SocialRecord.id)
            & (NlpResult.model_name == model.name)
            & (NlpResult.model_version == model.version),
        )
        .where(RecordMatch.tracked_entity_id == entity.id, SocialRecord.published_at >= lo, SocialRecord.published_at < hi)
        .order_by(SocialRecord.published_at.desc())
    ).all()

    sentiment: Counter[str] = Counter()
    aspects: dict[str, Counter[str]] = defaultdict(Counter)
    for record, result in rows:
        if result and result.sentiment:
            sentiment[result.sentiment] += 1
            for item in (result.aspects_json or {}).get("items", []):
                aspects[item["aspect"]][item["sentiment"]] += 1

    # Examples: the most negative and most positive confident posts, then the latest, so evidence isn't cherry-picked one way.
    def pick(label: str) -> list:
        return sorted(
            [(r, n) for r, n in rows if n and n.sentiment == label and not (n.flags_json or [])],
            key=lambda rn: -(rn[1].confidence or 0),
        )[:2]

    chosen = pick("negative") + pick("positive")
    seen = {r.id for r, _ in chosen}
    chosen += [(r, n) for r, n in rows if r.id not in seen][: MAX_EXAMPLES - len(chosen)]

    terms = [entity.term, *entity.variants]
    return Evidence(
        entity_id=entity.id,
        start=start,
        end=end,
        mentions=len(rows),
        scored=sum(sentiment.values()),
        sentiment={k: sentiment.get(k, 0) for k in ("positive", "neutral", "negative")},
        aspects=sorted(
            (AspectSummary(aspect=a, mentions=sum(c.values()), positive=c["positive"], neutral=c["neutral"], negative=c["negative"])
             for a, c in aspects.items()),
            key=lambda s: -s.mentions,
        ),
        phrases=top_phrases((r.text_reference or "" for r, _ in rows), terms, limit=8),
        examples=[
            EvidenceRecord(
                id=r.id, source=r.source, published_at=r.published_at, text=r.text_reference, url=r.permitted_url,
                sentiment=n.sentiment if n else None, confidence=n.confidence if n else None, flags=(n.flags_json or []) if n else [],
            )
            for r, n in chosen
        ],
    )


def entity_or_none(db: Session, entity_id: uuid.UUID) -> TrackedEntity | None:
    return db.get(TrackedEntity, entity_id)
