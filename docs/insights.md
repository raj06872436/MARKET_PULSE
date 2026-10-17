# How insights work

Each insight card answers four questions: what changed, why it might have happened, how sure we are, and what to look at next. The rules below keep cards tied to the data.

## What a card contains

| Part | Rule |
|---|---|
| Observation | A measurable change with its dates and comparison period, for example "Mentions of Poco X7 rose from 71 to 120 (+69%) in the 7 days to Oct 17". |
| Possible explanation | Worded as a possibility, never as a fact, and labelled "Possible explanation" on screen. |
| Caveat | Collected days, sample size and sentiment model limits that weaken the claim. |
| Next step | A page and filter to check, such as the negative battery posts in Explore. |
| Evidence | The facts the card cites (label and value) and up to 3 example posts. |

Periods are the 7 days ending on the last collected day, compared with the 7 days before, in UTC.

## Where the numbers come from

`build_facts()` builds a fact sheet for one watchlist from stored aggregates: mentions and their change, collected days, share of voice, scored posts, positive and negative share (only with at least 5 scored posts), the most discussed and most negative topics (only with at least 5 posts), the trend score, code and confidence for the last day, and the 7-day forecast total when a forecast was made on that day. Each fact has an ID like `t2.negative_share`, a label, a value and a unit.

## Who writes the cards

**Templates** are the default and always available. They cover rising negative attention, one-day spikes, rising and falling mentions, sentiment shifts, a topic gap between two terms, and a line for terms with no notable change.

**Claude** writes cards when `INSIGHTS_LLM_ENABLED=true` and `ANTHROPIC_API_KEY` is set, and someone presses "Write with Claude". The model gets the fact sheet and the example posts, and must answer in a fixed JSON schema listing the fact and post IDs each card relies on. The prompt version is stored with each card (`model_version`, such as `claude-opus-5-5/ins-1`).

## The check every card passes

`validate()` rejects a card that:

- cites a fact ID or post ID that isn't in the fact sheet,
- states a number that isn't the value of a fact it cites (percent facts may be written as whole percentages, and parts of the period's dates are allowed),
- leaves a section empty or runs too long.

Rejected drafts are logged and counted on the page. If the model call fails, is declined, is cut off, doesn't match the schema, or no card passes, the page shows template cards and says why.

## What is sent to Anthropic

Only when Claude writing is turned on and requested: the watchlist name, the tracked terms, the fact sheet values and up to 3 example posts per term (text, date, sentiment and permitted link). Authors, other posts and credentials are never sent. With the setting off, nothing leaves the server.

## Known limits

- The number check catches invented or miscopied numbers, not a wrong reading of a correct number (for example, calling a 3-point change "sharp").
- Explanations are guesses from the topics and example posts; the data can't show cause.
- Facts follow the same coverage rules as the rest of the app, so a week with missing days gets a caveat, not a zero.
