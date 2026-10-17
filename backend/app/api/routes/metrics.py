import uuid
from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.evidence import gather_evidence
from app.core.config import Settings, get_settings
from app.db.models import DailyMetric, TrackedEntity, TrendSignal, Watchlist
from app.db.session import get_db
from app.ml.sentiment.registry import get_model
from app.schemas.metrics import EntitySeries, Evidence, SeriesPoint, SeriesResponse, TrendCard

router = APIRouter(tags=["metrics"])
MAX_RANGE_DAYS = 366


def _parse_ids(raw: str) -> list[uuid.UUID]:
    try:
        return [uuid.UUID(part) for part in raw.split(",") if part.strip()]
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "entity_ids must be comma-separated UUIDs") from None


def _check_range(start: date, end: date) -> None:
    if end < start:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "end must not be before start")
    if (end - start).days >= MAX_RANGE_DAYS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Date range is limited to {MAX_RANGE_DAYS} days")


def build_points(rows: list[DailyMetric], start: date, end: date) -> list[SeriesPoint]:
    by_day: dict[date, list[DailyMetric]] = defaultdict(list)
    for r in rows:
        by_day[r.date].append(r)
    points = []
    day = start
    while day <= end:
        day_rows = by_day.get(day, [])
        covered = [r for r in day_rows if r.coverage_flags.get("collection") != "outside_window"]
        if not day_rows:
            points.append(SeriesPoint(date=day, collection="missing", mentions=None, engagement=None,
                                      positive_share=None, neutral_share=None, negative_share=None, scored=0))
        else:
            scored = sum(r.coverage_flags.get("scored", 0) for r in day_rows)

            def share(attr: str) -> float | None:
                if not scored:
                    return None
                return round(sum((getattr(r, attr) or 0) * r.coverage_flags.get("scored", 0) for r in day_rows) / scored, 4)

            engagement_rows = [r.engagement for r in day_rows if r.engagement is not None]
            complete = bool(covered) and all(r.coverage_flags.get("collection") == "complete" for r in covered)
            points.append(SeriesPoint(
                date=day, collection="complete" if complete else "incomplete", mentions=sum(r.mentions for r in day_rows),
                engagement=sum(engagement_rows) if engagement_rows else None, positive_share=share("positive_share"),
                neutral_share=share("neutral_share"), negative_share=share("negative_share"), scored=scored,
            ))
        day += timedelta(days=1)
    return points


@router.get("/metrics/series", response_model=SeriesResponse)
def metrics_series(
    entity_ids: str = Query(..., description="Comma-separated tracked entity IDs"),
    start: date = Query(...),
    end: date = Query(...),
    source: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
) -> SeriesResponse:
    _check_range(start, end)
    ids = _parse_ids(entity_ids)
    entities = {e.id: e for e in db.scalars(select(TrackedEntity).where(TrackedEntity.id.in_(ids)))}
    if missing := [str(i) for i in ids if i not in entities]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown entity: {', '.join(missing)}")
    query = select(DailyMetric).where(DailyMetric.tracked_entity_id.in_(ids), DailyMetric.date >= start, DailyMetric.date <= end)
    if source:
        query = query.where(DailyMetric.source.in_(source))
    rows: dict[uuid.UUID, list[DailyMetric]] = defaultdict(list)
    sources: set[str] = set()
    for r in db.scalars(query):
        rows[r.tracked_entity_id].append(r)
        sources.add(r.source)
    return SeriesResponse(
        start=start,
        end=end,
        sources=sorted(sources),
        series=[
            EntitySeries(entity_id=i, term=entities[i].term, entity_type=entities[i].entity_type,
                         points=build_points(rows[i], start, end))
            for i in ids
        ],
    )


@router.get("/entities/{entity_id}/evidence", response_model=Evidence)
def entity_evidence(
    entity_id: uuid.UUID,
    start: date = Query(...),
    end: date = Query(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Evidence:
    _check_range(start, end)
    entity = db.get(TrackedEntity, entity_id)
    if entity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entity not found")
    return gather_evidence(db, entity, start, end, get_model(settings.sentiment_model))


@router.get("/trends", response_model=list[TrendCard])
def trends(
    watchlist_id: uuid.UUID, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> list[TrendCard]:
    watchlist = db.get(Watchlist, watchlist_id)
    if watchlist is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Watchlist not found")
    model = get_model(settings.sentiment_model)
    cards = []
    for entity in watchlist.entities:
        signal = db.scalar(
            select(TrendSignal).where(TrendSignal.tracked_entity_id == entity.id).order_by(TrendSignal.date.desc())
        )
        last_day = signal.date if signal else db.scalar(
            select(DailyMetric.date).where(DailyMetric.tracked_entity_id == entity.id).order_by(DailyMetric.date.desc())
        )
        sparkline, evidence = [], None
        if last_day:
            first = last_day - timedelta(days=27)
            rows = list(db.scalars(select(DailyMetric).where(
                DailyMetric.tracked_entity_id == entity.id, DailyMetric.date >= first, DailyMetric.date <= last_day)))
            sparkline = build_points(rows, first, last_day)
            evidence = gather_evidence(db, entity, last_day - timedelta(days=6), last_day, model)
        cards.append(TrendCard(
            entity_id=entity.id, term=entity.term, entity_type=entity.entity_type, competitor_group=entity.competitor_group,
            date=signal.date if signal else None, score=signal.score if signal else None,
            explanation_code=signal.explanation_code if signal else None,
            details=signal.components_json if signal else None, sparkline=sparkline, evidence=evidence,
        ))
    cards.sort(key=lambda c: -(c.score if c.score is not None else -1))
    return cards
