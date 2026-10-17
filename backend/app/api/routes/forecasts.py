import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ForecastPoint, ForecastRun, TrackedEntity, Watchlist
from app.db.session import get_db
from app.ml.forecasting.models import METHODS
from app.ml.forecasting.service import build_series, create_forecast, latest_run
from app.schemas.forecast import ForecastCreate, ForecastOut

router = APIRouter(prefix="/forecasts", tags=["forecasts"])
HISTORY_DAYS = 56


def to_out(db: Session, run: ForecastRun) -> ForecastOut:
    entity = db.get(TrackedEntity, run.entity_id)
    info = run.metrics_json or {}
    dates, y = build_series(db, run.entity_id)
    observed = {d: (None if v != v else int(v)) for d, v in zip(dates, y)}  # v != v is NaN
    history = []
    if run.training_end is not None:
        day = run.training_end - timedelta(days=HISTORY_DAYS - 1)
        while day <= run.training_end:
            history.append({"date": day, "mentions": observed.get(day)})
            day += timedelta(days=1)
    points = db.scalars(
        select(ForecastPoint).where(ForecastPoint.forecast_run_id == run.id).order_by(ForecastPoint.target_date)
    ).all()
    bt = info.get("backtest")
    return ForecastOut(
        id=run.id,
        entity_id=run.entity_id,
        term=entity.term,
        status=run.status,
        method=run.method,
        method_label=METHODS[run.method].label if run.method in METHODS else None,
        model_version=run.model_version,
        horizon_days=run.horizon_days,
        training_start=run.training_start,
        training_end=run.training_end,
        created_at=run.created_at,
        checks=info.get("checks", []),
        interval_level=info.get("interval_level", 0.8),
        interval_coverage=info.get("interval_coverage"),
        candidate_beats_baseline=info.get("candidate_beats_baseline"),
        backtest=(
            {
                "origins": bt["origins"],
                "horizon_days": bt["horizon_days"],
                # JSONB doesn't keep key order, so list methods in their defined order.
                "methods": [{"name": name, **bt["methods"][name]} for name in METHODS if name in bt["methods"]],
            }
            if bt
            else None
        ),
        history=history,
        points=[
            {
                "date": p.target_date,
                "predicted": p.predicted_value,
                "lower": p.lower_bound,
                "upper": p.upper_bound,
                "actual": observed.get(p.target_date),
            }
            for p in points
        ],
    )


@router.post("", response_model=ForecastOut, status_code=status.HTTP_201_CREATED)
def create(payload: ForecastCreate, db: Session = Depends(get_db)) -> ForecastOut:
    entity = db.get(TrackedEntity, payload.entity_id)
    if entity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tracked term not found")
    run = create_forecast(db, entity, payload.horizon_days)
    return to_out(db, run)


@router.get("", response_model=list[ForecastOut])
def latest_for_watchlist(watchlist_id: uuid.UUID = Query(...), db: Session = Depends(get_db)) -> list[ForecastOut]:
    """The newest forecast for each term in a watchlist. Terms never forecast are left out."""
    watchlist = db.get(Watchlist, watchlist_id)
    if watchlist is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Watchlist not found")
    runs = [latest_run(db, e.id) for e in watchlist.entities]
    return [to_out(db, r) for r in runs if r is not None]


@router.get("/{forecast_id}", response_model=ForecastOut)
def get(forecast_id: uuid.UUID, db: Session = Depends(get_db)) -> ForecastOut:
    run = db.get(ForecastRun, forecast_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Forecast not found")
    return to_out(db, run)
