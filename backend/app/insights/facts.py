"""The validated numbers an insight may use.

Every insight, whether written by the template or by a language model, must cite facts from this
set, and every number it states must come from a fact it cites. Facts are computed from stored
records and aggregates for one watchlist and a 7-day window compared with the 7 days before.
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.evidence import day_bounds
from app.analytics.explore import compare
from app.db.models import ForecastPoint, NlpResult, RecordMatch, SocialRecord, TrendSignal, Watchlist
from app.ml.forecasting.service import latest_run
from app.ml.sentiment.base import SentimentModel

WINDOW = 7
MIN_SCORED = 5
MIN_ASPECT = 5
MAX_EXAMPLES_PER_TERM = 3


@dataclass(frozen=True)
class Fact:
    id: str
    label: str
    value: float | int | str | None
    unit: str = ""  # "", "percent" (stored as 0-1), "score", "posts", "days"

    def as_dict(self) -> dict:
        return {"id": self.id, "label": self.label, "value": self.value, "unit": self.unit}


@dataclass(frozen=True)
class Example:
    id: str
    entity_alias: str
    published_at: str
    sentiment: str | None
    text: str
    url: str | None


@dataclass
class TermFacts:
    alias: str
    entity_id: str
    term: str
    entity_type: str
    facts: dict[str, Fact] = field(default_factory=dict)

    def get(self, name: str) -> Fact | None:
        return self.facts.get(f"{self.alias}.{name}")

    def value(self, name: str):
        f = self.get(name)
        return f.value if f else None


@dataclass
class FactSheet:
    watchlist_id: str
    watchlist_name: str
    start: date
    end: date
    previous_start: date
    previous_end: date
    terms: list[TermFacts]
    examples: list[Example]

    def all_facts(self) -> dict[str, Fact]:
        return {fid: f for t in self.terms for fid, f in t.facts.items()}

    def term(self, alias: str) -> TermFacts | None:
        return next((t for t in self.terms if t.alias == alias), None)

    def as_prompt_data(self) -> dict:
        return {
            "watchlist": self.watchlist_name,
            "period": {"start": self.start.isoformat(), "end": self.end.isoformat(),
                       "previous_start": self.previous_start.isoformat(), "previous_end": self.previous_end.isoformat(),
                       "timezone": "UTC"},
            "terms": [
                {"alias": t.alias, "term": t.term, "type": t.entity_type, "facts": [f.as_dict() for f in t.facts.values()]}
                for t in self.terms
            ],
            "examples": [e.__dict__ for e in self.examples],
        }


def _add(t: TermFacts, name: str, label: str, value, unit: str = "") -> None:
    if value is None:
        return
    fid = f"{t.alias}.{name}"
    t.facts[fid] = Fact(fid, label, value, unit)


def build_facts(db: Session, watchlist: Watchlist, end: date, model: SentimentModel) -> FactSheet:
    start = end - timedelta(days=WINDOW - 1)
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=WINDOW - 1)
    current = {c.entity_id: c for c in compare(db, watchlist, start, end, model).scorecards}
    previous = {c.entity_id: c for c in compare(db, watchlist, prev_start, prev_end, model).scorecards}

    terms: list[TermFacts] = []
    for i, entity in enumerate(watchlist.entities, start=1):
        t = TermFacts(alias=f"t{i}", entity_id=str(entity.id), term=entity.term, entity_type=entity.entity_type)
        cur, prev = current[entity.id], previous[entity.id]
        _add(t, "mentions", f"Mentions of {entity.term}, {start} to {end}", cur.mentions, "posts")
        _add(t, "mentions_previous", f"Mentions of {entity.term}, {prev_start} to {prev_end}", prev.mentions, "posts")
        if prev.mentions:
            _add(t, "mentions_change", "Change in mentions versus the previous 7 days",
                 round((cur.mentions - prev.mentions) / prev.mentions, 4), "percent")
        _add(t, "collected_days", f"Days collected, {start} to {end} (of {WINDOW})", cur.collected_days, "days")
        _add(t, "collected_days_previous", f"Days collected, {prev_start} to {prev_end} (of {WINDOW})", prev.collected_days, "days")
        _add(t, "share_of_voice", "Share of the watchlist's mentions", cur.share_of_voice, "percent")
        _add(t, "scored", "Posts with a sentiment label", cur.scored, "posts")
        if cur.scored >= MIN_SCORED:
            _add(t, "negative_share", "Share of scored posts that were negative", cur.negative_share, "percent")
            _add(t, "positive_share", "Share of scored posts that were positive", cur.positive_share, "percent")
        if prev.scored >= MIN_SCORED:
            _add(t, "negative_share_previous", "Share of scored posts that were negative, previous 7 days",
                 prev.negative_share, "percent")
        aspects = [a for a in cur.aspects if a.mentions >= MIN_ASPECT]
        if aspects:
            worst = max(aspects, key=lambda a: (a.negative_share, a.mentions))
            _add(t, "top_negative_topic", "Topic with the highest share of negative posts", worst.aspect)
            _add(t, "top_negative_topic_share", f"Share of {worst.aspect.replace('_', ' ')} posts that were negative",
                 worst.negative_share, "percent")
            _add(t, "top_negative_topic_posts", f"Posts about {worst.aspect.replace('_', ' ')}", worst.mentions, "posts")
            busiest = aspects[0]
            _add(t, "top_topic", "Most discussed topic", busiest.aspect)
            _add(t, "top_topic_posts", f"Posts about {busiest.aspect.replace('_', ' ')}", busiest.mentions, "posts")

        signal = db.scalar(select(TrendSignal).where(TrendSignal.tracked_entity_id == entity.id, TrendSignal.date == end))
        if signal:
            _add(t, "trend_score", "Trend score (0 to 100, 50 means no change)", round(signal.score, 1), "score")
            _add(t, "trend_code", "Trend explanation code", signal.explanation_code)
            _add(t, "trend_confidence", "Trend confidence", (signal.components_json or {}).get("confidence"))

        run = latest_run(db, entity.id)
        if run and run.status == "ready" and run.training_end == end:
            points = db.scalars(select(ForecastPoint).where(ForecastPoint.forecast_run_id == run.id)).all()
            _add(t, "forecast_next_7_days", "Estimated mentions over the next 7 days",
                 round(sum(p.predicted_value for p in points[:WINDOW])), "posts")
        terms.append(t)

    return FactSheet(
        watchlist_id=str(watchlist.id), watchlist_name=watchlist.name, start=start, end=end,
        previous_start=prev_start, previous_end=prev_end, terms=terms,
        examples=_examples(db, terms, start, end, model),
    )


def _examples(db: Session, terms: list[TermFacts], start: date, end: date, model: SentimentModel) -> list[Example]:
    """A few confident, unflagged posts per term, negative first, near-duplicates removed."""
    from app.analytics.evidence import text_key

    lo, hi = day_bounds(start, end)
    out: list[Example] = []
    for t in terms:
        rows = db.execute(
            select(SocialRecord, NlpResult)
            .join(RecordMatch, RecordMatch.record_id == SocialRecord.id)
            .join(NlpResult, (NlpResult.record_id == SocialRecord.id) & (NlpResult.model_name == model.name)
                  & (NlpResult.model_version == model.version))
            .where(RecordMatch.tracked_entity_id == uuid.UUID(t.entity_id), SocialRecord.published_at >= lo,
                   SocialRecord.published_at < hi, SocialRecord.text_reference.is_not(None))
        ).all()
        rows = [(r, n) for r, n in rows if not (n.flags_json or [])]
        order = {"negative": 0, "positive": 1, "neutral": 2}
        rows.sort(key=lambda rn: (order.get(rn[1].sentiment or "", 3), -(rn[1].confidence or 0), -rn[0].published_at.timestamp()))
        seen: set[str] = set()
        for r, n in rows:
            key = text_key(r.text_reference)
            if key in seen:
                continue
            seen.add(key)
            out.append(Example(id=str(r.id), entity_alias=t.alias, published_at=r.published_at.date().isoformat(),
                               sentiment=n.sentiment, text=(r.text_reference or "")[:280], url=r.permitted_url))
            if sum(1 for e in out if e.entity_alias == t.alias) >= MAX_EXAMPLES_PER_TERM:
                break
    return out


# --- number checking -----------------------------------------------------------------------------------------

NUMBER = re.compile(r"(?<![\w.])[-+]?\d+(?:,\d{3})*(?:\.\d+)?")


def numbers_in(text: str) -> list[float]:
    return [float(m.group().replace(",", "").lstrip("+")) for m in NUMBER.finditer(text)]


def allowed_numbers(sheet: FactSheet, cited: list[Fact], term_names: list[str]) -> set[float]:
    """Numbers a card may state: values of the facts it cites (in every reasonable rounding and as
    percentages), the period's dates, the window length, and numbers that are part of term names."""
    allowed: set[float] = {float(WINDOW), 100.0}
    for f in cited:
        if isinstance(f.value, bool) or not isinstance(f.value, (int, float)):
            continue
        v = float(f.value)
        candidates = [v, abs(v)]
        if f.unit == "percent":
            candidates += [v * 100, abs(v) * 100]
        for c in candidates:
            allowed.update({round(c), round(c, 1), round(c, 2), float(int(c))})
    for d in (sheet.start, sheet.end, sheet.previous_start, sheet.previous_end):
        allowed.update({float(d.day), float(d.month), float(d.year)})
    for name in term_names:
        allowed.update(numbers_in(name))
        allowed.update(float(n) for n in re.findall(r"\d+", name))
    return allowed
