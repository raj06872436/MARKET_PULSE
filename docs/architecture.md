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
- New watchlist terms only match records ingested after they were added. Backfilling matches for older records is planned alongside the daily aggregates.
