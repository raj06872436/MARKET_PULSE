import csv
import io
import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.alerts import alert_entity_ids
from app.api.routes.metrics import _check_range
from app.core.config import Settings, get_settings
from app.db.models import Alert, AlertEvent, DailyMetric, InsightCard, TrackedEntity, Watchlist
from app.db.session import get_db
from app.insights.service import generate, llm_available
from app.ml.sentiment.registry import get_model
from app.schemas.insights import (
    AlertCreate,
    AlertEventOut,
    AlertOut,
    AlertUpdate,
    InsightBatch,
    InsightGenerate,
    InsightOut,
)

router = APIRouter(tags=["insights"])


def _watchlist(db: Session, watchlist_id: uuid.UUID) -> Watchlist:
    watchlist = db.get(Watchlist, watchlist_id)
    if watchlist is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Watchlist not found")
    return watchlist


def _insight_out(card: InsightCard) -> InsightOut:
    return InsightOut(
        id=card.id, watchlist_id=card.watchlist_id, entity_id=card.entity_id, period_start=card.period_start,
        period_end=card.period_end, observation=card.claim, interpretation=card.interpretation, caveat=card.caveat,
        suggested_action=card.suggested_action, evidence=card.evidence_json, generator=card.generator,
        model_version=card.model_version, generated_at=card.generated_at,
    )


# --- insights ------------------------------------------------------------------------------------------------


@router.post("/insights/generate", response_model=InsightBatch)
def generate_insights(
    payload: InsightGenerate, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> InsightBatch:
    watchlist = _watchlist(db, payload.watchlist_id)
    result = generate(db, watchlist, get_model(settings.sentiment_model), settings, payload.end, payload.use_llm)
    for card in result.cards:
        db.refresh(card)
    return InsightBatch(generator=result.generator, llm_status=result.llm_status, llm_available=llm_available(settings),
                        rejected=result.rejected, insights=[_insight_out(c) for c in result.cards])


@router.get("/insights", response_model=InsightBatch)
def latest_insights(
    watchlist_id: uuid.UUID, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> InsightBatch:
    """The most recent period's cards for a watchlist. Empty until someone generates them."""
    _watchlist(db, watchlist_id)
    latest = db.scalar(select(func.max(InsightCard.period_end)).where(InsightCard.watchlist_id == watchlist_id))
    cards = list(db.scalars(
        select(InsightCard).where(InsightCard.watchlist_id == watchlist_id, InsightCard.period_end == latest)
    )) if latest else []
    generator = cards[0].generator if cards else "template"
    return InsightBatch(generator=generator, llm_status="stored", llm_available=llm_available(settings),
                        rejected=[], insights=[_insight_out(c) for c in cards])


# --- export --------------------------------------------------------------------------------------------------

EXPORT_COLUMNS = [
    "date", "term", "entity_type", "source", "collection", "mentions", "unique_records", "engagement",
    "engagement_posts", "scored", "positive_share", "neutral_share", "negative_share",
]


@router.get("/export/daily.csv")
def export_daily(
    watchlist_id: uuid.UUID,
    start: date,
    end: date,
    source: list[str] | None = Query(None),
    db: Session = Depends(get_db),
) -> Response:
    """Daily aggregates per term and source. No post text or authors, only counts and shares.

    A day no source collected for a term gets a row with collection "not_collected" and empty
    values, so a gap can't be mistaken for zero mentions in a spreadsheet."""
    _check_range(start, end)
    watchlist = _watchlist(db, watchlist_id)
    entities = {e.id: e for e in watchlist.entities}
    query = select(DailyMetric).where(DailyMetric.tracked_entity_id.in_(list(entities)), DailyMetric.date >= start,
                                      DailyMetric.date <= end)
    if source:
        query = query.where(DailyMetric.source.in_(source))
    rows = list(db.scalars(query.order_by(DailyMetric.date, DailyMetric.source)))
    by_key: dict[tuple, list[DailyMetric]] = {}
    for r in rows:
        by_key.setdefault((r.date, r.tracked_entity_id), []).append(r)

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(EXPORT_COLUMNS)
    day = start
    while day <= end:
        for entity in watchlist.entities:
            day_rows = by_key.get((day, entity.id), [])
            if not day_rows:
                writer.writerow([day, entity.term, entity.entity_type, "", "not_collected"] + [""] * 8)
            for r in day_rows:
                flags = r.coverage_flags or {}
                collection = {"outside_window": "outside_window"}.get(flags.get("collection"), flags.get("collection", ""))
                writer.writerow([
                    day, entity.term, entity.entity_type, r.source, collection, r.mentions, r.unique_records,
                    "" if r.engagement is None else r.engagement, flags.get("engagement_records", ""), flags.get("scored", ""),
                    "" if r.positive_share is None else r.positive_share, "" if r.neutral_share is None else r.neutral_share,
                    "" if r.negative_share is None else r.negative_share,
                ])
        day += timedelta(days=1)
    filename = f"marketpulse-{watchlist.name.lower().replace(' ', '-')[:40]}-{start}-to-{end}.csv"
    safe = "".join(ch for ch in filename if ch.isalnum() or ch in "-._")
    return Response(out.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{safe}"'})


# --- alerts --------------------------------------------------------------------------------------------------


def _alert_out(db: Session, alert: Alert) -> AlertOut:
    entity = db.get(TrackedEntity, alert.entity_id)
    return AlertOut(id=alert.id, entity_id=alert.entity_id, term=entity.term, rule=alert.rule_json,
                    cooldown_minutes=alert.cooldown_minutes, active=alert.active,
                    last_triggered_at=alert.last_triggered_at, created_at=alert.created_at)


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(watchlist_id: uuid.UUID, db: Session = Depends(get_db)) -> list[AlertOut]:
    watchlist = _watchlist(db, watchlist_id)
    return [_alert_out(db, a) for a in alert_entity_ids(db, [e.id for e in watchlist.entities])]


@router.post("/alerts", response_model=AlertOut, status_code=status.HTTP_201_CREATED)
def create_alert(payload: AlertCreate, db: Session = Depends(get_db)) -> AlertOut:
    if db.get(TrackedEntity, payload.entity_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tracked term not found")
    alert = Alert(entity_id=payload.entity_id, rule_json=payload.rule.model_dump(), cooldown_minutes=payload.cooldown_minutes,
                  active=True)
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return _alert_out(db, alert)


@router.patch("/alerts/{alert_id}", response_model=AlertOut)
def update_alert(alert_id: uuid.UUID, payload: AlertUpdate, db: Session = Depends(get_db)) -> AlertOut:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    if payload.active is not None:
        alert.active = payload.active
    if payload.cooldown_minutes is not None:
        alert.cooldown_minutes = payload.cooldown_minutes
    if payload.rule is not None:
        alert.rule_json = payload.rule.model_dump()
    db.commit()
    db.refresh(alert)
    return _alert_out(db, alert)


@router.delete("/alerts/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alert(alert_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    db.delete(alert)
    db.commit()


@router.get("/alerts/events", response_model=list[AlertEventOut])
def alert_events(watchlist_id: uuid.UUID, limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)) -> list[AlertEventOut]:
    watchlist = _watchlist(db, watchlist_id)
    terms = {e.id: e.term for e in watchlist.entities}
    rows = db.execute(
        select(AlertEvent, Alert.entity_id).join(Alert, Alert.id == AlertEvent.alert_id)
        .where(Alert.entity_id.in_(list(terms))).order_by(AlertEvent.triggered_at.desc(), AlertEvent.data_date.desc()).limit(limit)
    ).all()
    return [AlertEventOut(id=e.id, alert_id=e.alert_id, entity_id=eid, term=terms[eid], triggered_at=e.triggered_at,
                          data_date=e.data_date, value=e.value, threshold=e.threshold, message=e.message) for e, eid in rows]
