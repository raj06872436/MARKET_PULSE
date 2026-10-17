import uuid
from itertools import batched

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.db.models import NlpResult, SocialRecord
from app.ml.sentiment.base import PREPROCESSING_VERSION, SentimentModel
from app.ml.sentiment.registry import ensure_registered
from app.ml.topics.aspects import ASPECT_VERSION, tag_aspects

BATCH_SIZE = 500


def score_pending(db: Session, model: SentimentModel, run_id: uuid.UUID | None = None) -> int:
    """Score every stored record that has no result from this model version yet. Returns how many were scored."""
    ensure_registered(db, model)
    query = (
        select(SocialRecord.id, SocialRecord.text_reference)
        .outerjoin(
            NlpResult,
            and_(
                NlpResult.record_id == SocialRecord.id,
                NlpResult.model_name == model.name,
                NlpResult.model_version == model.version,
            ),
        )
        .where(NlpResult.record_id.is_(None), SocialRecord.text_reference.is_not(None))
    )
    if run_id is not None:
        query = query.where(SocialRecord.ingestion_run_id == run_id)
    rows = db.execute(query).all()
    for batch in batched(rows, BATCH_SIZE):
        texts = [text for _, text in batch]
        predictions = model.predict(texts)
        aspects = tag_aspects(texts, model, [p.label for p in predictions])
        for (record_id, _), p, items in zip(batch, predictions, aspects, strict=True):
            db.add(
                NlpResult(
                    record_id=record_id,
                    model_name=model.name,
                    model_version=model.version,
                    preprocessing_version=PREPROCESSING_VERSION,
                    sentiment=p.label,
                    confidence=p.confidence,
                    scores_json=p.scores,
                    flags_json=p.flags or None,
                    aspects_json={"version": ASPECT_VERSION, "items": items},
                )
            )
        db.commit()
    return len(rows)


def tag_stale_aspects(db: Session, model: SentimentModel) -> int:
    """Re-tag aspects on this model's results that were tagged by an older taxonomy (or never)."""
    rows = db.execute(
        select(NlpResult, SocialRecord.text_reference)
        .join(SocialRecord, SocialRecord.id == NlpResult.record_id)
        .where(NlpResult.model_name == model.name, NlpResult.model_version == model.version)
    ).all()
    stale = [(r, text) for r, text in rows if (r.aspects_json or {}).get("version") != ASPECT_VERSION and text]
    for batch in batched(stale, BATCH_SIZE):
        items = tag_aspects([text for _, text in batch], model, [r.sentiment or "neutral" for r, _ in batch])
        for (result, _), tagged in zip(batch, items, strict=True):
            result.aspects_json = {"version": ASPECT_VERSION, "items": tagged}
        db.commit()
    return len(stale)
