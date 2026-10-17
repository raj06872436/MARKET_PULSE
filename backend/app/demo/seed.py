"""Load the synthetic demo data through the real import and analysis pipeline.

    python -m app.demo.seed                 # end date = today (UTC)
    python -m app.demo.seed --end 2026-10-17 --csv-out ../data_samples

The data goes into a workspace owned by the demo account (--email, default demo@marketpulse.local).
The account is created if missing, with the password from DEMO_PASSWORD or a random one printed once.
"""

import argparse
import csv
import os
import secrets
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.pipeline import run_analysis
from app.connectors.base import NormalizedRecord
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.models import IngestionRun, TrackedEntity, User, Watchlist, Workspace
from app.demo.synthetic import BRANDS, generate
from app.ingestion.matching import build_matchers
from app.ingestion.service import ingest_records
from app.ml.sentiment.registry import get_model
from app.schemas.watchlist import normalize_term

WORKSPACE = "Demo workspace"
DEMO_EMAIL = "demo@marketpulse.local"
WATCHLIST = "Budget smartphones India"
FIELDS = ["source_record_id", "published_at", "text", "url", "language", "likes", "comments", "shares", "views"]


def _records(rows: list[dict], source: str) -> list[NormalizedRecord]:
    out = []
    for r in rows:
        engagement = {k: r[k] for k in ("likes", "comments") if r[k] != ""}
        out.append(NormalizedRecord(
            source=source, source_record_id=r["source_record_id"],
            published_at=datetime.fromisoformat(r["published_at"].replace("Z", "+00:00")),
            text=r["text"], permitted_url=r["url"], language=r["language"], engagement=engagement or None,
        ))
    return out


def demo_user(db: Session, email: str, password: str | None) -> tuple[User, str | None]:
    """The demo account, created if missing. Returns the password only when it was just generated."""
    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        return user, None
    generated = None if password else secrets.token_urlsafe(12)
    first = db.scalar(select(User.id).where(User.password_hash.is_not(None))) is None
    user = User(email=email, password_hash=hash_password(password or generated), role="admin" if first else "member",
                status="active")
    db.add(user)
    db.flush()
    return user, generated


def seed(db: Session, end: date, email: str = DEMO_EMAIL, password: str | None = None) -> dict:
    user, generated = demo_user(db, email, password)
    workspace = db.scalar(select(Workspace).where(Workspace.name == WORKSPACE, Workspace.owner_user_id == user.id))
    if workspace is None:
        # A workspace from before sign-in existed is adopted rather than duplicated.
        workspace = db.scalar(select(Workspace).where(Workspace.name == WORKSPACE, Workspace.owner_user_id.is_(None)))
    workspace = workspace or Workspace(name=WORKSPACE)
    workspace.owner_user_id = user.id
    db.add(workspace)
    db.flush()
    watchlist = db.scalar(select(Watchlist).where(Watchlist.workspace_id == workspace.id, Watchlist.name == WATCHLIST))
    if watchlist is None:
        watchlist = Watchlist(workspace_id=workspace.id, name=WATCHLIST)
        db.add(watchlist)
        db.flush()
    existing = {e.normalized_term for e in db.scalars(select(TrackedEntity).where(TrackedEntity.watchlist_id == watchlist.id))}
    for brand in BRANDS:
        if normalize_term(brand.term) not in existing:
            db.add(TrackedEntity(
                watchlist_id=watchlist.id, term=brand.term, normalized_term=normalize_term(brand.term),
                entity_type=brand.entity_type, variants=list(brand.variants),
                competitor_group="budget phones" if brand.entity_type == "competitor" else None,
            ))
    db.commit()

    history, recent = generate(end)
    matchers = build_matchers(db, workspace.id)
    inserted = 0
    for name, rows in (("demo-history", history), ("demo-recent", recent)):
        source = f"csv:{name}"
        run = IngestionRun(source=source, trigger="csv", status="running", started_at=datetime.now(UTC),
                           workspace_id=workspace.id)
        db.add(run)
        db.commit()
        stats = ingest_records(db, _records(rows, source), run, matchers)
        run.status, run.ended_at, run.rejected_count = "succeeded", datetime.now(UTC), 0
        run.coverage_json = {"file_name": f"{name}.csv (synthetic)", "complete": True}
        db.commit()
        inserted += stats.inserted
    summary = run_analysis(db, get_model(get_settings().sentiment_model))
    out = {"email": user.email, "workspace_id": str(workspace.id), "watchlist_id": str(watchlist.id),
           "inserted": inserted, "analysis": summary}
    if generated:
        out["password"] = generated
    return out


def write_csvs(end: date, out_dir: Path) -> None:
    history, recent = generate(end)
    for name, rows in (("demo-history", history), ("demo-recent", recent)):
        with (out_dir / f"{name}.csv").open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--end", type=date.fromisoformat, default=datetime.now(UTC).date())
    parser.add_argument("--csv-out", type=Path, help="Also write the two CSV files to this directory")
    parser.add_argument("--email", default=DEMO_EMAIL, help="Demo account email")
    args = parser.parse_args()
    if args.csv_out:
        write_csvs(args.end, args.csv_out)
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        result = seed(db, args.end, args.email, os.environ.get("DEMO_PASSWORD") or None)
    if "password" in result:
        print(f"Created {result['email']} with password {result['password']} (shown once; set DEMO_PASSWORD to choose it).")
    print({k: v for k, v in result.items() if k != "password"})


if __name__ == "__main__":
    main()
