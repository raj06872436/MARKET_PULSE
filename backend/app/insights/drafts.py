"""Insight drafts, the deterministic template writer, and the validator every draft must pass."""

from dataclasses import dataclass, field

from app.insights.facts import Fact, FactSheet, TermFacts, allowed_numbers, numbers_in

TEMPLATE_VERSION = "template-1"
MAX_CARDS = 6


@dataclass
class Draft:
    entity_alias: str | None
    observation: str
    fact_ids: list[str]
    interpretation: str
    caveat: str
    suggested_action: str
    example_ids: list[str] = field(default_factory=list)


def pct(v: float) -> str:
    return f"{round(v * 100)}%"


def topic(name: str) -> str:
    return name.replace("_", " ")


def _caveat(t: TermFacts) -> tuple[str, list[str]]:
    """Coverage and confidence notes, with the facts they rely on."""
    notes, ids = [], []
    days, prev_days = t.value("collected_days"), t.value("collected_days_previous")
    if days is not None and prev_days is not None and (days < 7 or prev_days < 7):
        notes.append(f"Only {days} of 7 days were collected this week and {prev_days} of 7 the week before, so part of the change may be missing data.")
        ids += [f"{t.alias}.collected_days", f"{t.alias}.collected_days_previous"]
    confidence = t.value("trend_confidence")
    if confidence and confidence != "high":
        notes.append(f"Trend confidence is {confidence}.")
        ids.append(f"{t.alias}.trend_confidence")
    scored = t.value("scored")
    if scored is not None and scored < 30:
        notes.append(f"Sentiment rests on {scored} scored posts.")
        ids.append(f"{t.alias}.scored")
    if not notes:
        notes.append("Counts come from the connected sources only, and sentiment labels come from an automatic model that misreads sarcasm and mixed posts.")
    return " ".join(notes), ids


def _examples_for(sheet: FactSheet, alias: str, sentiment: str | None = None) -> list[str]:
    return [e.id for e in sheet.examples if e.entity_alias == alias and (sentiment is None or e.sentiment == sentiment)][:2]


def template_drafts(sheet: FactSheet) -> list[Draft]:
    """Rule-based cards from the fact sheet. Always available; used whenever no model output passes validation."""
    drafts: list[Draft] = []
    period = f"in the 7 days to {sheet.end:%b} {sheet.end.day}"
    for t in sheet.terms:
        code = t.value("trend_code")
        a = t.alias
        cur, prev = t.value("mentions"), t.value("mentions_previous")
        change = t.value("mentions_change")
        neg, neg_prev = t.value("negative_share"), t.value("negative_share_previous")
        worst, worst_share, worst_n = t.value("top_negative_topic"), t.value("top_negative_topic_share"), t.value("top_negative_topic_posts")
        caveat, caveat_ids = _caveat(t)
        mention_ids = [f"{a}.mentions", f"{a}.mentions_previous"] + ([f"{a}.mentions_change"] if change is not None else [])
        moved = f"from {prev} to {cur}" + (f" ({'+' if change > 0 else ''}{pct(change)})" if change is not None else "")

        if code == "rising_negative" and neg is not None:
            sentiment = f"the negative share {'went from ' + pct(neg_prev) + ' to ' if neg_prev is not None else 'was '}{pct(neg)}"
            topic_ids = [f"{a}.top_negative_topic", f"{a}.top_negative_topic_share", f"{a}.top_negative_topic_posts"] if worst else []
            drafts.append(Draft(
                a, f"Mentions of {t.term} rose {moved} {period}, and {sentiment}.",
                mention_ids + [f"{a}.negative_share"] + ([f"{a}.negative_share_previous"] if neg_prev is not None else [])
                + [f"{a}.trend_code"] + topic_ids + caveat_ids,
                (f"Possibly a product or service problem drawing complaints: {pct(worst_share)} of the {worst_n} {topic(worst)} posts were negative."
                 if worst else "Possibly a product or service problem drawing complaints."),
                caveat,
                f"Read the negative {topic(worst) + ' ' if worst else ''}posts about {t.term} in Explore to see what people describe.",
                _examples_for(sheet, a, "negative"),
            ))
        elif code == "one_day_spike":
            drafts.append(Draft(
                a, f"Mentions of {t.term} went {moved} {period}, but most of the rise came on a single day.",
                mention_ids + [f"{a}.trend_code"] + caveat_ids,
                "Possibly a single event such as an announcement, a sale or one widely shared post, rather than lasting interest.",
                caveat, f"Open the spike day for {t.term} in Explore and check whether one post or event explains it.",
                _examples_for(sheet, a),
            ))
        elif code in ("rising_mentions", "falling_mentions"):
            verb = "rose" if code == "rising_mentions" else "fell"
            topic_ids = [f"{a}.top_topic", f"{a}.top_topic_posts"] if t.value("top_topic") else []
            drafts.append(Draft(
                a, f"Mentions of {t.term} {verb} {moved} {period}.",
                mention_ids + [f"{a}.trend_code"] + topic_ids + caveat_ids,
                (f"Possibly driven by talk about {topic(t.value('top_topic'))}, the most discussed topic ({t.value('top_topic_posts')} posts)."
                 if topic_ids else "The data doesn't point to a single cause."),
                caveat, f"Compare {t.term} with the other terms on the Compare page for the same dates.",
                _examples_for(sheet, a),
            ))
        elif code in ("sentiment_drop", "sentiment_rise") and neg is not None and neg_prev is not None:
            direction = "worse" if code == "sentiment_drop" else "better"
            drafts.append(Draft(
                a, f"Sentiment about {t.term} got {direction} {period}: the negative share went from {pct(neg_prev)} to {pct(neg)} while mentions stayed near {cur}.",
                [f"{a}.negative_share", f"{a}.negative_share_previous", f"{a}.mentions", f"{a}.trend_code"] + caveat_ids,
                (f"Possibly linked to {topic(worst)}, where {pct(worst_share)} of posts were negative." if worst
                 else "The data doesn't point to a single topic."),
                caveat, f"Open the Sentiment page for {t.term} and look at the topic breakdown.",
                _examples_for(sheet, a, "negative" if code == "sentiment_drop" else "positive"),
            ))

    # Topic comparison: the single largest negative-share gap between terms on a shared topic.
    best = None
    for t in sheet.terms:
        if not t.value("top_negative_topic"):
            continue
        for other in sheet.terms:
            if other is t or other.value("top_negative_topic") != t.value("top_negative_topic"):
                continue
            gap = t.value("top_negative_topic_share") - other.value("top_negative_topic_share")
            if gap >= 0.2 and (best is None or gap > best[2]):
                best = (t, other, gap)
    if best:
        t, other, _ = best
        name = topic(t.value("top_negative_topic"))
        drafts.append(Draft(
            t.alias,
            f"{pct(t.value('top_negative_topic_share'))} of {t.term}'s {name} posts were negative {period}, against "
            f"{pct(other.value('top_negative_topic_share'))} for {other.term}.",
            [f"{t.alias}.top_negative_topic", f"{t.alias}.top_negative_topic_share", f"{t.alias}.top_negative_topic_posts",
             f"{other.alias}.top_negative_topic", f"{other.alias}.top_negative_topic_share", f"{other.alias}.top_negative_topic_posts"],
            f"Possibly a real difference in {name} between the two, or a difference in who is posting.",
            f"Based on {t.value('top_negative_topic_posts')} and {other.value('top_negative_topic_posts')} posts.",
            f"Filter Explore to {name} posts for both terms and read them side by side.",
            _examples_for(sheet, t.alias, "negative"),
        ))

    # Terms with nothing notable still get one line, so a quiet term isn't mistaken for a missing one.
    covered = {d.entity_alias for d in drafts}
    quiet = [t for t in sheet.terms if t.alias not in covered and t.value("mentions") is not None]
    if quiet:
        parts = [f"{t.term} ({t.value('mentions')}{' mentions' if i == 0 else ''})" for i, t in enumerate(quiet)]
        names = parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} and {parts[-1]}"
        drafts.append(Draft(
            None, f"No notable change for {names} {period}.",
            [f"{t.alias}.mentions" for t in quiet] + [f"{t.alias}.trend_code" for t in quiet if t.value("trend_code")],
            "Mentions and sentiment stayed close to the week before." if any(t.value("trend_code") for t in quiet)
            else "There isn't enough history yet to compare with the week before.",
            "A quiet week can also mean a source stopped collecting; check Sources if this is unexpected.",
            "Check back after the next sync.",
        ))
    return drafts[:MAX_CARDS]


def validate(draft: Draft, sheet: FactSheet) -> list[str]:
    """Reasons to reject a draft. Empty means it may be shown."""
    facts = sheet.all_facts()
    problems = []
    if draft.entity_alias is not None and sheet.term(draft.entity_alias) is None:
        problems.append(f"unknown term alias {draft.entity_alias!r}")
    if not draft.fact_ids:
        problems.append("cites no facts")
    unknown = [f for f in draft.fact_ids if f not in facts]
    if unknown:
        problems.append(f"cites facts that don't exist: {', '.join(unknown[:5])}")
    known_examples = {e.id for e in sheet.examples}
    if bad := [e for e in draft.example_ids if e not in known_examples]:
        problems.append(f"cites posts that weren't provided: {', '.join(bad[:3])}")
    for name, text in (("observation", draft.observation), ("interpretation", draft.interpretation),
                       ("caveat", draft.caveat), ("suggested action", draft.suggested_action)):
        if not text or not text.strip():
            problems.append(f"empty {name}")
        elif len(text) > 600:
            problems.append(f"{name} is too long")
    cited: list[Fact] = [facts[f] for f in draft.fact_ids if f in facts]
    allowed = allowed_numbers(sheet, cited, [t.term for t in sheet.terms])
    for name, text in (("observation", draft.observation), ("interpretation", draft.interpretation),
                       ("caveat", draft.caveat), ("suggested action", draft.suggested_action)):
        stray = [n for n in numbers_in(text or "") if n not in allowed]
        if stray:
            problems.append(f"{name} states numbers no cited fact supports: {', '.join(f'{n:g}' for n in stray[:5])}")
    return problems
