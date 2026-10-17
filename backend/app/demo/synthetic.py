"""Deterministic synthetic posts for demos and tests. Clearly fake: every URL is on example.com.

Built-in stories, so trends and forecasts have something to find:
- Redmi Note 14 grows steadily, with a one-day launch spike 40 days before the end.
- Poco X7 gets a surge of delivery and support complaints in the last 7 days.
- Samsung Galaxy M35 is flat with a weekend bump.
- Realme Narzo 70 slowly declines.
- Nothing is collected for 3 days, 58-60 days before the end (a deliberate gap).
"""

import math
import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

TEMPLATES = {
    ("camera", "positive"): ["{b} camera is amazing for the price", "Night photos on the {b} came out so sharp",
                             "Loving the zoom on my {b}", "{b} selfie camera is excellent"],
    ("camera", "negative"): ["{b} camera is blurry indoors", "Photos from the {b} look washed out, disappointing"],
    ("battery", "positive"): ["{b} battery easily lasts two days", "Fast charging on the {b} is unreal",
                              "Battery backup on {b} zabardast hai"],
    ("battery", "negative"): ["{b} battery drains overnight", "{b} charging is so slow, terrible",
                              "Battery on the {b} is a disaster after the update"],
    ("display", "positive"): ["{b} display is super bright and smooth", "AMOLED screen on the {b} is gorgeous"],
    ("display", "negative"): ["{b} screen has a green tint, annoying"],
    ("performance", "positive"): ["{b} gaming is smooth, no lag at all", "{b} feels fast even with many apps open"],
    ("performance", "negative"): ["{b} heats up badly while gaming", "{b} lags constantly, very frustrating"],
    ("delivery", "positive"): ["{b} delivery came a day early, nice"],
    ("delivery", "negative"): ["{b} delivery delayed again, a week late", "My {b} order was cancelled without reason",
                               "{b} arrived with a damaged box, unacceptable"],
    ("customer_support", "positive"): ["{b} customer care resolved my issue quickly, impressed"],
    ("customer_support", "negative"): ["{b} customer support never replied, worst experience",
                                       "Service center kept my {b} for 3 weeks, horrible",
                                       "{b} refund still pending after 20 days"],
    ("price", "positive"): ["{b} is great value for money", "Got the {b} on sale, totally worth it"],
    ("price", "negative"): ["{b} is overpriced for what you get"],
    ("neutral", "neutral"): ["Is the {b} worth buying this month?", "{b} vs the rest, which one should I get?",
                             "Unboxing the {b} today", "{b} price in India announced", "Anyone using the {b} on Jio 5G?"],
}


@dataclass(frozen=True)
class Brand:
    term: str
    entity_type: str
    variants: tuple[str, ...]
    base: float
    growth: float  # relative change per day
    positive: float
    negative: float
    aspects: tuple[str, ...]


BRANDS = (
    Brand("Redmi Note 14", "product", ("#RedmiNote14", "RedmiNote14"), 14, 0.006, 0.55, 0.2,
          ("camera", "battery", "display", "performance", "price")),
    Brand("Poco X7", "competitor", ("#PocoX7",), 10, 0.0, 0.42, 0.3, ("performance", "battery", "delivery", "customer_support", "price")),
    Brand("Samsung Galaxy M35", "competitor", ("Galaxy M35",), 12, 0.0, 0.4, 0.3, ("display", "battery", "camera", "performance")),
    Brand("Realme Narzo 70", "competitor", ("Narzo 70",), 8, -0.006, 0.4, 0.3, ("battery", "performance", "price")),
)
GAP = range(58, 61)  # days before the end with no collection


def _poisson(rng: random.Random, lam: float) -> int:
    # Knuth for small lambda, normal approximation for large.
    if lam > 30:
        return max(0, round(rng.gauss(lam, math.sqrt(lam))))
    threshold, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= threshold:
            return k
        k += 1


def generate(end: date, days: int = 120, seed: int = 42) -> tuple[list[dict], list[dict]]:
    """Return (history, recent) rows for two CSV files that leave the deliberate gap between them."""
    rng = random.Random(seed)
    history, recent = [], []
    n = 0
    for back in range(days - 1, -1, -1):
        if back in GAP:
            continue
        day = end - timedelta(days=back)
        for brand in BRANDS:
            lam = brand.base * (1 + brand.growth) ** (days - back)
            if day.weekday() >= 5:
                lam *= 1.3 if brand.term == "Samsung Galaxy M35" else 1.1
            positive, negative, aspects = brand.positive, brand.negative, brand.aspects
            if brand.term == "Redmi Note 14" and back == 40:
                lam *= 5
            if brand.term == "Poco X7" and back < 7:
                lam *= 1.8
                positive, negative = 0.2, 0.6
                aspects = ("delivery", "customer_support", "customer_support", "performance")
            for _ in range(_poisson(rng, lam)):
                n += 1
                roll = rng.random()
                if roll < positive:
                    sentiment = "positive"
                elif roll < positive + negative:
                    sentiment = "negative"
                else:
                    sentiment = "neutral"
                key = ("neutral", "neutral") if sentiment == "neutral" else (rng.choice(aspects), sentiment)
                options = TEMPLATES.get(key) or TEMPLATES[("neutral", "neutral")]
                name = rng.choice((brand.term, *brand.variants)) if rng.random() < 0.3 else brand.term
                published = datetime.combine(day, time(rng.randint(6, 23), rng.randint(0, 59)), UTC)
                has_engagement = rng.random() < 0.75
                row = {
                    "source_record_id": f"syn-{n:06d}",
                    "published_at": published.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "text": rng.choice(options).format(b=name),
                    "url": f"https://example.com/synthetic/{n:06d}",
                    "language": "en",
                    "likes": _poisson(rng, 8 if sentiment != "neutral" else 3) if has_engagement else "",
                    "comments": _poisson(rng, 2) if has_engagement else "",
                    "shares": "",
                    "views": "",
                }
                (recent if back < GAP.start else history).append(row)
    return history, recent
