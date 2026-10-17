"""Threshold alerts with a cooldown.

Rules are checked on each term's latest collected day after every analysis run. A day nobody
collected is never treated as zero, so an outage can't fire (or hide) an alert. Each rule fires at
most once per data day and not again until its cooldown has passed. Alerts are shown in the app;
nothing is sent outside it.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.pipeline import entity_series
from app.db.models import Alert, AlertEvent, TrackedEntity, TrendSignal

METRICS = {
    "daily_mentions": "Daily mentions",
    "weekly_change": "Change in weekly mentions",
    "negative_share": "Negative share",
    "trend_score": "Trend score",
}
MIN_WINDOW_DAYS = 6  # of 7, for the weekly rules


def evaluate(db: Session, alert: Alert) -> tuple[float, object] | None:
    """(value, data_date) for the rule on the term's latest collected day, or None if it can't be judged."""
    rule = alert.rule_json
    series = entity_series(db, alert.entity_id)
    covered = [p for p in series if p.covered]
    if not covered:
        return None
    last = covered[-1]
    idx = series.index(last)
    metric = rule["metric"]
    if metric == "daily_mentions":
        return float(last.mentions), last.date
    if metric == "trend_score":
        signal = db.scalar(select(TrendSignal).where(TrendSignal.tracked_entity_id == alert.entity_id, TrendSignal.date == last.date))
        return (signal.score, last.date) if signal else None
    week = series[max(0, idx - 6) : idx + 1]
    if sum(p.covered for p in week) < MIN_WINDOW_DAYS:
        return None
    if metric == "weekly_change":
        prev = series[max(0, idx - 13) : max(0, idx - 6)]
        if len(prev) < 7 or sum(p.covered for p in prev) < MIN_WINDOW_DAYS:
            return None
        before = sum(p.mentions for p in prev)
        if before == 0:
            return None
        return (sum(p.mentions for p in week) - before) / before * 100, last.date
    if metric == "negative_share":
        scored = sum(p.scored for p in week)
        if scored < rule.get("min_posts", 10):
            return None
        return sum(p.negative for p in week) / scored * 100, last.date
    return None


def check_alerts(db: Session, now: datetime | None = None) -> list[AlertEvent]:
    now = now or datetime.now(UTC)
    fired = []
    for alert in db.scalars(select(Alert).where(Alert.active.is_(True))).all():
        result = evaluate(db, alert)
        if result is None:
            continue
        value, day = result
        threshold = float(alert.rule_json["threshold"])
        if value < threshold:
            continue
        last = alert.last_triggered_at
        if last is not None and last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        if last is not None and now - last < timedelta(minutes=alert.cooldown_minutes):
            continue
        if db.scalar(select(AlertEvent.id).where(AlertEvent.alert_id == alert.id, AlertEvent.data_date == day)):
            continue
        entity = db.get(TrackedEntity, alert.entity_id)
        weekly = alert.rule_json["metric"] in ("weekly_change", "negative_share")
        unit = "%" if weekly else ""
        when = f"in the 7 days to {day}" if weekly else f"on {day}"
        event = AlertEvent(
            alert_id=alert.id, triggered_at=now, data_date=day, value=round(value, 2), threshold=threshold,
            message=f"{METRICS[alert.rule_json['metric']]} for {entity.term} was {value:.0f}{unit} {when}, "
                    f"at or above the {threshold:g}{unit} threshold.",
        )
        alert.last_triggered_at = now
        db.add(event)
        fired.append(event)
    db.commit()
    return fired


def alert_entity_ids(db: Session, watchlist_entity_ids: list[uuid.UUID]) -> list[Alert]:
    return list(db.scalars(select(Alert).where(Alert.entity_id.in_(watchlist_entity_ids)).order_by(Alert.created_at)))
