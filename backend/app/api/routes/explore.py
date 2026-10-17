import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.analytics import explore
from app.api.routes.metrics import _check_range, _parse_ids
from app.core.config import Settings, get_settings
from app.api.deps import current_user, owned_entity, owned_watchlist
from app.db.models import User
from app.db.session import get_db
from app.ml.sentiment.registry import get_model
from app.schemas.explore import Comparison, DataRange, RecordPage, SentimentBreakdown

router = APIRouter(tags=["explore"])


@router.get("/watchlists/{watchlist_id}/data-range", response_model=DataRange)
def data_range(watchlist_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)) -> DataRange:
    return explore.data_range(db, owned_watchlist(db, user, watchlist_id))


@router.get("/records", response_model=RecordPage)
def records(
    watchlist_id: uuid.UUID,
    start: date,
    end: date,
    entity_ids: str | None = Query(None, description="Comma-separated; defaults to every term in the watchlist"),
    source: list[str] | None = Query(None),
    q: str | None = Query(None, max_length=200),
    sentiment: Literal["positive", "neutral", "negative", "unscored"] | None = None,
    aspect: str | None = Query(None, max_length=50),
    sort: Literal["newest", "oldest", "engagement"] = "newest",
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(current_user),
) -> RecordPage:
    _check_range(start, end)
    watchlist = owned_watchlist(db, user, watchlist_id)
    allowed = {e.id for e in watchlist.entities}
    ids = _parse_ids(entity_ids) if entity_ids else list(allowed)
    if stray := [str(i) for i in ids if i not in allowed]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Not in this watchlist: {', '.join(stray)}")
    if not ids:
        return RecordPage(total=0, limit=limit, offset=offset, items=[])
    return explore.search_records(
        db, ids, start, end, get_model(settings.sentiment_model), sources=source, q=q.strip() if q else None,
        sentiment=sentiment, aspect=aspect, sort=sort, limit=limit, offset=offset,
    )


@router.get("/entities/{entity_id}/sentiment", response_model=SentimentBreakdown)
def sentiment(
    entity_id: uuid.UUID,
    start: date,
    end: date,
    source: list[str] | None = Query(None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(current_user),
) -> SentimentBreakdown:
    _check_range(start, end)
    entity = owned_entity(db, user, entity_id)
    return explore.sentiment_breakdown(db, entity, start, end, get_model(settings.sentiment_model), source)


@router.get("/compare", response_model=Comparison)
def compare(
    watchlist_id: uuid.UUID,
    start: date,
    end: date,
    source: list[str] | None = Query(None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(current_user),
) -> Comparison:
    _check_range(start, end)
    return explore.compare(db, owned_watchlist(db, user, watchlist_id), start, end, get_model(settings.sentiment_model), source)
