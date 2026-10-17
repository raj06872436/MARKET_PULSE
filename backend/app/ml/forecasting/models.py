"""Forecasting methods (plan section 8.5).

Every method takes a daily history with NaN for days no source collected and returns point
forecasts for the next `horizon` days. Intervals are added later from back-test errors, so all
methods are treated the same way and intervals reflect how wrong each method actually was.
"""

import warnings
from dataclasses import dataclass
from typing import Callable

import numpy as np

SEASON = 7


def fill_gaps(y: np.ndarray) -> np.ndarray:
    """Linearly interpolate uncollected days for methods that need a continuous series.

    Only used for training input. Leading gaps are dropped by the caller; a trailing gap is
    carried forward from the last observed day.
    """
    y = np.asarray(y, dtype=float)
    observed = ~np.isnan(y)
    if observed.all():
        return y
    idx = np.arange(len(y))
    return np.interp(idx, idx[observed], y[observed])


def last_value(y: np.ndarray, horizon: int) -> np.ndarray:
    observed = y[~np.isnan(y)]
    return np.full(horizon, observed[-1])


def trailing_mean(y: np.ndarray, horizon: int, window: int = 7) -> np.ndarray:
    observed = y[~np.isnan(y)]
    return np.full(horizon, observed[-window:].mean())


def seasonal_naive(y: np.ndarray, horizon: int) -> np.ndarray:
    """Same weekday last week. Falls back to the gap-filled value when that day wasn't collected."""
    filled = fill_gaps(y)
    last_week = filled[-SEASON:]
    return np.array([last_week[i % SEASON] for i in range(horizon)])


def exponential_smoothing(y: np.ndarray, horizon: int) -> np.ndarray:
    """Holt-Winters on log1p counts: damped additive trend, additive weekly seasonality.

    Log space keeps forecasts non-negative and lets weekly swings scale with volume.
    """
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    z = np.log1p(np.maximum(fill_gaps(y), 0))
    seasonal = "add" if len(z) >= 4 * SEASON else None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = ExponentialSmoothing(
            z,
            trend="add",
            damped_trend=True,
            seasonal=seasonal,
            seasonal_periods=SEASON if seasonal else None,
            initialization_method="estimated",
        ).fit(optimized=True)
    return np.maximum(np.expm1(fit.forecast(horizon)), 0)


@dataclass(frozen=True)
class Method:
    name: str
    label: str
    kind: str  # "baseline" or "candidate"
    fn: Callable[[np.ndarray, int], np.ndarray]


METHODS: dict[str, Method] = {
    m.name: m
    for m in [
        Method("last_value", "Last value", "baseline", last_value),
        Method("trailing_mean", "7-day average", "baseline", trailing_mean),
        Method("seasonal_naive", "Same day last week", "baseline", seasonal_naive),
        Method("ets", "Exponential smoothing", "candidate", exponential_smoothing),
    ]
}
REFERENCE_BASELINE = "seasonal_naive"
CANDIDATE = "ets"
