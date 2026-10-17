"""Generate and store insight cards for a watchlist."""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date

import anthropic
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import DailyMetric, InsightCard, Watchlist
from app.insights.drafts import TEMPLATE_VERSION, Draft, template_drafts, validate
from app.insights.facts import FactSheet, build_facts
from app.insights.llm import PROMPT_VERSION, InsightModelError, llm_drafts
from app.ml.sentiment.base import SentimentModel

logger = logging.getLogger(__name__)


@dataclass
class Generation:
    cards: list[InsightCard]
    generator: str  # "llm" or "template"
    llm_status: str  # "not_configured", "not_requested", "used", "failed: ..." or "all rejected"
    rejected: list[dict] = field(default_factory=list)


def last_collected_day(db: Session, watchlist: Watchlist) -> date | None:
    ids = [e.id for e in watchlist.entities]
    if not ids:
        return None
    return db.scalar(select(func.max(DailyMetric.date)).where(DailyMetric.tracked_entity_id.in_(ids)))


def llm_available(settings: Settings) -> bool:
    return settings.insights_llm_enabled and bool(settings.anthropic_api_key)


def _store(db: Session, watchlist: Watchlist, sheet: FactSheet, drafts: list[Draft], generator: str, version: str) -> list[InsightCard]:
    facts = sheet.all_facts()
    examples = {e.id: e for e in sheet.examples}
    db.execute(delete(InsightCard).where(InsightCard.watchlist_id == watchlist.id, InsightCard.period_end == sheet.end))
    cards = []
    for d in drafts:
        term = sheet.term(d.entity_alias) if d.entity_alias else None
        card = InsightCard(
            workspace_id=watchlist.workspace_id,
            watchlist_id=watchlist.id,
            entity_id=uuid.UUID(term.entity_id) if term else None,
            period_start=sheet.start,
            period_end=sheet.end,
            claim=d.observation,
            interpretation=d.interpretation,
            caveat=d.caveat,
            suggested_action=d.suggested_action,
            generator=generator,
            model_version=version,
            evidence_json={
                "facts": [facts[f].as_dict() for f in dict.fromkeys(d.fact_ids)],
                "examples": [examples[e].__dict__ for e in dict.fromkeys(d.example_ids) if e in examples],
                "comparison": {"start": sheet.previous_start.isoformat(), "end": sheet.previous_end.isoformat()},
            },
        )
        db.add(card)
        cards.append(card)
    db.commit()
    return cards


def generate(
    db: Session,
    watchlist: Watchlist,
    model: SentimentModel,
    settings: Settings,
    end: date | None = None,
    use_llm: bool = True,
    client: anthropic.Anthropic | None = None,
) -> Generation:
    end = end or last_collected_day(db, watchlist)
    if end is None:
        return Generation([], "template", "not_requested")
    sheet = build_facts(db, watchlist, end, model)

    rejected: list[dict] = []
    if not use_llm:
        status = "not_requested"
    elif client is None and not llm_available(settings):
        status = "not_configured"
    else:
        client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key)
        try:
            drafts = llm_drafts(sheet, client, settings.insights_model)
            passed = []
            for d in drafts:
                problems = validate(d, sheet)
                if problems:
                    rejected.append({"observation": d.observation[:200], "problems": problems})
                else:
                    passed.append(d)
            if rejected:
                logger.warning("Rejected %d model-written insight(s): %s", len(rejected), rejected)
            if passed:
                cards = _store(db, watchlist, sheet, passed, "llm", f"{settings.insights_model}/{PROMPT_VERSION}")
                return Generation(cards, "llm", "used", rejected)
            status = "all rejected"
        except InsightModelError as exc:
            logger.warning("Insight model failed, using templates: %s", exc)
            status = f"failed: {exc}"

    drafts = template_drafts(sheet)
    for d in drafts:
        # Templates should always pass; if one doesn't, that's a bug worth seeing in logs, not on screen.
        if problems := validate(d, sheet):
            logger.error("Template insight failed validation: %s %s", d.observation, problems)
    drafts = [d for d in drafts if not validate(d, sheet)]
    cards = _store(db, watchlist, sheet, drafts, "template", TEMPLATE_VERSION)
    return Generation(cards, "template", status, rejected)
