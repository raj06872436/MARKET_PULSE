import json
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ModelVersion
from app.ml.sentiment.base import PREPROCESSING_VERSION, SentimentModel
from app.ml.sentiment.evaluate import EVALUATION_PATH

TASK = "sentiment"


def load_evaluation() -> dict:
    return json.loads(EVALUATION_PATH.read_text())


@lru_cache
def get_model(name: str = "auto") -> SentimentModel:
    """The model named in settings, or with "auto" the one the latest evaluation selected."""
    if name == "auto":
        name = load_evaluation()["selected"]
    if name == "lexicon":
        from app.ml.sentiment.lexicon import LexiconSentiment

        return LexiconSentiment()
    if name == "tfidf-logreg":
        from app.ml.sentiment.tfidf import TfidfSentiment

        return TfidfSentiment(c=load_evaluation()["tfidf_selected_c"])
    if name == "transformer":
        from app.ml.sentiment.transformer import TransformerSentiment

        return TransformerSentiment()
    raise ValueError(f"Unknown sentiment model '{name}'")


def ensure_registered(db: Session, model: SentimentModel) -> ModelVersion:
    """Record the active model and its evaluation, and retire the previously active one."""
    row = db.scalar(
        select(ModelVersion).where(ModelVersion.task == TASK, ModelVersion.name == model.name, ModelVersion.version == model.version)
    )
    if row is not None and row.status == "active":
        return row
    evaluation = load_evaluation()
    entry = evaluation["models"].get(model.name, {})
    for previous in db.scalars(select(ModelVersion).where(ModelVersion.task == TASK, ModelVersion.status == "active")):
        previous.status = "retired"
    if row is None:
        row = ModelVersion(task=TASK, name=model.name, version=model.version, preprocessing_version=PREPROCESSING_VERSION)
        db.add(row)
    row.status = "active"
    row.evaluation_json = {
        "dataset": evaluation["dataset"],
        "generated_at": evaluation["generated_at"],
        "validation": entry.get("validation"),
        "test": {k: v for k, v in entry.get("test", {}).items() if k != "errors"} or None,
    } if entry.get("version") == model.version else None
    db.commit()
    return row
