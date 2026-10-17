from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.sentiment import score_pending
from app.core.config import Settings, get_settings
from app.db.models import ModelVersion
from app.db.session import get_db
from app.ml.sentiment.registry import ensure_registered, get_model
from app.schemas.analysis import ModelVersionRead, ScoringResult

router = APIRouter(tags=["analysis"])


@router.post("/analysis/sentiment", response_model=ScoringResult)
def score_sentiment(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> ScoringResult:
    """Score every stored record the active model hasn't scored yet (e.g. after switching models)."""
    model = get_model(settings.sentiment_model)
    scored = score_pending(db, model)
    return ScoringResult(model=ModelVersionRead.model_validate(ensure_registered(db, model)), scored=scored)


@router.get("/models", response_model=list[ModelVersionRead])
def list_models(db: Session = Depends(get_db)) -> list[ModelVersion]:
    return list(db.scalars(select(ModelVersion).order_by(ModelVersion.task, ModelVersion.created_at.desc())))
