import uuid
from itertools import batched

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.db.models import NlpResult, SocialRecord
from app.ml.sentiment.base import PREPROCESSING_VERSION, SentimentModel
from app.ml.sentiment.registry import ensure_registered

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
        predictions = model.predict([text for _, text in batch])
        for (record_id, _), p in zip(batch, predictions, strict=True):
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
                )
            )
        db.commit()
    return len(rows)
