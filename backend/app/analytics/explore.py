"""Queries behind the Explore, Sentiment and Compare pages.

All of them read stored records and the active sentiment model's results for a date range, so
the numbers agree with daily_metrics for the same range and sources.
"""

import uuid
from collections import Counter, defaultdict
from datetime import date

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.analytics.evidence import day_bounds, text_key
from app.analytics.pipeline import ENGAGEMENT_KEYS
from app.db.models import DailyMetric, NlpResult, RecordMatch, SocialRecord, TrackedEntity, Watchlist
from app.ml.sentiment.base import SentimentModel
from app.ml.topics.phrases import top_phrases
from app.schemas.explore import (
    AspectGap,
    AspectShare,
    Comparison,
    DataRange,
    RecordAspect,
    RecordPage,
    RecordRow,
    Scorecard,
    SentimentBreakdown,
)
from app.schemas.metrics import AspectSummary, EvidenceRecord

MIN_ASPECT_MENTIONS = 5  # below this an aspect's negative share is too noisy to compare
MIN_GAP = 0.15


def engagement_total(engagement: dict | None) -> int | None:
    if not engagement:
        return None
    values = [v for k, v in engagement.items() if k in ENGAGEMENT_KEYS and v is not None]
    return sum(values) if values else None


def data_range(db: Session, watchlist: Watchlist) -> DataRange:
    ids = [e.id for e in watchlist.entities]
    if not ids:
        return DataRange(first=None, last=None, sources=[])
    covered = DailyMetric.coverage_flags["collection"].as_string() != "outside_window"
    first, last = db.execute(
        select(func.min(DailyMetric.date), func.max(DailyMetric.date)).where(DailyMetric.tracked_entity_id.in_(ids), covered)
    ).one()
    sources = db.scalars(select(DailyMetric.source).where(DailyMetric.tracked_entity_id.in_(ids)).distinct()).all()
    return DataRange(first=first, last=last, sources=sorted(sources))


def _record_query(entity_ids: list[uuid.UUID], start: date, end: date, sources: list[str] | None, model: SentimentModel) -> Select:
    lo, hi = day_bounds(start, end)
    matched = select(RecordMatch.record_id).where(RecordMatch.tracked_entity_id.in_(entity_ids))
    query = (
        select(SocialRecord, NlpResult)
        .outerjoin(
            NlpResult,
            (NlpResult.record_id == SocialRecord.id)
            & (NlpResult.model_name == model.name)
            & (NlpResult.model_version == model.version),
        )
        .where(SocialRecord.id.in_(matched), SocialRecord.published_at >= lo, SocialRecord.published_at < hi)
    )
    if sources:
        query = query.where(SocialRecord.source.in_(sources))
    return query


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_records(
    db: Session,
    entity_ids: list[uuid.UUID],
    start: date,
    end: date,
    model: SentimentModel,
    *,
    sources: list[str] | None = None,
    q: str | None = None,
    sentiment: str | None = None,
    aspect: str | None = None,
    sort: str = "newest",
    limit: int = 25,
    offset: int = 0,
) -> RecordPage:
    query = _record_query(entity_ids, start, end, sources, model)
    if q:
        query = query.where(SocialRecord.text_reference.ilike(f"%{_escape_like(q)}%", escape="\\"))
    if sentiment == "unscored":
        query = query.where(or_(NlpResult.sentiment.is_(None), NlpResult.record_id.is_(None)))
    elif sentiment:
        query = query.where(NlpResult.sentiment == sentiment)
    rows = db.execute(query).all()
    if aspect:
        # Aspects live in JSON; filter in Python so SQLite and Postgres behave the same.
        rows = [(r, n) for r, n in rows if n and any(i["aspect"] == aspect for i in (n.aspects_json or {}).get("items", []))]
    if sort == "engagement":
        rows.sort(key=lambda rn: (engagement_total(rn[0].engagement_json) is None, -(engagement_total(rn[0].engagement_json) or 0)))
    else:
        rows.sort(key=lambda rn: rn[0].published_at, reverse=sort != "oldest")
    total = len(rows)
    page = rows[offset : offset + limit]

    terms: dict[uuid.UUID, list[str]] = defaultdict(list)
    if page:
        for record_id, term in db.execute(
            select(RecordMatch.record_id, TrackedEntity.term)
            .join(TrackedEntity, TrackedEntity.id == RecordMatch.tracked_entity_id)
            .where(RecordMatch.record_id.in_([r.id for r, _ in page]), RecordMatch.tracked_entity_id.in_(entity_ids))
        ):
            terms[record_id].append(term)
    return RecordPage(
        total=total,
        limit=limit,
        offset=offset,
        items=[
            RecordRow(
                id=r.id, source=r.source, published_at=r.published_at, text=r.text_reference, url=r.permitted_url,
                engagement=engagement_total(r.engagement_json), sentiment=n.sentiment if n else None,
                confidence=n.confidence if n else None, flags=(n.flags_json or []) if n else [],
                aspects=[RecordAspect(**i) for i in ((n.aspects_json or {}).get("items", []) if n else [])],
                terms=sorted(terms[r.id]),
            )
            for r, n in page
        ],
    )


def _evidence_record(r: SocialRecord, n: NlpResult | None) -> EvidenceRecord:
    return EvidenceRecord(
        id=r.id, source=r.source, published_at=r.published_at, text=r.text_reference, url=r.permitted_url,
        sentiment=n.sentiment if n else None, confidence=n.confidence if n else None, flags=(n.flags_json or []) if n else [],
    )


def sentiment_breakdown(
    db: Session, entity: TrackedEntity, start: date, end: date, model: SentimentModel, sources: list[str] | None = None
) -> SentimentBreakdown:
    rows = db.execute(_record_query([entity.id], start, end, sources, model)).all()
    counts: Counter[str] = Counter()
    flagged: Counter[str] = Counter()
    aspects: dict[str, Counter[str]] = defaultdict(Counter)
    by_label: dict[str, list] = defaultdict(list)
    for r, n in rows:
        if not (n and n.sentiment):
            continue
        counts[n.sentiment] += 1
        by_label[n.sentiment].append((r, n))
        flagged.update(n.flags_json or [])
        for item in (n.aspects_json or {}).get("items", []):
            aspects[item["aspect"]][item["sentiment"]] += 1

    terms = [entity.term, *entity.variants]

    def examples(label: str) -> list[EvidenceRecord]:
        # Confident, unflagged posts first; ties broken by recency so the pick is stable. Near-identical
        # posts (copies, the same text with a hashtag) are shown once so three examples say three things.
        ranked = sorted(
            (rn for rn in by_label[label] if not (rn[1].flags_json or [])),
            key=lambda rn: (-(rn[1].confidence or 0), -rn[0].published_at.timestamp()),
        )
        picked, seen = [], set()
        for r, n in ranked:
            key = text_key(r.text_reference)
            if key in seen:
                continue
            seen.add(key)
            picked.append(_evidence_record(r, n))
            if len(picked) == 3:
                break
        return picked

    return SentimentBreakdown(
        entity_id=entity.id,
        term=entity.term,
        start=start,
        end=end,
        sources=sorted({r.source for r, _ in rows}),
        mentions=len(rows),
        scored=sum(counts.values()),
        counts={k: counts.get(k, 0) for k in ("positive", "neutral", "negative")},
        flagged=dict(flagged),
        aspects=sorted(
            (AspectSummary(aspect=a, mentions=sum(c.values()), positive=c["positive"], neutral=c["neutral"], negative=c["negative"])
             for a, c in aspects.items()),
            key=lambda s: -s.mentions,
        ),
        positive_phrases=top_phrases((r.text_reference or "" for r, _ in by_label["positive"]), terms, limit=8, min_count=2),
        negative_phrases=top_phrases((r.text_reference or "" for r, _ in by_label["negative"]), terms, limit=8, min_count=2),
        positive_examples=examples("positive"),
        negative_examples=examples("negative"),
    )


def compare(
    db: Session, watchlist: Watchlist, start: date, end: date, model: SentimentModel, sources: list[str] | None = None
) -> Comparison:
    entities = list(watchlist.entities)
    ids = [e.id for e in entities]
    stats = {e.id: {"mentions": 0, "eng": 0, "eng_n": 0, "counts": Counter(), "aspects": defaultdict(Counter)} for e in entities}
    seen_sources: set[str] = set()
    if ids:
        lo, hi = day_bounds(start, end)
        query = (
            select(RecordMatch.tracked_entity_id, SocialRecord, NlpResult)
            .join(SocialRecord, SocialRecord.id == RecordMatch.record_id)
            .outerjoin(
                NlpResult,
                (NlpResult.record_id == SocialRecord.id)
                & (NlpResult.model_name == model.name)
                & (NlpResult.model_version == model.version),
            )
            .where(RecordMatch.tracked_entity_id.in_(ids), SocialRecord.published_at >= lo, SocialRecord.published_at < hi)
        )
        if sources:
            query = query.where(SocialRecord.source.in_(sources))
        for entity_id, r, n in db.execute(query):
            s = stats[entity_id]
            s["mentions"] += 1
            seen_sources.add(r.source)
            if (e := engagement_total(r.engagement_json)) is not None:
                s["eng"] += e
                s["eng_n"] += 1
            if n and n.sentiment:
                s["counts"][n.sentiment] += 1
                for item in (n.aspects_json or {}).get("items", []):
                    s["aspects"][item["aspect"]][item["sentiment"]] += 1

    collected: dict[uuid.UUID, set[date]] = defaultdict(set)
    if ids:
        query = select(DailyMetric.tracked_entity_id, DailyMetric.date, DailyMetric.coverage_flags).where(
            DailyMetric.tracked_entity_id.in_(ids), DailyMetric.date >= start, DailyMetric.date <= end
        )
        if sources:
            query = query.where(DailyMetric.source.in_(sources))
        for entity_id, day, flags in db.execute(query):
            if (flags or {}).get("collection") != "outside_window":
                collected[entity_id].add(day)

    total = sum(s["mentions"] for s in stats.values())
    cards = []
    for e in entities:
        s = stats[e.id]
        scored = sum(s["counts"].values())
        cards.append(Scorecard(
            entity_id=e.id, term=e.term, entity_type=e.entity_type, competitor_group=e.competitor_group,
            mentions=s["mentions"], share_of_voice=round(s["mentions"] / total, 4) if total else None,
            collected_days=len(collected[e.id]),
            engagement_per_post=round(s["eng"] / s["eng_n"], 2) if s["eng_n"] else None, engagement_records=s["eng_n"],
            scored=scored,
            net_sentiment=round((s["counts"]["positive"] - s["counts"]["negative"]) / scored, 4) if scored else None,
            positive_share=round(s["counts"]["positive"] / scored, 4) if scored else None,
            negative_share=round(s["counts"]["negative"] / scored, 4) if scored else None,
            aspects=sorted(
                (AspectShare(aspect=a, mentions=sum(c.values()), negative_share=round(c["negative"] / sum(c.values()), 4))
                 for a, c in s["aspects"].items()),
                key=lambda x: -x.mentions,
            ),
        ))

    # Topic gaps: where one term's complaints about an aspect stand out against everyone else's.
    gaps = []
    for e in entities:
        for aspect, c in stats[e.id]["aspects"].items():
            n = sum(c.values())
            others = Counter()
            for other in entities:
                if other.id != e.id:
                    others.update(stats[other.id]["aspects"].get(aspect, Counter()))
            m = sum(others.values())
            if n < MIN_ASPECT_MENTIONS or m < MIN_ASPECT_MENTIONS:
                continue
            mine, theirs = c["negative"] / n, others["negative"] / m
            if abs(mine - theirs) >= MIN_GAP:
                gaps.append(AspectGap(aspect=aspect, entity_id=e.id, term=e.term, mentions=n, negative_share=round(mine, 4),
                                      others_negative_share=round(theirs, 4), difference=round(mine - theirs, 4)))
    gaps.sort(key=lambda g: -abs(g.difference))
    return Comparison(start=start, end=end, days=(end - start).days + 1, sources=sorted(seen_sources),
                      scorecards=cards, aspect_gaps=gaps)
