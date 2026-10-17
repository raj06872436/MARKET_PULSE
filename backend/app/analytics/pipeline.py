"""Turn stored records into chart-ready aggregates.

run_analysis() is idempotent: it can run after every sync, import or watchlist change and
always rebuilds daily_metrics and trend_signals from the stored records.
"""

import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.analytics import trend
from app.analytics.sentiment import score_pending, tag_stale_aspects
from app.connectors.registry import CONNECTORS
from app.db.models import (
    DailyMetric,
    IngestionRun,
    NlpResult,
    RecordMatch,
    SocialRecord,
    TrackedEntity,
    TrendSignal,
    Watchlist,
)
from app.ingestion.matching import build_matchers, match_text
from app.ml.sentiment.base import SentimentModel

logger = logging.getLogger(__name__)
ENGAGEMENT_KEYS = ("likes", "comments", "shares", "quotes")


@dataclass
class AnalysisSummary:
    new_matches: int
    scored: int
    aspects_retagged: int
    daily_metric_rows: int
    trend_signal_rows: int
    forecasts_created: int = 0
    alerts_fired: int = 0


def utc_date(value: datetime) -> date:
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).astimezone(UTC).date()


def rematch_records(db: Session) -> int:
    """Match every stored record against current active watchlist terms, adding only missing matches.

    New terms therefore also count posts collected before they were added.
    """
    matchers = build_matchers(db)
    if not matchers:
        return 0
    existing = {(r, e) for r, e in db.execute(select(RecordMatch.record_id, RecordMatch.tracked_entity_id))}
    added = 0
    rows = db.execute(select(SocialRecord.id, SocialRecord.text_reference, SocialRecord.workspace_id)).all()
    for record_id, text, workspace_id in rows:
        for entity_id in match_text(text, matchers, workspace_id):
            if (record_id, entity_id) not in existing:
                db.add(RecordMatch(record_id=record_id, tracked_entity_id=entity_id, match_method="term"))
                added += 1
    db.commit()
    return added


Scope = tuple[str, uuid.UUID | None]  # (source, workspace the upload belongs to, or None if shared)


def coverage_days(db: Session) -> dict[Scope, dict[date, bool]]:
    """Days each source was actually collected, mapped to whether collection was complete that day.

    A day absent from the map is "missing", which is different from an observed zero. Uploads count
    as coverage only for the workspace they were uploaded to.
    """
    coverage: dict[Scope, dict[date, bool]] = defaultdict(dict)
    runs = db.scalars(select(IngestionRun).where(IngestionRun.status.in_(("succeeded", "partial")))).all()
    for run in runs:
        bounds = db.execute(
            select(func.min(SocialRecord.published_at), func.max(SocialRecord.published_at)).where(
                SocialRecord.ingestion_run_id == run.id
            )
        ).one()
        if run.source in CONNECTORS:
            # A sync covers from its window start (or its oldest post, on a first sync) up to when it ran.
            start = run.window_start or bounds[0] or run.started_at
            end = run.ended_at or run.started_at
        else:
            # A file covers the span of dates it contains.
            if bounds[0] is None:
                continue
            start, end = bounds
        complete = run.status == "succeeded"
        key = (run.source, run.workspace_id)
        day = utc_date(start)
        while day <= utc_date(end):
            coverage[key][day] = coverage[key].get(day, False) or complete
            day += timedelta(days=1)
    return coverage


def active_model_key(model: SentimentModel) -> tuple[str, str]:
    return model.name, model.version


def rebuild_daily_metrics(db: Session, model: SentimentModel) -> int:
    coverage = coverage_days(db)
    rows = db.execute(
        select(
            RecordMatch.tracked_entity_id,
            SocialRecord.source,
            SocialRecord.published_at,
            SocialRecord.content_hash,
            SocialRecord.engagement_json,
            NlpResult.sentiment,
            NlpResult.flags_json,
        )
        .join(SocialRecord, SocialRecord.id == RecordMatch.record_id)
        .outerjoin(
            NlpResult,
            (NlpResult.record_id == SocialRecord.id)
            & (NlpResult.model_name == model.name)
            & (NlpResult.model_version == model.version),
        )
    ).all()

    buckets: dict[tuple[uuid.UUID, str, date], dict] = defaultdict(
        lambda: {"mentions": 0, "hashes": set(), "engagement": 0, "engagement_records": 0,
                 "positive": 0, "neutral": 0, "negative": 0, "scored": 0, "low_confidence": 0}
    )
    for entity_id, source, published_at, content_hash, engagement, sentiment, flags in rows:
        b = buckets[(entity_id, source, utc_date(published_at))]
        b["mentions"] += 1
        b["hashes"].add(content_hash)
        if engagement:
            b["engagement"] += sum(v for k, v in engagement.items() if k in ENGAGEMENT_KEYS)
            b["engagement_records"] += 1
        if sentiment:
            b[sentiment] += 1
            b["scored"] += 1
            if flags and "low_confidence" in flags:
                b["low_confidence"] += 1

    # Every covered day gets a row for every entity, so a quiet day is an observed zero, not a gap.
    entity_workspace = dict(db.execute(select(TrackedEntity.id, Watchlist.workspace_id).join(Watchlist)).all())
    db.execute(delete(DailyMetric))
    count = 0
    for (source, workspace_id), days in coverage.items():
        entity_ids = [e for e, w in entity_workspace.items() if workspace_id is None or w == workspace_id]
        for day, complete in days.items():
            for entity_id in entity_ids:
                b = buckets.pop((entity_id, source, day), None)
                db.add(_metric_row(entity_id, source, day, b, complete))
                count += 1
    # Records outside any covered span (e.g. a sync's oldest posts) still count, flagged as such.
    for (entity_id, source, day), b in buckets.items():
        db.add(_metric_row(entity_id, source, day, b, False, outside=True))
        count += 1
    db.commit()
    return count


def _metric_row(entity_id, source, day, b, complete, outside=False) -> DailyMetric:
    b = b or {"mentions": 0, "hashes": set(), "engagement": 0, "engagement_records": 0,
              "positive": 0, "neutral": 0, "negative": 0, "scored": 0, "low_confidence": 0}
    scored = b["scored"]
    return DailyMetric(
        date=day,
        tracked_entity_id=entity_id,
        source=source,
        mentions=b["mentions"],
        unique_records=len(b["hashes"]),
        engagement=b["engagement"] if b["engagement_records"] else None,
        positive_share=round(b["positive"] / scored, 4) if scored else None,
        neutral_share=round(b["neutral"] / scored, 4) if scored else None,
        negative_share=round(b["negative"] / scored, 4) if scored else None,
        coverage_flags={
            "collection": "outside_window" if outside else ("complete" if complete else "incomplete"),
            "scored": scored,
            "low_confidence": b["low_confidence"],
            "engagement_records": b["engagement_records"],
        },
    )


def entity_series(db: Session, entity_id: uuid.UUID, sources: list[str] | None = None) -> list[trend.DayPoint]:
    """Daily points for one entity, summed across sources, with every calendar day filled in."""
    query = select(DailyMetric).where(DailyMetric.tracked_entity_id == entity_id)
    if sources:
        query = query.where(DailyMetric.source.in_(sources))
    by_day: dict[date, list[DailyMetric]] = defaultdict(list)
    for m in db.scalars(query):
        by_day[m.date].append(m)
    if not by_day:
        return []
    points = []
    day, last = min(by_day), max(by_day)
    while day <= last:
        rows = by_day.get(day, [])
        covered = [r for r in rows if r.coverage_flags.get("collection") != "outside_window"]
        engagement_rows = [r for r in rows if r.engagement is not None]
        positive = negative = scored = 0
        for r in rows:
            n = r.coverage_flags.get("scored", 0)
            scored += n
            positive += round((r.positive_share or 0) * n)
            negative += round((r.negative_share or 0) * n)
        points.append(
            trend.DayPoint(
                date=day,
                covered=bool(covered),
                complete=bool(covered) and all(r.coverage_flags.get("collection") == "complete" for r in covered),
                mentions=sum(r.mentions for r in rows),
                engagement=sum(r.engagement for r in engagement_rows) if engagement_rows else None,
                engagement_records=sum(r.coverage_flags.get("engagement_records", 0) for r in rows),
                positive=positive,
                negative=negative,
                scored=scored,
            )
        )
        day += timedelta(days=1)
    return points


def rebuild_trend_signals(db: Session) -> int:
    db.execute(delete(TrendSignal))
    count = 0
    for entity_id in db.scalars(select(TrackedEntity.id)).all():
        series = entity_series(db, entity_id)
        for idx, point in enumerate(series):
            result = trend.compute(series, idx)
            if result is None or not point.covered:
                continue
            db.add(
                TrendSignal(
                    tracked_entity_id=entity_id,
                    date=point.date,
                    score=result["score"],
                    components_json={k: v for k, v in result.items() if k not in ("score", "explanation_code")},
                    explanation_code=result["explanation_code"],
                )
            )
            count += 1
    db.commit()
    return count


def run_analysis(db: Session, model: SentimentModel) -> AnalysisSummary:
    new_matches = rematch_records(db)
    scored = score_pending(db, model)
    retagged = tag_stale_aspects(db, model)
    metrics = rebuild_daily_metrics(db, model)
    signals = rebuild_trend_signals(db)
    from app.ml.forecasting.service import refresh_forecasts  # imports this module

    from app.analytics.alerts import check_alerts

    forecasts = refresh_forecasts(db)
    fired = len(check_alerts(db))
    summary = AnalysisSummary(new_matches, scored, retagged, metrics, signals, forecasts, fired)
    logger.info("Analysis finished: %s", summary)
    return summary
