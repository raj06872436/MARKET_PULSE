"""Hand-check the dashboard numbers: recount mentions from raw records and compare with daily_metrics.

    python -m app.analytics.reconcile --start 2026-10-11 --end 2026-10-17
"""

import argparse
from collections import Counter
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.evidence import day_bounds
from app.core.config import get_settings
from app.db.models import DailyMetric, NlpResult, RecordMatch, SocialRecord, TrackedEntity
from app.ml.sentiment.registry import get_model


def reconcile(db: Session, start: date, end: date) -> list[dict]:
    lo, hi = day_bounds(start, end)
    model = get_model(get_settings().sentiment_model)
    rows = []
    for entity in db.scalars(select(TrackedEntity).order_by(TrackedEntity.term)):
        raw = db.execute(
            select(NlpResult.sentiment)
            .select_from(RecordMatch)
            .join(SocialRecord, SocialRecord.id == RecordMatch.record_id)
            .outerjoin(NlpResult, (NlpResult.record_id == SocialRecord.id) & (NlpResult.model_name == model.name)
                       & (NlpResult.model_version == model.version))
            .where(RecordMatch.tracked_entity_id == entity.id, SocialRecord.published_at >= lo, SocialRecord.published_at < hi)
        ).scalars().all()
        raw_sentiment = Counter(raw)
        metrics = db.scalars(select(DailyMetric).where(
            DailyMetric.tracked_entity_id == entity.id, DailyMetric.date >= start, DailyMetric.date <= end)).all()
        dashboard_negative = round(sum((m.negative_share or 0) * m.coverage_flags.get("scored", 0) for m in metrics))
        rows.append({
            "entity": entity.term,
            "raw_mentions": len(raw),
            "dashboard_mentions": sum(m.mentions for m in metrics),
            "raw_negative": raw_sentiment.get("negative", 0),
            "dashboard_negative": dashboard_negative,
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        print(f"Reconciliation {args.start} to {args.end} (UTC days)\n")
        print("| Entity | Raw mentions | Dashboard mentions | Raw negative | Dashboard negative | Match |")
        print("| --- | --- | --- | --- | --- | --- |")
        for r in reconcile(db, args.start, args.end):
            ok = r["raw_mentions"] == r["dashboard_mentions"] and r["raw_negative"] == r["dashboard_negative"]
            print(f"| {r['entity']} | {r['raw_mentions']} | {r['dashboard_mentions']} | {r['raw_negative']} | {r['dashboard_negative']} | {'yes' if ok else 'NO'} |")


if __name__ == "__main__":
    main()
