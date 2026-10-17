# MarketPulse AI

Social listening and market intelligence for consumer brands. MarketPulse tracks brands, products and competitors across approved data sources, measures sentiment and topics, flags trends and forecasts short-term attention. Every insight links back to the evidence behind it.

It covers consumer markets only. It does not predict stock or crypto prices.

## Status

All ten weeks of the implementation plan are built:

- FastAPI backend with typed config, JSON logging and a health check
- PostgreSQL schema for every table in the plan, managed by Alembic migrations
- Workspaces and watchlists: create, edit, pause and delete, with duplicate-safe terms and variants
- CSV import with row-level validation ([format](docs/csv-format.md)) and a synthetic sample in `data_samples/`
- Bluesky connector with paging, retries and backoff, behind a recorded terms review
- Sync jobs with status, incremental windows, an optional scheduler, and deduplication so repeated syncs never double-count
- Source health that tells "failed" and "incomplete" apart from "no mentions"
- Sentiment on every stored post, with confidence, quality flags and model versioning ([model card](docs/model-card-sentiment.md), [evaluation](docs/evaluation/sentiment.md))
- Aspect tagging (price, battery, camera, delivery and more) and frequent phrases per entity
- Daily metrics per entity that keep "not collected" days apart from zero-mention days
- An explainable trend score with confidence, components and example posts ([how it works](docs/architecture.md#trend-score))
- Daily mention forecasts with an 80% range, compared against three baselines in a rolling back-test, and a "not enough reliable data" state when the data doesn't support one ([model card](docs/model-card-forecast.md), [back-test](docs/evaluation/forecast.md))
- Dashboard pages: Overview, Explore (searchable post table), Sentiment (over time, by topic, phrases and examples), Compare (scorecards, share of voice, topic gaps) and Forecasts, plus Watchlists and Sources
- Shared filters for watchlist, date range and sources, kept in the URL so they carry between pages and can be shared as links
- Coverage labels on every chart and comparison, and warnings when a source failed or the data is stale
- Insight cards that state what changed, a cautious possible explanation, a caveat and a next step, each linked to the numbers and posts behind it. Templates write them by default; Claude can write them when enabled, and every number it states is checked against the data first ([how insights work](docs/insights.md))
- Threshold alerts on daily mentions, weekly change, negative share or trend score, with a cooldown, shown in the app
- Daily totals export as CSV (counts and shares only, with uncollected days marked)
- Accounts with sign-in, private workspaces, and server-side checks on every endpoint so one account never sees another's watchlists, uploads or results ([security notes](docs/security.md))
- Rate limits on sign-in and expensive endpoints, safe error messages with a request ID, security headers and redacted logs
- Accessibility: keyboard skip link, labelled controls, text summaries for every chart, and a clean automated WCAG 2 AA check on every page
- A production Docker image that serves the app and API on one port, with a Render Blueprint, a single-server Compose file, and a smoke test that CI runs against the built image ([deployment guide](docs/deployment.md))
- Docker Compose for local development and GitHub Actions CI

## Documentation

- [User guide](docs/user-guide.md): what each page shows and how to read the numbers
- [Demo script](docs/demo-script.md): a 10 to 15 minute walk-through on the demo data
- [Deployment](docs/deployment.md): hosting, settings, backups and logs
- [Evaluation summary and limitations](docs/evaluation/summary.md): how far to trust each part
- [Architecture](docs/architecture.md), [security](docs/security.md), [insights](docs/insights.md), [CSV format](docs/csv-format.md)
- Model cards: [sentiment](docs/model-card-sentiment.md), [forecast](docs/model-card-forecast.md)

## Getting data in

1. Create a watchlist and add the brands or products to track on the **Watchlists** page.
2. On **Sources**, either upload a CSV (try `data_samples/sample_mentions.csv`) or connect Bluesky. Connecting asks you to confirm you've checked the platform's current terms; the date and your notes are saved.
3. Press **Sync now**, or set `SCHEDULER_ENABLED=true` to sync every `SYNC_INTERVAL_MINUTES`.

Each run records how many records were fetched, new, already stored, matched to a watchlist and rejected, plus what it couldn't cover.

## Demo data

To see every chart without collecting anything, load the synthetic demo. It creates a "Demo workspace" with four budget phones and 120 days of fake posts (one product grows with a one-day spike, a competitor gets a complaint surge, one is flat, one declines, and three days are left uncollected on purpose):

```bash
cd backend
DEMO_PASSWORD='choose-a-password' python -m app.demo.seed --end 2026-10-17
```

Sign in as `demo@marketpulse.local` with that password. Without `DEMO_PASSWORD` the script makes up a password and prints it once. If the demo account is the first account, it is the admin. Everything it writes is fictional and links point at example.com. Add `--csv-out ../data_samples` to also save the two CSVs.

To check that the dashboard numbers match the raw records for a date range:

```bash
python -m app.analytics.reconcile --start 2026-09-01 --end 2026-10-17
```

To rebuild the forecast back-test report from the latest forecasts:

```bash
python -m app.ml.forecasting.report --out ../docs/evaluation/forecast.md
```

## Run with Docker

```bash
cp .env.example .env
docker compose up --build
```

Open http://localhost:5173 and create an account; the first account becomes the admin, who can connect shared sources. The API runs on http://localhost:8000 and its docs on http://localhost:8000/docs. Migrations run automatically when the backend starts.

## Run without Docker

You need Python 3.13, Node 22 and a PostgreSQL 16 database matching `DATABASE_URL` in `.env.example`.

```bash
# backend
cd backend
cp ../.env.example .env
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload

# frontend, in a second terminal
cd frontend
npm install
npm run dev
```

## Tests

```bash
cd backend && pytest        # API, analytics, security and end-to-end journey tests on in-memory SQLite
alembic check               # fails if the models and migrations disagree
cd ../frontend && npm run build   # type-check and build
```

## Deploy

```bash
docker build -t marketpulse .
docker run -p 8000:8000 -e DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/marketpulse marketpulse
```

The image runs migrations on start and serves the app at http://localhost:8000. Add `-e COOKIE_SECURE=false` only to try it over plain http on your own machine. For Render, other platforms, a single server, backups and logs, see the [deployment guide](docs/deployment.md). Check any deployment with `python3 deploy/smoke.py <url> <email> <password>`.

## Changing the schema

Edit the models in `backend/app/db/models/`, then generate and review a migration:

```bash
cd backend
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

Never edit the database by hand.

## Repository layout

```
backend/app/
  api/routes/   HTTP endpoints
  core/         settings and logging
  db/models/    SQLAlchemy models (one file per area)
  schemas/      Pydantic request and response models
  connectors/   source adapters, all implementing SourceConnector
  ingestion/  analytics/  ml/{sentiment,topics,forecasting}/  insights/  jobs/
backend/alembic/  migrations
backend/tests/
frontend/src/{api,charts,components,pages,types}/
data_samples/   synthetic or licensed examples only
notebooks/      experiments, not production logic
deploy/         container entrypoint and the deployment smoke test
docs/
Dockerfile      production image (frontend build served by the API)
```

## Data rules

- Collect only through approved APIs, licensed datasets or user uploads. No scraping that breaks platform terms and no private content.
- Keep API keys in `.env` or a secret store and never in Git.
- Missing engagement is stored as null, never as zero, and a failed source must never read as zero mentions.
