import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.analytics.pipeline import run_analysis
from app.core.config import Settings, get_settings
from app.ml.sentiment.registry import get_model

from app.api.deps import current_user, owned_watchlist, owned_workspace, workspace_ids
from app.db.models import TrackedEntity, User, Watchlist
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


def _get_watchlist(db: Session, user: User, watchlist_id: uuid.UUID) -> Watchlist:
    return owned_watchlist(db, user, watchlist_id)


@router.post("", response_model=WatchlistRead, status_code=status.HTTP_201_CREATED)
def create_watchlist(body: WatchlistCreate, db: Session = Depends(get_db), user: User = Depends(current_user)) -> Watchlist:
    owned_workspace(db, user, body.workspace_id)
    watchlist = Watchlist(workspace_id=body.workspace_id, name=body.name, language=body.language)
    db.add(watchlist)
    db.commit()
    return _get_watchlist(db, user, watchlist.id)


@router.get("", response_model=list[WatchlistRead])
def list_watchlists(
    workspace_id: uuid.UUID | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> list[Watchlist]:
    query = (select(Watchlist).options(selectinload(Watchlist.entities))
             .where(Watchlist.workspace_id.in_(workspace_ids(db, user))).order_by(Watchlist.created_at))
    if workspace_id is not None:
        query = query.where(Watchlist.workspace_id == workspace_id)
    return list(db.scalars(query))


@router.get("/{watchlist_id}", response_model=WatchlistRead)
def get_watchlist(watchlist_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)) -> Watchlist:
    return _get_watchlist(db, user, watchlist_id)


@router.patch("/{watchlist_id}", response_model=WatchlistRead)
def update_watchlist(
    watchlist_id: uuid.UUID, body: WatchlistUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> Watchlist:
    watchlist = _get_watchlist(db, user, watchlist_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(watchlist, field, value)
    db.commit()
    return _get_watchlist(db, user, watchlist_id)


@router.delete("/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watchlist(watchlist_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)) -> Response:
    db.delete(_get_watchlist(db, user, watchlist_id))
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
    user: User = Depends(current_user),
) -> TrackedEntity:
    watchlist = _get_watchlist(db, user, watchlist_id)
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
def delete_entity(
    watchlist_id: uuid.UUID, entity_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> Response:
    _get_watchlist(db, user, watchlist_id)
    entity = db.get(TrackedEntity, entity_id)
    if entity is None or entity.watchlist_id != watchlist_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entity not found")
    db.delete(entity)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
