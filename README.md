# MarketPulse AI

Social listening and market intelligence for consumer brands. MarketPulse tracks brands, products and competitors across approved data sources, measures sentiment and topics, flags trends and forecasts short-term attention. Every insight links back to the evidence behind it.

It covers consumer markets only. It does not predict stock or crypto prices.

## Status

This is the Week 2 foundation from the implementation plan:

- FastAPI backend with typed config, JSON logging and a health check
- PostgreSQL schema for every table in the plan, managed by Alembic migrations
- Workspace, watchlist and tracked-entity endpoints (create, edit, pause, delete, duplicate-safe terms)
- React + TypeScript + Vite + Tailwind shell with a working Watchlists page and placeholders for later screens
- Docker Compose for local development and GitHub Actions CI

Authentication, connectors, the CSV importer and all analytics come in later weeks. See [docs/architecture.md](docs/architecture.md).

## Run with Docker

```bash
cp .env.example .env
docker compose up --build
```

Open http://localhost:5173. The API runs on http://localhost:8000 and its docs on http://localhost:8000/docs. Migrations run automatically when the backend starts.

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
cd backend && pytest        # API tests, run against in-memory SQLite
alembic check               # fails if the models and migrations disagree
cd ../frontend && npm run build   # type-check and build
```

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
docs/
```

## Data rules

- Collect only through approved APIs, licensed datasets or user uploads. No scraping that breaks platform terms and no private content.
- Keep API keys in `.env` or a secret store and never in Git.
- Missing engagement is stored as null, never as zero, and a failed source must never read as zero mentions.
