"""Rolling-origin back-test.

For each origin, a method sees only days before the origin and forecasts the next `horizon`
days. Errors are scored only on days that were actually collected, so a gap never counts as a
zero. Nothing from after an origin is used to fit, fill or scale anything before it.
"""

from dataclasses import dataclass, field

import numpy as np

from app.ml.forecasting.models import METHODS


@dataclass
class MethodResult:
    name: str
    errors: list[list[float]] = field(default_factory=list)  # per origin, per horizon step (NaN if uncollected)
    actuals: list[list[float]] = field(default_factory=list)
    failures: int = 0

    def flat(self) -> tuple[np.ndarray, np.ndarray]:
        e = np.array(self.errors, dtype=float).ravel()
        a = np.array(self.actuals, dtype=float).ravel()
        keep = ~np.isnan(e)
        return e[keep], a[keep]

    def metrics(self) -> dict | None:
        e, a = self.flat()
        if len(e) == 0:
            return None
        total = np.abs(a).sum()
        return {
            "mae": round(float(np.abs(e).mean()), 3),
            "rmse": round(float(np.sqrt((e**2).mean())), 3),
            "wape": round(float(np.abs(e).sum() / total), 4) if total > 0 else None,
            "n": int(len(e)),
        }

    def mae_by_step(self) -> list[float | None]:
        e = np.array(self.errors, dtype=float)
        out = []
        for step in range(e.shape[1]):
            col = e[:, step]
            col = col[~np.isnan(col)]
            out.append(round(float(np.abs(col).mean()), 3) if len(col) else None)
        return out


def origins(n: int, horizon: int, count: int, min_train: int) -> list[int]:
    """Indexes where forecasts start, newest last, spaced a week (or a horizon, if longer) apart so
    test windows don't overlap."""
    step = max(7, horizon)
    last = n - horizon
    out = [last - i * step for i in range(count)]
    return sorted(o for o in out if o >= min_train)


def run(y: np.ndarray, horizon: int, origin_count: int = 8, min_train: int = 28) -> tuple[list[int], dict[str, MethodResult]]:
    results = {name: MethodResult(name) for name in METHODS}
    starts = origins(len(y), horizon, origin_count, min_train)
    for o in starts:
        train, test = y[:o], y[o : o + horizon]
        for name, method in METHODS.items():
            try:
                pred = method.fn(train, horizon)
            except Exception:  # a method failing on one origin shouldn't sink the others
                results[name].failures += 1
                pred = np.full(horizon, np.nan)
            results[name].errors.append(list(pred - test))  # NaN where test day wasn't collected
            results[name].actuals.append(list(test))
    return starts, results


def interval_halfwidths(result: MethodResult, level: float) -> list[float | None]:
    """Per-step quantile of absolute back-test errors: the symmetric interval width that would
    have contained `level` of past errors at that horizon."""
    e = np.abs(np.array(result.errors, dtype=float))
    out = []
    for step in range(e.shape[1]):
        col = e[:, step]
        col = col[~np.isnan(col)]
        out.append(float(np.quantile(col, level)) if len(col) else None)
    return out


def interval_coverage(result: MethodResult, level: float) -> float | None:
    """Honest check of the interval: calibrate widths on the older half of origins and count how
    often the newer half's actuals fell inside."""
    k = len(result.errors) // 2
    if k < 2:
        return None
    older = MethodResult(result.name, result.errors[:k], result.actuals[:k])
    widths = interval_halfwidths(older, level)
    hits = total = 0
    for errs in result.errors[k:]:
        for step, err in enumerate(errs):
            if np.isnan(err) or widths[step] is None:
                continue
            total += 1
            hits += abs(err) <= widths[step]
    return round(hits / total, 3) if total else None
