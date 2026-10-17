# Deployment

MarketPulse ships as one container: the FastAPI app serves both the API (`/api/...`) and the built React frontend on the same origin, so there is no separate web server and no CORS to configure. It needs one PostgreSQL 16 database.

## What's in the image

The root `Dockerfile` builds the frontend with Node 22, then copies the result into a Python 3.13 image with the backend. The container:

- runs as a non-root user (`marketpulse`, uid 10001);
- on start, applies database migrations (`alembic upgrade head`) and then starts uvicorn on `$PORT` (default 8000);
- answers `GET /api/health` and has a Docker `HEALTHCHECK` on it;
- writes JSON log lines to stdout, one per API request plus anything the app logs, with secrets masked.

CI builds this image on every pull request, starts it against a fresh Postgres, seeds the demo data and runs `deploy/smoke.py` through the main screens' API calls.

## Settings

Set these as environment variables on the host. Never put real values in Git.

| Variable | Needed | What it does |
|---|---|---|
| `DATABASE_URL` | Yes | Postgres connection. `postgres://` and `postgresql://` URLs from hosting providers are accepted and switched to the psycopg driver. Add `?sslmode=require` when the database is reached over a network. |
| `ENVIRONMENT` | Set by the image | `production`. Turns on secure (HTTPS-only) cookies and HSTS. |
| `COOKIE_SECURE` | Only to override | Leave unset behind HTTPS. Set `false` only to try the image on plain `http://localhost`. |
| `ALLOW_REGISTRATION` | Recommended | Leave `true` until you and your team have signed up, then set `false`. The first account is the admin. |
| `SESSION_DAYS` | No | How long a sign-in lasts after the last request. Default 14. |
| `FORWARDED_ALLOW_IPS` | Behind a proxy | Which proxy addresses to trust for the client IP and scheme. Rate limits use the client IP, so set this to your load balancer's address range, or `*` on platforms where only the platform's proxy can reach the container. Default `127.0.0.1`. |
| `PORT` | No | Port to listen on. Most platforms set it. Default 8000. |
| `WEB_CONCURRENCY` | No | Uvicorn workers. Keep it at 1, see below. |
| `RUN_MIGRATIONS` | No | Set `false` if you run `alembic upgrade head` as a separate release step. |
| `DB_POOL_SIZE` | No | Connections per worker. Default 5; keep the total below your database's connection limit. |
| `SCHEDULER_ENABLED`, `SYNC_INTERVAL_MINUTES` | No | Sync enabled sources in the background. Off by default. |
| `INSIGHTS_LLM_ENABLED`, `ANTHROPIC_API_KEY`, `INSIGHTS_MODEL` | No | Let Claude write insight cards. Off by default; read [what is sent](insights.md#what-is-sent-to-anthropic) first. Store the key in the platform's secret store. |
| `BLUESKY_HANDLE`, `BLUESKY_APP_PASSWORD` | No | Only if Bluesky search needs a signed-in account. |
| `LOG_LEVEL` | No | Default `INFO`. |

**Why one worker:** sign-in and endpoint rate limits are counted in the process, and the optional sync scheduler runs inside it. With more workers or more replicas, each keeps its own counts (so limits become N times looser) and each runs the scheduler. One worker comfortably handles a pilot; if you need more, put rate limiting in front (at the load balancer) and run the scheduler in a single separate instance.

## Option 1: Render (Blueprint included)

`render.yaml` describes a Docker web service and a managed Postgres database.

1. In Render, choose **New > Blueprint** and select this repository.
2. When asked, leave `ANTHROPIC_API_KEY` empty unless you are turning on Claude-written insights.
3. Wait for the first deploy, open the service URL and create your account. It becomes the admin.
4. Set `ALLOW_REGISTRATION=false` once everyone who needs an account has one.

Render terminates HTTPS and passes the client address through its proxy, which is why the Blueprint sets `FORWARDED_ALLOW_IPS=*`. Plans and prices are Render's; change `plan:` in the file to suit.

## Option 2: Any container platform

Fly.io, Railway, Google Cloud Run, Azure Container Apps and AWS App Runner all run the same image. On each:

1. Create a managed PostgreSQL 16 database with automated backups.
2. Deploy the image built from the root `Dockerfile`, with the settings above. Health check path: `/api/health`.
3. Serve it over HTTPS only (all of these do by default). Secure cookies won't be sent over plain HTTP.
4. Keep one instance with one worker, or read the note above before scaling out.

On platforms that scale to zero (Cloud Run), the scheduler only runs while an instance is up. Either keep one minimum instance or leave the scheduler off and sync from the Sources page.

## Option 3: A single server with Docker Compose

`docker-compose.prod.yml` runs the image with its own Postgres on one machine:

```bash
cp .env.example .env        # set POSTGRES_PASSWORD; set COOKIE_SECURE=false only for http://localhost
docker compose -f docker-compose.prod.yml up --build -d
docker compose -f docker-compose.prod.yml logs -f app
```

Put a reverse proxy with HTTPS (Caddy, nginx, Traefik) in front of port 8000 and set `FORWARDED_ALLOW_IPS` to its address. You are then responsible for the database backups below.

## Demo data on a deployment

Load the fictional demo dataset into a running deployment with:

```bash
DEMO_PASSWORD='choose-a-password' python -m app.demo.seed
```

run inside the container (for Compose: `docker compose -f docker-compose.prod.yml exec -e DEMO_PASSWORD=... app python -m app.demo.seed`; on Render, the service's Shell tab). Sign in as `demo@marketpulse.local`. If the demo account is the first account on the deployment it becomes the admin, so create your own account first if you don't want that.

## Checking a deployment

```bash
python3 deploy/smoke.py https://your-app.example.com demo@marketpulse.local 'the-demo-password'
```

It uses only the Python standard library and checks health, the frontend, sign-in, and the API calls behind Overview, Explore, Compare, Forecasts, Insights and export. It reads data only.

## Backups and restore

Use the managed database's automated backups and point-in-time recovery where offered. For the Compose option, take a nightly dump and copy it off the server:

```bash
docker compose -f docker-compose.prod.yml exec -T db pg_dump -U marketpulse -Fc marketpulse > marketpulse-$(date +%F).dump
```

Test a restore before relying on it, into a fresh database:

```bash
createdb -h HOST -U USER marketpulse_restore
pg_restore -h HOST -U USER -d marketpulse_restore --no-owner marketpulse-YYYY-MM-DD.dump
```

then point a copy of the app at it and run `deploy/smoke.py`.

## Logs and monitoring

Each API request (apart from the health check) is logged as one JSON line with method, path, status, duration and request ID. Errors include the request ID shown to the user, so a report of "Something went wrong ... (ID abc123)" can be found in the logs. Point the platform's log alerting at:

- `"level": "ERROR"` lines (unexpected errors, failed syncs);
- status 429 bursts (someone hitting rate limits);
- health check failures.

In the app, the **Sources** page shows each source's last successful run, errors, and days not collected, which covers connector health.

## Updating

Deploy the new image. Migrations run on start before the app accepts requests, so a release that fails to migrate never serves traffic. Migrations are written to be applied in order from any earlier release; never edit the database by hand. To roll back code, deploy the previous image; to roll back a schema change, run `alembic downgrade -1` from the previous release's image first.

## Before inviting outside users

- Turn registration off once the expected accounts exist.
- Confirm HTTPS and that the `mp_session` cookie is marked `Secure`.
- Rotate any key that was ever pasted into a chat, ticket or log.
- Read [security.md](security.md#known-gaps): there is no password reset or email verification yet.
- Write a privacy notice saying what is collected, how long it is kept, and how to delete an account (the Account page does it).
