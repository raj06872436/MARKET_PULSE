"""Tag posts with product aspects from a fixed taxonomy, with a sentiment per aspect.

Aspect sentiment comes from the clause that mentions the aspect, so "great camera but awful battery"
gives camera positive and battery negative. Bump ASPECT_VERSION when the taxonomy changes so
historical charts don't silently change meaning.
"""

import re

from app.ml.sentiment.base import SentimentModel
from app.ml.sentiment.preprocess import preprocess

ASPECT_VERSION = "asp-1"

TAXONOMY: dict[str, list[str]] = {
    "price": ["price", "priced", "pricey", "overpriced", "cheap", "expensive", "value for money", "worth", "budget",
              "cost", "paisa", "rupee", "rupees", "discount", "sale", "offer", "deal", "₹"],
    "battery": ["battery", "charging", "charge", "charger", "drain", "drains", "mah", "backup", "fast charging"],
    "camera": ["camera", "photo", "photos", "picture", "pictures", "zoom", "selfie", "night mode", "video", "lens", "focus"],
    "display": ["display", "screen", "amoled", "brightness", "bright", "120hz", "refresh rate", "tint", "panel"],
    "performance": ["lag", "lags", "laggy", "slow", "fast", "smooth", "performance", "gaming", "heat", "heats",
                    "heating", "overheats", "hang", "hangs", "freeze", "crash", "crashes", "fps", "chipset", "garam"],
    "build_quality": ["build", "plastic", "premium", "cracked", "crack", "durable", "sturdy", "creaks", "scratches",
                      "quality", "drop", "broke", "broken"],
    "software": ["update", "updates", "software", "bloatware", "ads", "android", "ui", "bug", "bugs", "os", "firmware", "app"],
    "delivery": ["delivery", "delivered", "shipping", "shipped", "courier", "package", "packaging", "box", "arrived",
                 "late", "order", "dispatch"],
    "customer_support": ["support", "customer care", "service center", "service centre", "helpline", "refund",
                         "replacement", "warranty", "return", "complaint", "staff"],
    "design": ["design", "colour", "color", "looks", "weight", "lightweight", "matte", "finish", "slim"],
    "connectivity": ["wifi", "network", "signal", "5g", "bluetooth", "hotspot", "gps", "sim"],
}

PATTERNS = {
    aspect: re.compile(r"(?<!\w)(?:" + "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True)) + r")(?!\w)")
    for aspect, terms in TAXONOMY.items()
}
CLAUSE_SPLIT = re.compile(r"\s*(?:[.;!?]+|,|\bbut\b|\bthough\b|\balthough\b|\bhowever\b|\bwhile\b|\bpar\b|\blekin\b)\s*")


def tag_aspects(texts: list[str], model: SentimentModel, overall: list[str]) -> list[list[dict]]:
    """Return, per text, a list of {"aspect", "sentiment"} items.

    Clause sentiment comes from `model`; a neutral clause falls back to the post's overall label.
    """
    clauses_per_text: list[list[tuple[str, set[str]]]] = []
    to_score: list[str] = []
    for text in texts:
        clauses = []
        for clause in CLAUSE_SPLIT.split(preprocess(text)):
            found = {aspect for aspect, pattern in PATTERNS.items() if pattern.search(clause)}
            if found:
                clauses.append((clause, found))
                to_score.append(clause)
        clauses_per_text.append(clauses)

    scored = iter(model.predict(to_score)) if to_score else iter(())
    results = []
    for clauses, post_label in zip(clauses_per_text, overall, strict=True):
        per_aspect: dict[str, str] = {}
        for _, aspects in clauses:
            label = next(scored).label
            if label == "neutral":
                label = post_label
            for aspect in aspects:
                # If an aspect appears in several clauses, a negative mention wins: complaints matter more.
                if per_aspect.get(aspect) != "negative":
                    per_aspect[aspect] = label
        results.append([{"aspect": a, "sentiment": s} for a, s in sorted(per_aspect.items())])
    return results
