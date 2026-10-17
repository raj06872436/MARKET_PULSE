# Evaluation summary and limitations

Where each part of MarketPulse stands, how it was checked, and what that check does and doesn't show. Read this before using the app's output for decisions.

## At a glance

| Part | How it was checked | Result | How far to trust it |
|---|---|---|---|
| Mention counts and daily metrics | `python -m app.analytics.reconcile` recounts raw records for a date range and compares them with the stored daily metrics; tests hand-check small cases | Match on the demo data | High, for the sources you connected. Counts only cover what was collected |
| Sentiment (`lex-2`) | Held-out test split of 170 labelled posts ([report](sentiment.md)) | Macro F1 0.88, accuracy 0.88, calibration error 0.15 | Optimistic. Labels and lexicon were written by the same author (Claude), not people |
| Topic tags (aspects) | Keyword rules, unit tests on examples | Not measured against labels | Indicative. Good for routing you to posts, not for precise shares |
| Trend score (`trend-1`) | Unit tests on built-in stories (steady rise, one-day spike, complaint surge, flat, thin data) | Behaves as designed on those cases | Unvalidated against real outcomes. A ranking aid, not a measurement |
| Forecast (`fc-1`) | Rolling-origin back-test against three baselines ([report](forecast.md)) | WAPE 25.7% against 26.6% for the 7-day average, on synthetic data | Barely better than a simple average, and only on synthetic data |
| Insight cards | Every stated number is checked against the fact sheet; tests feed invented numbers, unknown facts, refusals and bad output | Unsupported cards are rejected | The numbers are right; the explanations are guesses |
| Access control | `tests/test_security.py` makes 25 calls as a second account ([security notes](../security.md)) | All refused | High for the API as tested |
| Accessibility | axe-core WCAG 2 A and AA checks on every page, keyboard check | Clean | Automated checks only; no screen-reader user testing yet |
| End to end | `tests/test_journey.py` (sign up to export through the API); `deploy/smoke.py` against the production image in CI | Pass | Covers the main path, not every screen |

## Sentiment

The lexicon was chosen over TF-IDF with logistic regression (test macro F1 0.39) on validation scores. With 102 training posts, the trained model had too little to learn from. A transformer model was set up but not evaluated, because the build environment couldn't download it.

The 0.88 is likely too high: the same author wrote the test posts, their labels and the word list, so the test set shares the lexicon's blind spots. Before relying on it, two people should re-label the 34 test posts independently, measure their agreement, and re-run `python -m app.ml.sentiment.evaluate`. Expect real posts to score lower, especially for sarcasm, mixed opinions and slang. See the [model card](../model-card-sentiment.md).

## Forecasts

Exponential smoothing beat the same-day-last-week baseline for all 4 demo terms and had the lowest error for 3 of them, but its overall margin over the 7-day average is under one point of WAPE. Its 80% range covered between 64% and 86% of actual days per term. All of this is on synthetic data generated from smooth patterns, so it shows the pipeline works, not that it forecasts real conversation well. Spikes from launches, sales or news can't be foreseen from history. See the [model card](../model-card-forecast.md).

The app already guards against weak forecasts: it shows the back-test beside every forecast and refuses to forecast when history is short or patchy.

## Trend score

The weights (mentions 35%, engagement 25%, sentiment 20%, persistence 20%) were set by judgement, not fitted. There is no labelled set of "real trends" to test against. Treat the score as a way to sort terms for a closer look, and read the components and posts on the card before acting.

## Data and coverage

- Only connected sources are counted. A source outage shows as "not collected", but adding a new source raises volumes without any change in the conversation.
- Engagement fields differ between sources and are often missing; comparisons show how many posts each figure comes from.
- Bluesky was tested with recorded responses only, because the build environment couldn't reach it. Test against the live API before relying on it.
- All demo and test data is synthetic. Nothing here has been checked against real brand conversations yet.

## What to do next

1. Collect 4 to 8 weeks of real posts for a real watchlist.
2. Have two people label at least 100 of them for sentiment and topics; re-run the sentiment evaluation and compare the lexicon with a transformer model.
3. Re-run the forecast back-test on the real data (`python -m app.ml.forecasting.report`).
4. Review 30 insight cards by hand for overstatement and missing caveats, as the plan's validation checklist asks.
5. Check the trend score against cases people agree were real trends.
