# Security and privacy

This page covers how MarketPulse controls access, what it stores, and the week 9 review. It describes the code as it is; re-check it before inviting people outside your team.

## Accounts and sessions

- Accounts sign in with an email and a password of at least 10 characters. Passwords are hashed with scrypt and a per-password salt (`app/core/security.py`); the password itself is never stored or logged.
- Signing in sets an `HttpOnly`, `SameSite=Lax` session cookie. It is also `Secure` (HTTPS only) everywhere except `ENVIRONMENT=local`. The database keeps only a SHA-256 of the cookie, so a copy of the database can't be used to sign in. Sessions last `SESSION_DAYS` (14) from the last request and are deleted on sign-out.
- The first account is the **admin**. It takes over any workspace created before sign-in existed, so an upgraded installation keeps its data. Later accounts are **members**. Set `ALLOW_REGISTRATION=false` once the accounts you need exist.
- Wrong email and wrong password get the same answer in about the same time, so the sign-in form can't be used to find out who has an account.
- Sign-ins, failed sign-ins, new accounts and deletions are written to `audit_events` (no passwords or tokens).

## Who can see what

| Data | Who can see or change it |
|---|---|
| Workspaces, watchlists, terms, alerts, insights, forecasts, exports | Only the workspace owner |
| Uploaded CSV files and their posts | Only the workspace they were uploaded to; they never match another workspace's terms, and two workspaces can upload the same file without clashing |
| Posts from shared sources (Bluesky) | Any workspace whose terms they mention. The search uses every active term from every workspace, so the terms themselves are sent to the source |
| Source connections (enable, terms review) and full re-analysis | Admin only, because they affect every workspace |
| Jobs list and source health | Shared sources plus your own uploads |

Every endpoint that takes an ID checks ownership on the server and answers 404 for anything that isn't yours, the same as for something that doesn't exist. `tests/test_security.py` calls each endpoint as a second account to prove it.

## Limits on expensive or abusable endpoints

In-process sliding windows (`app/core/ratelimit.py`), answered with 429 and a `Retry-After` header:

| Endpoint | Limit |
|---|---|
| Sign in | 10 per 15 minutes per IP and email |
| Create account | 5 per hour per IP |
| CSV import | 10 per minute per user (plus the 10 MB and 50,000-row limits) |
| Forecast run | 20 per minute per user |
| Insight refresh | 10 per minute per user; Claude-written insights 5 per hour |
| Export | 30 per minute per user |
| Source sync, full re-analysis | 5 per minute per user |

Counts are per process. Behind several API workers, multiply by the worker count, or move the counts to Redis.

## Errors and logs

- Every response carries an `X-Request-ID`. An unexpected error returns a plain message with that ID; the details go to the server log only.
- Logs are JSON lines. Values after words like `password`, `token`, `secret`, `api_key`, `authorization` or `cookie`, Anthropic keys, and database URL passwords are masked before writing. Post text and authors are not logged.
- Responses carry `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: same-origin` and, when cookies are secure, `Strict-Transport-Security`. CORS allows credentials only from `CORS_ORIGINS`.

## Data kept and deleted

- **Account deletion** (Account page, or `DELETE /api/auth/me`) removes the account, its sessions, its workspaces and everything in them: watchlists, terms, alerts, insights, forecasts, uploaded files and the posts from them. Posts from shared sources stay, since other workspaces may use them. The only admin can't delete their account while other accounts exist.
- Insight writing with Claude is off by default. When on, see [insights.md](insights.md#what-is-sent-to-anthropic) for exactly what is sent.
- Post text is kept only where the source's terms allow it; engagement and coverage fields stay null when unknown.

## Week 9 review (2026-10-17)

| Check | How | Result |
|---|---|---|
| Secrets in Git | Pattern scan of every commit for Anthropic, AWS, GitHub, Slack and Google keys, private keys and assigned passwords or tokens; list of tracked `.env`, key and certificate files | None found. Only `.env.example` is tracked, with empty values |
| Python dependencies | `pip-audit -r backend/requirements.txt` | No known vulnerabilities |
| JavaScript dependencies | `npm audit` | 0 vulnerabilities |
| Sample and demo data | Scanned `data_samples/`, the demo generator and the labelled sentiment set for URLs, emails and @handles | Synthetic only. All 61 links point at example.com; no emails or handles |
| Access control | `tests/test_security.py`: 25 endpoint calls made as a second account | All refused with 404; admin-only actions refused with 403 for members |
| Accessibility | axe-core WCAG 2 A and AA rules on every page at 1280px, plus a keyboard check | Clean after raising the contrast of small grey text and heat-map labels |
| Performance | Demo data: 5,961 posts, 4 terms, 90-day range, local Postgres | Slowest calls were Compare (0.87 s) and the post table (0.35 s). After loading only the needed columns, and loading full posts only for the shown page, both are near 0.1 to 0.15 s. Other endpoints answer in under 0.2 s |

## Known gaps

- The local `docker-compose.yml` uses a fixed database password. It is for development only; a deployment must supply its own `DATABASE_URL`.
- There is no email verification or password reset yet. An admin can't reset another account's password from the app.
- A workspace has one owner; sharing a workspace with teammates is not built.
- Rate limits are per process, as above.
