"""Optional insight writing with Claude.

The model only sees the fact sheet (aggregates with IDs) and a few permitted example posts, and
must answer in a fixed JSON schema. Its drafts then go through the same validator as the
templates: a card that cites a missing fact or post, or states a number that none of its cited
facts supports, is rejected. If the call fails, is refused, or nothing passes, the caller falls
back to the template cards.
"""

import json
import logging

import anthropic
from pydantic import BaseModel, ValidationError

from app.insights.drafts import Draft
from app.insights.facts import FactSheet

logger = logging.getLogger(__name__)

PROMPT_VERSION = "ins-1"

SYSTEM = """You write short, careful insight cards for a brand-monitoring dashboard.

You get a fact sheet for one watchlist: for each tracked term, facts with an id, a label, a value and a unit (percent values are fractions, so 0.42 means 42%), plus a few example posts with ids.

Write up to 5 cards about the changes that matter most this week. Each card has:
- observation: one or two sentences stating a measurable change with its dates and comparison period.
- fact_ids: the ids of every fact the card relies on.
- example_record_ids: ids of example posts that illustrate it (may be empty).
- interpretation: a cautious possible explanation, worded as a possibility, never as fact.
- caveat: what limits confidence (coverage, sample size, sentiment model limits).
- suggested_investigation: one concrete next step in the dashboard (Explore, Sentiment, Compare or Forecasts pages).
- term_alias: the alias of the term the card is about, or an empty string for a card about the whole watchlist.

Rules:
- Every number you write must be the value of a fact you cite in fact_ids (percent facts may be written as whole percentages), or part of a date in the period. Do not compute new numbers such as differences or ratios, and do not round counts.
- Never invent causes, quotes, sources, coverage or confidence. Example posts may be paraphrased in the interpretation but not quoted as evidence of volume.
- If a term's data is thin (few collected days or scored posts), say so in the caveat.
- Prefer fewer, well-supported cards over many weak ones. If nothing changed, write one card saying so."""

SCHEMA = {
    "type": "object",
    "properties": {
        "cards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "term_alias": {"type": "string"},
                    "observation": {"type": "string"},
                    "fact_ids": {"type": "array", "items": {"type": "string"}},
                    "example_record_ids": {"type": "array", "items": {"type": "string"}},
                    "interpretation": {"type": "string"},
                    "caveat": {"type": "string"},
                    "suggested_investigation": {"type": "string"},
                },
                "required": ["term_alias", "observation", "fact_ids", "example_record_ids", "interpretation",
                             "caveat", "suggested_investigation"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["cards"],
    "additionalProperties": False,
}


class _Card(BaseModel):
    term_alias: str
    observation: str
    fact_ids: list[str]
    example_record_ids: list[str]
    interpretation: str
    caveat: str
    suggested_investigation: str


class _Cards(BaseModel):
    cards: list[_Card]


class InsightModelError(Exception):
    """The model call failed, was refused, or returned something unusable."""


def llm_drafts(sheet: FactSheet, client: anthropic.Anthropic, model: str) -> list[Draft]:
    try:
        response = client.beta.messages.create(
            model=model,
            max_tokens=16000,
            system=SYSTEM,
            messages=[{"role": "user", "content": json.dumps(sheet.as_prompt_data(), ensure_ascii=False)}],
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
            # On a safety decline the API re-runs the request on Anthropic's recommended fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.APIConnectionError as exc:
        raise InsightModelError("could not reach the Anthropic API") from exc
    except anthropic.RateLimitError as exc:
        raise InsightModelError("rate limited by the Anthropic API") from exc
    except anthropic.APIStatusError as exc:
        raise InsightModelError(f"Anthropic API error {exc.status_code}") from exc

    if response.stop_reason == "refusal":
        raise InsightModelError("the model declined the request")
    if response.stop_reason == "max_tokens":
        raise InsightModelError("the response was cut off")
    text = next((b.text for b in response.content if b.type == "text"), None)
    if text is None:
        raise InsightModelError("the response had no text")
    try:
        parsed = _Cards.model_validate_json(text)
    except ValidationError as exc:
        raise InsightModelError("the response didn't match the schema") from exc
    return [
        Draft(
            entity_alias=c.term_alias or None,
            observation=c.observation.strip(),
            fact_ids=c.fact_ids,
            interpretation=c.interpretation.strip(),
            caveat=c.caveat.strip(),
            suggested_action=c.suggested_investigation.strip(),
            example_ids=c.example_record_ids,
        )
        for c in parsed.cards
    ]
