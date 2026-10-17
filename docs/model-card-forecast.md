# Model card: mention forecast (`fc-1`)

## What it does

Estimates daily mentions of one tracked term for the next 1 to 14 days (7 by default), with an 80% range. It forecasts attention, not sales, sentiment or prices.

## Methods

| Method | Kind | How it forecasts |
|---|---|---|
| Last value | baseline | Repeats the last collected day |
| 7-day average | baseline | Repeats the average of the last 7 collected days |
| Same day last week | baseline | Repeats the same weekday from the last week (the reference baseline) |
| Exponential smoothing | candidate | Holt-Winters on log(1 + mentions): damped additive trend, additive weekly season once there are 4 weeks of data |

Code: `backend/app/ml/forecasting/`.

## How a forecast is chosen

1. **Data checks.** A forecast is only made with at least 56 days of history, at least 85% of the last 56 days collected, an average of at least 2 mentions a day with no more than half the days empty, and room for at least 4 back-test windows. Otherwise the run is stored as `insufficient_data` with the reasons, and the UI says "Not enough reliable data" instead of drawing a line.
2. **Rolling-origin back-test.** From up to 8 origins a week apart, each method is trained only on days before the origin and scored on the following days. Days that weren't collected are skipped, never treated as zero. MAE, RMSE and WAPE are reported per method, and MAE per horizon day.
3. **Selection.** The method with the lowest back-test WAPE is shown (MAE if all actuals were zero; ties go to the simpler method). Each run records whether exponential smoothing beat the same-day-last-week baseline, which the plan requires before the model is presented as useful.
4. **Interval.** For each horizon day, the 80th percentile of the shown method's absolute back-test errors, added either side of the forecast and floored at zero. Coverage is checked by fitting widths on the older half of the windows and testing on the newer half.

## Training and retraining

There is no stored model; each forecast is fitted on the term's full collected history at the time it runs. Forecasts are refreshed after every analysis run (after each sync or import), but only when a newer collected day exists, so the history of runs doubles as a record of past forecasts. Once forecast days are collected, the API returns the actual value next to each forecast point so drift can be seen.

## Evaluation

See [evaluation/forecast.md](evaluation/forecast.md). Those numbers come from synthetic demo data and only show that the pipeline works. Re-run `python -m app.ml.forecasting.report` on real data before relying on it.

## Limitations

- Daily mentions are counts of matched posts from the connected sources, so a source outage or a new connector changes the level. Coverage checks catch outages but not a source being added.
- One-off spikes (a launch, a viral post) can't be predicted from history and will fall outside the range.
- With 8 weekly windows the interval is estimated from about 8 errors per horizon day, so its coverage is rough.
- No external drivers (launch dates, sales events, ad spend) are used.
