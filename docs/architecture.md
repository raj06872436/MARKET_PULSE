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
| Accounts | `users`, `workspaces`, `audit_events` |
| Monitoring setup | `watchlists`, `tracked_entities`, `alerts` |
| Ingestion | `source_connections`, `ingestion_runs`, `social_records`, `record_matches` |
| Analytics | `nlp_results`, `daily_metrics`, `trend_signals`, `forecast_runs`, `forecast_points`, `insight_cards` |

Rules applied in the schema:

- UUID primary keys, plus indexes on date, source and tracked entity.
- Unique constraints stop duplicate source records (`source`, `source_record_id`), duplicate daily aggregates (`date`, `tracked_entity_id`, `source`) and duplicate terms within a watchlist (`watchlist_id`, `normalized_term`).
- Every NLP output stores `model_name`, `model_version` and `preprocessing_version`.
- Engagement and coverage fields are nullable. Null means "not available", not zero.
- `source_connections.credential_ref` points at a secret and never holds one.

## Decisions so far

- **No authentication yet.** `workspaces.owner_user_id` is nullable, and the frontend uses the first workspace or creates one. Auth arrives before any multi-user deployment.
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
