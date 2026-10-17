import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.analytics.pipeline import run_analysis
from app.core.config import Settings, get_settings
from app.ml.sentiment.registry import get_model

from app.db.models import TrackedEntity, Watchlist, Workspace
from app.db.session import get_db, get_session_factory
from app.schemas.watchlist import (
    TrackedEntityCreate,
    TrackedEntityRead,
    WatchlistCreate,
    WatchlistRead,
    WatchlistUpdate,
    normalize_term,
)

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


def _reanalyze(session_factory: sessionmaker, model_name: str) -> None:
    """Terms changed: match older posts to them and refresh the aggregates."""
    with session_factory() as db:
        run_analysis(db, get_model(model_name))


def _get_watchlist(db: Session, watchlist_id: uuid.UUID) -> Watchlist:
    watchlist = db.scalar(
        select(Watchlist).where(Watchlist.id == watchlist_id).options(selectinload(Watchlist.entities))
    )
    if watchlist is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Watchlist not found")
    return watchlist


@router.post("", response_model=WatchlistRead, status_code=status.HTTP_201_CREATED)
def create_watchlist(body: WatchlistCreate, db: Session = Depends(get_db)) -> Watchlist:
    if db.get(Workspace, body.workspace_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    watchlist = Watchlist(workspace_id=body.workspace_id, name=body.name, language=body.language)
    db.add(watchlist)
    db.commit()
    return _get_watchlist(db, watchlist.id)


@router.get("", response_model=list[WatchlistRead])
def list_watchlists(workspace_id: uuid.UUID | None = None, db: Session = Depends(get_db)) -> list[Watchlist]:
    query = select(Watchlist).options(selectinload(Watchlist.entities)).order_by(Watchlist.created_at)
    if workspace_id is not None:
        query = query.where(Watchlist.workspace_id == workspace_id)
    return list(db.scalars(query))


@router.get("/{watchlist_id}", response_model=WatchlistRead)
def get_watchlist(watchlist_id: uuid.UUID, db: Session = Depends(get_db)) -> Watchlist:
    return _get_watchlist(db, watchlist_id)


@router.patch("/{watchlist_id}", response_model=WatchlistRead)
def update_watchlist(watchlist_id: uuid.UUID, body: WatchlistUpdate, db: Session = Depends(get_db)) -> Watchlist:
    watchlist = _get_watchlist(db, watchlist_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(watchlist, field, value)
    db.commit()
    return _get_watchlist(db, watchlist_id)


@router.delete("/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watchlist(watchlist_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    db.delete(_get_watchlist(db, watchlist_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{watchlist_id}/entities", response_model=TrackedEntityRead, status_code=status.HTTP_201_CREATED)
def add_entity(
    watchlist_id: uuid.UUID,
    body: TrackedEntityCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    session_factory: sessionmaker = Depends(get_session_factory),
    settings: Settings = Depends(get_settings),
) -> TrackedEntity:
    watchlist = _get_watchlist(db, watchlist_id)
    normalized = normalize_term(body.term)
    if any(entity.normalized_term == normalized for entity in watchlist.entities):
        raise HTTPException(status.HTTP_409_CONFLICT, f"'{body.term}' is already tracked in this watchlist")
    entity = TrackedEntity(
        watchlist_id=watchlist.id,
        term=body.term,
        normalized_term=normalized,
        entity_type=body.entity_type,
        variants=[v for v in body.variants if normalize_term(v) != normalized],
        competitor_group=body.competitor_group,
    )
    db.add(entity)
    db.commit()
    background.add_task(_reanalyze, session_factory, settings.sentiment_model)
    return entity


@router.delete("/{watchlist_id}/entities/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entity(watchlist_id: uuid.UUID, entity_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    entity = db.get(TrackedEntity, entity_id)
    if entity is None or entity.watchlist_id != watchlist_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entity not found")
    db.delete(entity)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
