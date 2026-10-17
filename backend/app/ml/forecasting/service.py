"""Forecast one tracked entity's daily mentions, or explain why not (plan sections 8.5 and 12).

Flow: build the daily series (NaN for uncollected days) -> data checks -> rolling-origin
back-test of every method -> choose -> fit on all history -> store points with intervals.

The method with the lowest back-test error is shown, so the candidate (exponential smoothing)
only appears when it beat every baseline, including same-day-last-week. The run records whether
the candidate beat that reference baseline, as the plan requires before calling the model useful.
"""

import logging
import math
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.pipeline import entity_series
from app.db.models import ForecastPoint, ForecastRun, TrackedEntity, Watchlist
from app.ml.forecasting import backtest
from app.ml.forecasting.models import CANDIDATE, METHODS, REFERENCE_BASELINE

logger = logging.getLogger(__name__)

FORECAST_VERSION = "fc-1"
DEFAULT_HORIZON = 7
MAX_HORIZON = 14
INTERVAL_LEVEL = 0.8

# Data checks. A forecast is only made when all of them pass.
MIN_HISTORY_DAYS = 56  # eight weeks, so seasonality and at least four back-test origins fit
RECENT_DAYS = 56
MIN_RECENT_COVERAGE = 0.85
MAX_RECENT_ZERO_SHARE = 0.5
MIN_RECENT_MEAN = 2.0
MIN_BACKTEST_ORIGINS = 4


@dataclass
class Check:
    name: str
    passed: bool
    detail: str

    def as_dict(self) -> dict:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


def build_series(db: Session, entity_id) -> tuple[list[date], np.ndarray]:
    """Daily mentions from the first to the last collected day; NaN where nothing was collected."""
    points = entity_series(db, entity_id)
    covered = [i for i, p in enumerate(points) if p.covered]
    if not covered:
        return [], np.array([], dtype=float)
    points = points[covered[0] : covered[-1] + 1]
    return [p.date for p in points], np.array([p.mentions if p.covered else np.nan for p in points], dtype=float)


def data_checks(y: np.ndarray, horizon: int) -> list[Check]:
    recent = y[-RECENT_DAYS:]
    observed = recent[~np.isnan(recent)]
    coverage = len(observed) / len(recent) if len(recent) else 0.0
    zero_share = float((observed == 0).mean()) if len(observed) else 1.0
    mean = float(observed.mean()) if len(observed) else 0.0
    origins = backtest.origins(len(y), horizon, 8, 28)
    return [
        Check("history", len(y) >= MIN_HISTORY_DAYS, f"{len(y)} days of history; {MIN_HISTORY_DAYS} needed"),
        Check(
            "coverage",
            coverage >= MIN_RECENT_COVERAGE,
            f"{coverage:.0%} of the last {len(recent)} days collected; {MIN_RECENT_COVERAGE:.0%} needed",
        ),
        Check(
            "sparsity",
            zero_share <= MAX_RECENT_ZERO_SHARE and mean >= MIN_RECENT_MEAN,
            f"{mean:.1f} mentions a day on average, {zero_share:.0%} of days with none; "
            f"at least {MIN_RECENT_MEAN:g} a day and at most {MAX_RECENT_ZERO_SHARE:.0%} empty days needed",
        ),
        Check(
            "backtest",
            len(origins) >= MIN_BACKTEST_ORIGINS,
            f"{len(origins)} back-test windows available; {MIN_BACKTEST_ORIGINS} needed",
        ),
    ]


def _score(m: dict | None) -> float:
    """Selection metric: WAPE, or MAE when the actuals were all zero."""
    if m is None:
        return math.inf
    return m["wape"] if m["wape"] is not None else m["mae"]


def choose(metrics: dict[str, dict | None]) -> tuple[str, bool]:
    """Returns (method with the lowest back-test error, whether the candidate beat the reference baseline).

    Ties go to the simpler method, which comes first in METHODS."""
    beats = _score(metrics[CANDIDATE]) < _score(metrics[REFERENCE_BASELINE])
    return min(METHODS, key=lambda n: _score(metrics[n])), beats


def create_forecast(db: Session, entity: TrackedEntity, horizon: int = DEFAULT_HORIZON) -> ForecastRun:
    if not 1 <= horizon <= MAX_HORIZON:
        raise ValueError(f"horizon must be between 1 and {MAX_HORIZON} days")
    dates, y = build_series(db, entity.id)
    run = ForecastRun(
        entity_id=entity.id,
        model_version=FORECAST_VERSION,
        horizon_days=horizon,
        training_start=dates[0] if dates else None,
        training_end=dates[-1] if dates else None,
    )
    checks = data_checks(y, horizon) if len(y) else [Check("history", False, "No collected days for this term yet")]
    info: dict = {"checks": [c.as_dict() for c in checks], "interval_level": INTERVAL_LEVEL}
    if not all(c.passed for c in checks):
        run.status = "insufficient_data"
        run.metrics_json = info
        db.add(run)
        db.commit()
        return run

    try:
        starts, results = backtest.run(y, horizon)
        metrics = {name: r.metrics() for name, r in results.items()}
        method, beats = choose(metrics)
        result = results[method]
        widths = backtest.interval_halfwidths(result, INTERVAL_LEVEL)
        pred = METHODS[method].fn(y, horizon)
    except Exception as exc:  # pragma: no cover - statsmodels or numeric failure
        logger.exception("Forecast failed for %s", entity.id)
        run.status = "failed"
        run.metrics_json = {**info, "error": type(exc).__name__}
        db.add(run)
        db.commit()
        return run

    run.status = "ready"
    run.method = method
    run.metrics_json = {
        **info,
        "candidate": CANDIDATE,
        "reference_baseline": REFERENCE_BASELINE,
        "candidate_beats_baseline": beats,
        "backtest": {
            "origins": [dates[o].isoformat() for o in starts],
            "horizon_days": horizon,
            "methods": {
                name: {
                    "label": METHODS[name].label,
                    "kind": METHODS[name].kind,
                    **(metrics[name] or {}),
                    "mae_by_horizon": results[name].mae_by_step(),
                    "failures": results[name].failures,
                }
                for name in METHODS
            },
        },
        "interval_coverage": backtest.interval_coverage(result, INTERVAL_LEVEL),
    }
    db.add(run)
    db.flush()
    for step in range(horizon):
        value = max(float(pred[step]), 0.0)
        width = widths[step]
        db.add(
            ForecastPoint(
                forecast_run_id=run.id,
                target_date=run.training_end + timedelta(days=step + 1),
                predicted_value=round(value, 2),
                lower_bound=round(max(value - width, 0.0), 2) if width is not None else None,
                upper_bound=round(value + width, 2) if width is not None else None,
            )
        )
    db.commit()
    return run


def latest_run(db: Session, entity_id) -> ForecastRun | None:
    return db.scalars(
        select(ForecastRun)
        .where(ForecastRun.entity_id == entity_id)
        .order_by(ForecastRun.created_at.desc(), ForecastRun.training_end.desc().nulls_last())
        .limit(1)
    ).first()


def refresh_forecasts(db: Session) -> int:
    """Forecast every term in an active watchlist whose data has moved on since its last forecast.

    This is the documented retraining schedule: a new forecast only when a newer collected day
    exists, so repeated analysis runs don't pile up identical forecasts.
    """
    created = 0
    query = (
        select(TrackedEntity)
        .join(Watchlist, Watchlist.id == TrackedEntity.watchlist_id)
        .where(Watchlist.active.is_(True))
    )
    for entity in db.scalars(query).all():
        dates, _ = build_series(db, entity.id)
        last = latest_run(db, entity.id)
        newest = dates[-1] if dates else None
        if last is not None and last.training_end == newest and last.model_version == FORECAST_VERSION:
            continue
        if newest is None and last is not None:
            continue
        create_forecast(db, entity)
        created += 1
    return created
