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
- **Connectors are not chosen yet.** That depends on the Week 1 source feasibility check. `app/connectors/base.py` defines the interface every connector has to implement.
