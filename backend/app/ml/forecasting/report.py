"""Write a back-test report for the latest forecast of every term.

    python -m app.ml.forecasting.report --out ../docs/evaluation/forecast.md

Per-term rows plus an aggregate, where aggregate WAPE is total absolute error over total actual
mentions across every term and back-test window.
"""

import argparse
from pathlib import Path

from sqlalchemy import select

from app.db.models import TrackedEntity
from app.db.session import get_session_factory
from app.ml.forecasting.models import CANDIDATE, METHODS, REFERENCE_BASELINE
from app.ml.forecasting.service import FORECAST_VERSION, latest_run


def fmt(v, pct=False):
    if v is None:
        return "–"
    return f"{v:.1%}" if pct else f"{v:.2f}"


def build(db, note: str = "") -> str:
    lines = [
        "# Forecast back-test",
        "",
        f"Forecast version `{FORECAST_VERSION}`. Each method forecasts daily mentions from rolling weekly origins, "
        "trained only on days before each origin and scored only on days that were collected. Lower is better.",
        "",
    ]
    if note:
        lines += [note, ""]
    totals = {name: [0.0, 0.0, 0] for name in METHODS}  # abs error, actual, n
    beats = shown_candidate = ready = 0
    rows = []
    for entity in db.scalars(select(TrackedEntity).order_by(TrackedEntity.term)):
        run = latest_run(db, entity.id)
        if run is None:
            continue
        if run.status != "ready":
            failed = [c["detail"] for c in run.metrics_json.get("checks", []) if not c["passed"]]
            rows.append(f"| {entity.term} | no forecast: {'; '.join(failed) or run.status} | | | | |")
            continue
        ready += 1
        info = run.metrics_json
        beats += bool(info["candidate_beats_baseline"])
        shown_candidate += run.method == CANDIDATE
        methods = info["backtest"]["methods"]
        for name, m in methods.items():
            if m.get("n"):
                totals[name][0] += m["mae"] * m["n"]
                totals[name][1] += (m["mae"] * m["n"] / m["wape"]) if m.get("wape") else 0
                totals[name][2] += m["n"]
        cells = " | ".join(f"{fmt(methods[n].get('wape'), pct=True)}" for n in METHODS)
        rows.append(
            f"| {entity.term} | {METHODS[run.method].label} | {cells} | "
            f"{fmt(info.get('interval_coverage'), pct=True)} |"
        )
    header = " | ".join(METHODS[n].label for n in METHODS)
    lines += [
        "## WAPE per term",
        "",
        f"| Term | Shown | {header} | 80% interval coverage |",
        "|---" * (len(METHODS) + 3) + "|",
        *rows,
        "",
        "## Aggregate",
        "",
        "| Method | Kind | MAE | WAPE | Days scored |",
        "|---|---|---|---|---|",
    ]
    for name, (abs_err, actual, n) in totals.items():
        if n:
            lines.append(
                f"| {METHODS[name].label} | {METHODS[name].kind} | {abs_err / n:.2f} | "
                f"{fmt(abs_err / actual if actual else None, pct=True)} | {n} |"
            )
    lines += [
        "",
        f"Exponential smoothing beat the same-day-last-week baseline for {beats} of {ready} terms "
        f"and had the lowest error overall (so it is the forecast shown) for {shown_candidate}.",
        "",
        "Interval coverage is measured honestly: interval widths are fitted on the older half of the "
        "back-test windows and checked on the newer half. With only a few windows per term it is a "
        "rough check, not a calibration guarantee.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--note", default="")
    args = parser.parse_args()
    with get_session_factory()() as db:
        text = build(db, args.note)
    if args.out:
        args.out.write_text(text)
    else:
        print(text)


if __name__ == "__main__":
    main()
