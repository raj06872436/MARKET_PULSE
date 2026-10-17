import math
import uuid
from datetime import date, timedelta

import numpy as np
import pytest

from app.db.models import DailyMetric, ForecastPoint, ForecastRun, TrackedEntity
from app.ml.forecasting import backtest, models, service

START = date(2026, 6, 1)


def weekly(days: int, base: float = 20, seed: int = 0) -> np.ndarray:
    """A steady series with a weekend bump and a little noise."""
    rng = np.random.default_rng(seed)
    t = np.arange(days)
    return np.round(base + 6 * (t % 7 >= 5) + rng.normal(0, 1.5, days)).clip(0)


def add_metrics(db, entity_id, values, start=START):
    """One daily_metrics row per value; None means the day was never collected (no row)."""
    for i, v in enumerate(values):
        if v is None:
            continue
        db.add(DailyMetric(date=start + timedelta(days=i), tracked_entity_id=entity_id, source="csv:test",
                           mentions=int(v), unique_records=int(v), coverage_flags={"collection": "complete", "scored": 0}))
    db.commit()


def entity(db, watchlist_id, term="Redmi Note 14") -> TrackedEntity:
    return db.query(TrackedEntity).filter_by(watchlist_id=uuid.UUID(watchlist_id), term=term).one()


# --- methods ---------------------------------------------------------------------------------------------


def test_baselines():
    y = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14], dtype=float)
    assert models.last_value(y, 3).tolist() == [14, 14, 14]
    assert models.trailing_mean(y, 2).tolist() == [11, 11]
    assert models.seasonal_naive(y, 9).tolist() == [8, 9, 10, 11, 12, 13, 14, 8, 9]


def test_gaps_are_interpolated_for_training_only():
    y = np.array([10, np.nan, np.nan, 16, 18], dtype=float)
    assert models.fill_gaps(y).tolist() == [10, 12, 14, 16, 18]
    assert models.last_value(np.array([5, 7, np.nan]), 1).tolist() == [7]


def test_exponential_smoothing_is_non_negative_and_follows_the_week():
    y = weekly(84)
    pred = models.exponential_smoothing(y, 14)
    assert (pred >= 0).all()
    # Days 5 and 6 of each week are the bump.
    weekend = [pred[i] for i in range(14) if (84 + i) % 7 >= 5]
    weekday = [pred[i] for i in range(14) if (84 + i) % 7 < 5]
    assert min(weekend) > max(weekday)


# --- back-test -------------------------------------------------------------------------------------------


def test_backtest_trains_only_on_the_past(monkeypatch):
    seen = []

    def spy(train, horizon):
        seen.append(len(train))
        return np.zeros(horizon)

    monkeypatch.setattr(backtest, "METHODS", {"spy": models.Method("spy", "Spy", "baseline", spy)})
    y = np.arange(70, dtype=float)
    starts, results = backtest.run(y, 7)
    assert starts == [28, 35, 42, 49, 56, 63]
    assert seen == starts  # each fit sees exactly the days before its origin
    # Errors are prediction minus actual for the 7 days after each origin.
    assert results["spy"].errors[0] == [-(28 + i) for i in range(7)]


def test_uncollected_test_days_are_not_scored_as_zero():
    y = np.full(70, 10.0)
    y[65] = np.nan
    _, results = backtest.run(y, 7)
    m = results["last_value"].metrics()
    assert m["mae"] == 0 and m["n"] == 6 * 7 - 1


def test_metrics_and_interval_coverage():
    r = backtest.MethodResult("x", errors=[[1, -2], [3, np.nan], [-1, 1], [2, 2]], actuals=[[10, 10], [10, 10], [10, 10], [10, 10]])
    m = r.metrics()
    assert m["mae"] == pytest.approx(12 / 7, abs=1e-3)
    assert m["rmse"] == pytest.approx(math.sqrt(24 / 7), abs=1e-3)
    assert m["wape"] == pytest.approx(12 / 70, abs=1e-4)
    assert r.mae_by_step() == [1.75, pytest.approx(5 / 3, abs=1e-3)]
    # Widths from the older two origins: step 0 -> quantile of [1, 3], step 1 -> [2].
    # Newer origins' errors [-1, 1] and [2, 2]: 1<=2.6, 1<=2, 2<=2.6, 2<=2 -> all inside.
    assert backtest.interval_coverage(r, 0.8) == 1.0


def test_choose_prefers_lowest_error_and_reports_baseline_comparison():
    metrics = {name: {"wape": 0.3, "mae": 3} for name in models.METHODS}
    assert service.choose(metrics) == ("last_value", False)  # ties go to the simplest method
    metrics["ets"] = {"wape": 0.2, "mae": 2}
    assert service.choose(metrics) == ("ets", True)
    metrics["trailing_mean"] = {"wape": 0.1, "mae": 1}
    assert service.choose(metrics) == ("trailing_mean", True)


# --- data checks -----------------------------------------------------------------------------------------


def test_data_checks():
    def failed(y):
        return {c.name for c in service.data_checks(np.asarray(y, dtype=float), 7) if not c.passed}

    assert failed(weekly(84)) == set()
    assert failed(weekly(40)) == {"history", "backtest"}
    gappy = weekly(84)
    gappy[-20:-8] = np.nan
    assert failed(gappy) == {"coverage"}
    sparse = np.zeros(84)
    sparse[::3] = 4
    assert failed(sparse) == {"sparsity"}


# --- service and API -------------------------------------------------------------------------------------


def test_insufficient_data_is_stored_without_points(client, watchlist_id, db_session):
    e = entity(db_session, watchlist_id)
    add_metrics(db_session, e.id, weekly(30))
    response = client.post("/api/forecasts", json={"entity_id": str(e.id)})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "insufficient_data"
    assert body["points"] == [] and body["backtest"] is None
    assert any(c["name"] == "history" and not c["passed"] for c in body["checks"])

    other = entity(db_session, watchlist_id, "Poco")
    body = client.post("/api/forecasts", json={"entity_id": str(other.id)}).json()
    assert body["status"] == "insufficient_data" and body["training_end"] is None


def test_forecast_with_backtest_and_intervals(client, watchlist_id, db_session):
    e = entity(db_session, watchlist_id)
    values = list(weekly(84))
    values[50] = values[51] = None  # two uncollected days
    add_metrics(db_session, e.id, values)

    body = client.post("/api/forecasts", json={"entity_id": str(e.id), "horizon_days": 10}).json()
    assert body["status"] == "ready", body["checks"]
    assert body["training_end"] == (START + timedelta(days=83)).isoformat()
    assert [p["date"] for p in body["points"]] == [(START + timedelta(days=84 + i)).isoformat() for i in range(10)]
    for p in body["points"]:
        assert 0 <= p["lower"] <= p["predicted"] <= p["upper"]
        assert p["actual"] is None  # not collected yet
    names = {m["name"] for m in body["backtest"]["methods"]}
    assert names == set(models.METHODS)
    shown = next(m for m in body["backtest"]["methods"] if m["name"] == body["method"])
    assert shown["wape"] == min(m["wape"] for m in body["backtest"]["methods"])
    assert len(body["backtest"]["origins"]) == 5  # 10-day windows, spaced 10 days apart
    assert len(body["history"]) == 56
    assert body["history"][50 - 28]["mentions"] is None  # the gap shows as not collected, not zero

    # Once the forecast days are collected, the stored forecast shows the actuals next to it.
    add_metrics(db_session, e.id, [25, 26], start=START + timedelta(days=84))
    again = client.get(f"/api/forecasts/{body['id']}").json()
    assert [p["actual"] for p in again["points"][:3]] == [25, 26, None]

    listed = client.get("/api/forecasts", params={"watchlist_id": watchlist_id}).json()
    assert {f["term"]: f["status"] for f in listed} == {"Redmi Note 14": "ready", "Poco": "insufficient_data"}
    assert next(f["id"] for f in listed if f["term"] == "Redmi Note 14") == body["id"]


def test_refresh_only_when_new_data_arrives(watchlist_id, db_session):
    e = entity(db_session, watchlist_id)
    add_metrics(db_session, e.id, weekly(70))
    # Adding the terms already recorded an "insufficient data" run for each. Only Redmi has new data.
    assert service.refresh_forecasts(db_session) == 1
    assert service.refresh_forecasts(db_session) == 0
    add_metrics(db_session, e.id, [20], start=START + timedelta(days=70))
    assert service.refresh_forecasts(db_session) == 1
    statuses = [r.status for r in db_session.query(ForecastRun).filter_by(entity_id=e.id)]
    assert sorted(statuses) == ["insufficient_data", "ready", "ready"]
    assert db_session.query(ForecastPoint).count() == 14


def test_forecast_input_validation(client, watchlist_id, db_session):
    e = entity(db_session, watchlist_id)
    assert client.post("/api/forecasts", json={"entity_id": str(e.id), "horizon_days": 0}).status_code == 422
    assert client.post("/api/forecasts", json={"entity_id": str(e.id), "horizon_days": 15}).status_code == 422
    assert client.post("/api/forecasts", json={"entity_id": str(uuid.uuid4())}).status_code == 404
    assert client.get(f"/api/forecasts/{uuid.uuid4()}").status_code == 404
    assert client.get("/api/forecasts", params={"watchlist_id": str(uuid.uuid4())}).status_code == 404
