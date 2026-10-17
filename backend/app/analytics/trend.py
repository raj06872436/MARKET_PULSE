"""Transparent 0-100 trend score (plan section 8.4).

Starter weights, not validated constants: 35% mention growth, 25% engagement growth, 20% sentiment
shift, 20% persistence. Components without enough data are dropped and the rest re-weighted, and
every component's raw inputs are kept so the score can be inspected.
"""

import math
from dataclasses import dataclass
from datetime import date

WEIGHTS = {"mention_growth": 0.35, "engagement_growth": 0.25, "sentiment_shift": 0.20, "persistence": 0.20}
WINDOW = 7
BASELINE_DAYS = 28
SMOOTHING = 5  # added to both 7-day counts so growth from near zero isn't explosive
MIN_SCORED = 5
MIN_ENGAGEMENT_RECORDS = 5
SCORE_VERSION = "trend-1"


@dataclass(frozen=True)
class DayPoint:
    date: date
    covered: bool
    complete: bool
    mentions: int
    engagement: int | None
    engagement_records: int
    positive: int
    negative: int
    scored: int


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def _growth(current: float, previous: float) -> float:
    return _clamp(50 + 25 * math.log2(current / previous))


def compute(days: list[DayPoint], idx: int) -> dict | None:
    """Score day `idx` from the 7 days ending there versus the 7 days before. None if there's no full prior window."""
    if idx < 2 * WINDOW - 1:
        return None
    cur = days[idx - WINDOW + 1 : idx + 1]
    prev = days[idx - 2 * WINDOW + 1 : idx - WINDOW + 1]
    c, p = sum(d.mentions for d in cur), sum(d.mentions for d in prev)
    components: dict[str, dict] = {}

    components["mention_growth"] = {
        "value": round(_growth(c + SMOOTHING, p + SMOOTHING), 1),
        "current_mentions": c,
        "previous_mentions": p,
    }

    ce, pe = sum(d.engagement_records for d in cur), sum(d.engagement_records for d in prev)
    if ce >= MIN_ENGAGEMENT_RECORDS and pe >= MIN_ENGAGEMENT_RECORDS:
        cur_avg = sum(d.engagement or 0 for d in cur) / ce
        prev_avg = sum(d.engagement or 0 for d in prev) / pe
        components["engagement_growth"] = {
            "value": round(_growth(cur_avg + 1, prev_avg + 1), 1),
            "current_per_post": round(cur_avg, 2),
            "previous_per_post": round(prev_avg, 2),
        }
    else:
        components["engagement_growth"] = {"value": None, "reason": "fewer than 5 posts with engagement data in a window"}

    cs, ps = sum(d.scored for d in cur), sum(d.scored for d in prev)
    if cs >= MIN_SCORED and ps >= MIN_SCORED:
        net_c = (sum(d.positive for d in cur) - sum(d.negative for d in cur)) / cs
        net_p = (sum(d.positive for d in prev) - sum(d.negative for d in prev)) / ps
        raw = 50 + 50 * (net_c - net_p)
        damping = min(cs, ps) / (min(cs, ps) + 20)
        components["sentiment_shift"] = {
            "value": round(_clamp(50 + (raw - 50) * damping), 1),
            "current_net": round(net_c, 3),
            "previous_net": round(net_p, 3),
            "damping": round(damping, 2),
        }
    else:
        components["sentiment_shift"] = {"value": None, "reason": "fewer than 5 scored posts in a window"}

    base = [d for d in days[max(0, idx - WINDOW - BASELINE_DAYS + 1) : idx - WINDOW + 1] if d.covered]
    if len(base) >= 14:
        baseline = sum(d.mentions for d in base) / len(base)
        above = sum(1 for d in cur if d.covered and d.mentions > max(baseline * 1.2, 1))
        peak = max(d.mentions for d in cur)
        components["persistence"] = {
            "value": round(above / WINDOW * 100, 1),
            "days_above_baseline": above,
            "baseline_daily_mentions": round(baseline, 2),
            "peak_day_mentions": peak,
        }
    else:
        components["persistence"] = {"value": None, "reason": "less than 14 days of history before this window"}

    available = {k: v["value"] for k, v in components.items() if v["value"] is not None}
    total_weight = sum(WEIGHTS[k] for k in available)
    score = sum(WEIGHTS[k] * v for k, v in available.items()) / total_weight
    for k, comp in components.items():
        comp["weight"] = round(WEIGHTS[k] / total_weight, 3) if k in available else 0

    window = cur + prev
    covered = sum(d.covered for d in window) / len(window)
    complete = all(d.complete for d in window if d.covered)
    if c >= 50 and covered == 1 and complete:
        confidence = "high"
    elif c >= 15 and covered >= 0.7:
        confidence = "medium"
    else:
        confidence = "low"

    persistence = components["persistence"]
    if c + p < 10:
        code = "insufficient_data"
    elif (
        components["mention_growth"]["value"] >= 65
        and persistence["value"] is not None
        and persistence["peak_day_mentions"] > 3 * max(persistence["baseline_daily_mentions"], 1)
        and persistence["peak_day_mentions"] >= 0.35 * c
    ):
        # One day carries over a third of the week: a spike, not a sustained trend.
        code = "one_day_spike"
    elif components["mention_growth"]["value"] >= 65 and (s := components["sentiment_shift"]["value"]) is not None and s <= 40:
        code = "rising_negative"
    elif components["mention_growth"]["value"] >= 65:
        code = "rising_mentions"
    elif components["mention_growth"]["value"] <= 35:
        code = "falling_mentions"
    elif (s := components["sentiment_shift"]["value"]) is not None and s <= 40:
        code = "sentiment_drop"
    elif s is not None and s >= 60:
        code = "sentiment_rise"
    else:
        code = "stable"

    return {
        "score": round(score, 1),
        "explanation_code": code,
        "components": components,
        "confidence": confidence,
        "coverage": round(covered, 2),
        "window": {"start": cur[0].date.isoformat(), "end": cur[-1].date.isoformat(),
                   "previous_start": prev[0].date.isoformat(), "previous_end": prev[-1].date.isoformat()},
        "version": SCORE_VERSION,
    }
