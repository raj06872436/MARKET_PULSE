# Forecast back-test

Forecast version `fc-1`. Each method forecasts daily mentions from rolling weekly origins, trained only on days before each origin and scored only on days that were collected. Lower is better.

Run on the synthetic demo data (`python -m app.demo.seed --end 2026-10-17`), so these numbers show the method works end to end, not how it will do on real conversations. Re-run on real data before relying on it.

## WAPE per term

| Term | Shown | Last value | 7-day average | Same day last week | Exponential smoothing | 80% interval coverage |
|---|---|---|---|---|---|---|
| Poco X7 | Exponential smoothing | 52.0% | 33.6% | 44.4% | 32.1% | 78.6% |
| Realme Narzo 70 | Exponential smoothing | 60.4% | 38.4% | 54.7% | 38.3% | 85.7% |
| Redmi Note 14 | Exponential smoothing | 24.8% | 23.0% | 27.7% | 21.7% | 64.3% |
| Samsung Galaxy M35 | 7-day average | 27.4% | 23.3% | 29.1% | 23.6% | 85.7% |

## Aggregate

| Method | Kind | MAE | WAPE | Days scored |
|---|---|---|---|---|
| Last value | baseline | 4.76 | 34.0% | 224 |
| 7-day average | baseline | 3.72 | 26.6% | 224 |
| Same day last week | baseline | 4.72 | 33.7% | 224 |
| Exponential smoothing | candidate | 3.60 | 25.7% | 224 |

Exponential smoothing beat the same-day-last-week baseline for 4 of 4 terms and had the lowest error overall (so it is the forecast shown) for 3.

Interval coverage is measured honestly: interval widths are fitted on the older half of the back-test windows and checked on the newer half. With only a few windows per term it is a rough check, not a calibration guarantee.
