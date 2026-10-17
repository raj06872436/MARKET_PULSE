# Architecture

MarketPulse is a modular monolith: one React frontend, one FastAPI backend, one PostgreSQL database and background jobs. Modules have clear boundaries so they can be split out later if scale requires it.

## Request flow

```
React (Vite) --/api--> FastAPI --> PostgreSQL
                          |
                          +--> jobs (APScheduler first, Celery + Redis later)
                                  |
                                  +--> connectors --> ingestion --> NLP --> daily_metrics --> trends / forecasts --> insight_cards
```

Dashboards read precomputed `daily_metrics`, `trend_signals` and `forecast_points`, not raw records.

## Tables

| Area | Tables |
| --- | --- |
| Accounts | `users`, `user_sessions`, `workspaces`, `audit_events` |
| Monitoring setup | `watchlists`, `tracked_entities`, `alerts`, `alert_events` |
| Ingestion | `source_connections`, `ingestion_runs`, `social_records`, `record_matches` |
| Analytics | `nlp_results`, `daily_metrics`, `trend_signals`, `forecast_runs`, `forecast_points`, `insight_cards` |

Rules applied in the schema:

- UUID primary keys, plus indexes on date, source and tracked entity.
- Unique constraints stop duplicate source records (`source`, `source_record_id`), duplicate daily aggregates (`date`, `tracked_entity_id`, `source`) and duplicate terms within a watchlist (`watchlist_id`, `normalized_term`).
- Every NLP output stores `model_name`, `model_version` and `preprocessing_version`.
- Engagement and coverage fields are nullable. Null means "not available", not zero.
- `source_connections.credential_ref` points at a secret and never holds one.

## Decisions so far

- **Accounts own workspaces.** Every data endpoint checks that the workspace behind the requested watchlist, term, alert or forecast belongs to the signed-in user, and answers 404 otherwise. Uploaded files belong to one workspace (`social_records.scope` and `workspace_id`) and only match that workspace's terms; posts from shared sources such as Bluesky are visible to any workspace whose terms they mention. Details in [security.md](security.md).
- **Tests run on SQLite** for speed. CI also applies the migrations to a real PostgreSQL and runs `alembic check`.
- **Bluesky is the first connector** because the plan rates it the most accessible. It uses `app.bsky.feed.searchPosts` on the public API and can sign in with an app password if unauthenticated search is refused. Each new connector implements `SourceConnector` in `app/connectors/base.py` and is registered in `app/connectors/registry.py`.
- **Syncing requires a recorded terms review.** A source can't be enabled until someone confirms they checked its terms; the date and notes are stored in `source_connections`.

## Ingestion

```
CSV upload ─┐
            ├─> NormalizedRecord ─> dedupe on (source, source_record_id) ─> social_records
connector ──┘                                                            └─> record_matches (whole-word match on terms and variants of active watchlists)
```

- Every import or sync is an `ingestion_runs` row: `queued → running → succeeded | partial | failed`, with fetched, new, duplicate, rejected and matched counts.
- `partial` means data arrived but coverage is incomplete: rows were rejected, or a query hit the page or query limit. `coverage_json` says which.
- A connector failure stores the error code and a sanitized message and keeps every record that arrived before it. Source health then shows **Failed** rather than a quiet zero.
- Incremental syncs ask for posts since the last successful run, minus one hour of overlap. Failed runs don't move that window, and dedupe absorbs the overlap.
- Manual syncs run as FastAPI background tasks. The optional APScheduler job (`SCHEDULER_ENABLED`) syncs every enabled source on an interval. Move to Celery + Redis if retries or concurrency need it.
- CSV sources are named `csv:<dataset>`, so identical IDs in two datasets stay separate.
- Adding a term re-matches stored records in the background, so a new term picks up older posts too.

## Analytics pipeline

`app/analytics/pipeline.py:run_analysis` runs after every sync, CSV import and term change, and from `POST /api/analysis/run`:

1. **Re-match** every stored record against the active terms.
2. **Score sentiment** for records without a result from the active model version, and tag aspects (`app/ml/topics/aspects.py`). Aspects are scored per clause, so "great camera but the battery dies fast" is positive for camera and negative for battery.
3. **Rebuild `daily_metrics`** for every UTC day a source covered. A CSV covers the span of its dates; an API sync covers its requested window. A covered day with no posts gets a row with 0 mentions. A day no source covered gets no row, and the API returns it as `mentions: null` with `collection: "missing"`, which the charts shade as "not collected".
4. **Rebuild `trend_signals`** for each entity and day.
5. **Refresh forecasts** for terms whose data has a newer collected day than their last forecast (see [the forecast model card](model-card-forecast.md)).

Rebuilding from stored records each time keeps the numbers reproducible; `python -m app.analytics.reconcile` checks them against raw counts.

## Trend score

Version `trend-1`, in `app/analytics/trend.py`. It compares the last 7 days with the 7 before and scores 0 to 100, where 50 means no change.

| Component | Weight | What it measures |
|---|---|---|
| Mention growth | 35% | Change in mentions, damped for small counts |
| Engagement growth | 25% | Change in likes, replies and reposts, where the source provides them |
| Sentiment shift | 20% | Change in net sentiment |
| Persistence | 20% | Share of the last 7 days that were more than 20% above the entity's usual daily level before the window, so a one-day spike counts less than a steady rise |

A component without data (no engagement fields, too few scored posts) is dropped and the other weights are rescaled; the card says which. Confidence is **high** with at least 50 mentions this week and both weeks fully and completely collected, **medium** with at least 15 mentions and 70% of the days collected, and **low** otherwise.

Each signal has one explanation code: `insufficient_data`, `one_day_spike`, `rising_negative`, `rising_mentions`, `falling_mentions`, `sentiment_drop`, `sentiment_rise` or `stable`. The trend card shows the score, the code in words, the component table, sentiment split, most discussed aspects, frequent phrases and up to five example posts with links.

Frequent phrases are unreviewed n-grams and are labelled as such. Topic clustering is left out until there is enough real data to judge it.

## Forecasts

`app/ml/forecasting/` holds the methods (`models.py`), the rolling-origin back-test (`backtest.py`) and the service that checks the data, picks the method with the lowest back-test WAPE, fits it on all history and stores a `forecast_runs` row with `forecast_points`. A run that fails a data check is stored with `status = insufficient_data` and its reasons, and has no points. `POST /api/forecasts` runs one on demand; `GET /api/forecasts/{id}` returns it with the last 56 days of history and, once forecast days are collected, the actual values beside the forecast.

## Dashboard

| Page | Endpoint(s) | Answers |
|---|---|---|
| Overview | `/api/trends`, `/api/metrics/series` | What changed in the last week? |
| Explore | `/api/records`, `/api/metrics/series` | What evidence is behind a number? |
| Sentiment | `/api/entities/{id}/sentiment`, `/api/metrics/series` | What are people responding to? |
| Compare | `/api/compare`, `/api/metrics/series` | Where does our brand differ? |
| Forecasts | `/api/forecasts` | How much should I trust this estimate? |
| Insights | `/api/insights`, `/api/insights/generate` | What should I look at first? |

Filters shared by every page live in the URL (`wl`, `range`, `from`, `to`, `src`), and the navigation carries them from page to page. Preset ranges end on the last collected day from `/api/watchlists/{id}/data-range`, not today, and a banner says so when that day is more than two days old. All dates are UTC days.

Counting rules the pages share: a post that names two terms counts once for each term on Compare and once overall in Explore; topic sentiment is per clause; cells and periods with fewer than 5 scored posts are left blank rather than shown as a percentage of almost nothing.

## Insights, alerts and export

Insight cards are built from a fact sheet (`app/insights/facts.py`): numbered facts per term, such as `t1.mentions` or `t2.negative_share`, for the last 7 collected days and the 7 before, plus a few example posts. Templates (`drafts.py`) always produce cards. When `INSIGHTS_LLM_ENABLED` is set with an API key, Claude writes them instead from the same fact sheet (`llm.py`), and `validate()` drops any card that cites a fact or post that doesn't exist or states a number none of its cited facts support. If the call fails, is declined, or nothing passes, the templates are used. Cards are stored in `insight_cards` with the facts and posts they cite, and regenerating a period replaces its cards. Details: [insights.md](insights.md).

Alerts (`app/analytics/alerts.py`) are checked at the end of every analysis run, on each term's latest collected day. Weekly rules need at least 6 of 7 days collected in each window, so an outage can neither fire nor hide an alert. Each rule fires at most once per data day (`alert_events` is unique on alert and data date) and not again until its cooldown passes. Alerts are shown on the Watchlists page only; nothing is sent outside the app.

`GET /api/export/daily.csv` returns daily totals per term and source for a date range. It has no post text or authors, and a day nobody collected gets a `not_collected` row with empty values instead of zeros.
