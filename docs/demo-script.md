# Demo script

A 10 to 15 minute walk-through following the plan's suggested demo scenario (Appendix B). It uses the synthetic demo data, so it runs the same way on any clean installation and contains no real people's posts.

## Setup (before the audience arrives)

```bash
cd backend
DEMO_PASSWORD='choose-a-password' python -m app.demo.seed --end 2026-10-17
```

On a deployment, run the same command inside the container (see [deployment.md](deployment.md#demo-data-on-a-deployment)). Use a fixed `--end` so the dates below match; with a different end date, every date shifts by the same amount.

The demo data covers 120 days (20 June to 17 October 2026) for four budget phones:

| Term | Story built into the data |
|---|---|
| Redmi Note 14 (product) | Grows steadily, with a one-day launch spike on 7 September |
| Poco X7 (competitor) | Delivery and customer-support complaints surge in the last 7 days (11 to 17 October) |
| Samsung Galaxy M35 (competitor) | Flat, with a weekend bump |
| Realme Narzo 70 (competitor) | Slowly declines |
| All | Nothing collected on 18 to 20 August, on purpose |

Sign in as `demo@marketpulse.local`. Run `python3 deploy/smoke.py <url> demo@marketpulse.local <password>` once to be sure everything answers.

## 1. A spike, checked against coverage

- Open **Overview**. Point out the trend cards: Poco X7 stands out with "rising negative" while the others are stable.
- Set the date range to 1 August to 30 September. On the daily mentions chart, show Redmi Note 14's one-day spike on 7 September.
- In the same view, show the shaded band on 18 to 20 August: those days were not collected, so the line breaks instead of dropping to zero.
- Open **Sources** and show the coverage panel: two uploads, records matched, and the 3 days not covered.

**Say:** "A spike only means something if we collected the days around it. The app shows what it didn't see."

## 2. Which topics drive sentiment

- Open **Sentiment** for Poco X7, last 30 days.
- Show sentiment over time turning negative in the last week, then the **By topic** chart: delivery and customer support carry the negative posts.
- Open the negative examples and read one or two aloud.

**Say:** "Topic tags come from keyword rules and the sentiment model is automatic, so we always show the posts it's based on."

## 3. Compare competitors, with the sample sizes

- Open **Compare**, last 30 days.
- Walk through the scorecards: mentions, share of voice, net sentiment with `n=` scored posts, and the coverage column.
- Point to the topic heat map: only Poco X7 has delivery and customer-support posts, and most of them are negative. "Where terms differ" lists the topics where one term is clearly better or worse than the rest, such as Redmi Note 14's battery and camera.
- Note that engagement per post says how many posts it comes from, and that blank cells mean fewer than 5 posts.

**Say:** "Every comparison carries how many records it rests on, so a big percentage from a handful of posts is easy to spot."

## 4. A forecast and its limits

- Open **Forecasts** for Redmi Note 14.
- Show the 80% range, then the **Back-test** table: exponential smoothing against last value, 7-day average and same day last week.
- Point out that on this data it only beats the 7-day average by about a point of WAPE (see [evaluation summary](evaluation/summary.md)).

**Say:** "This is a short-term attention estimate, not a sales forecast, and it can't see launches or outages coming."

## 5. An insight traced to its evidence

- Open **Insights** and press **Refresh**.
- Pick the Poco X7 card. Read the observation, the possible explanation and the caveat.
- Open **Evidence**: every number in the card appears in the facts list with its label, and the example posts are linked.
- If Claude-written insights are turned on, press **Write with Claude** and show that the numbers still match the evidence; cards that state anything unsupported are dropped before they're shown.

**Say:** "The model can phrase the card, but it can't choose or change the numbers."

## 6. Missing data shows a warning, not a made-up value

- On **Watchlists**, add a new competitor, "Nothing Phone 3".
- Back on **Overview**, its card says "Not enough data to call a trend" with low confidence.
- On **Forecasts**, select it and run a forecast: "Not enough reliable data to forecast Nothing Phone 3".
- Optionally, on **Explore** or Compare, download the daily totals (CSV) for August and show the `not_collected` rows for 18 to 20 August.
- Remove the term afterwards.

**Say:** "When the data can't support an answer, the app says so."

## Wrap-up

- Alerts: on **Watchlists**, open Alerts on the card and add "Negative share at or above 40%" for Poco X7. It fires on the next import.
- Privacy: a second account sees none of this workspace.
- Limits: see the [evaluation summary](evaluation/summary.md).
