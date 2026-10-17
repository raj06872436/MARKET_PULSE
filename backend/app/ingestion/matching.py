import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import TrackedEntity, Watchlist
from app.schemas.watchlist import normalize_term


@dataclass(frozen=True)
class EntityMatcher:
    entity_id: uuid.UUID
    pattern: re.Pattern[str]
    workspace_id: uuid.UUID | None = None


def build_matchers(db: Session, workspace_id: uuid.UUID | None = None) -> list[EntityMatcher]:
    """One case-insensitive, whole-word pattern per tracked entity in an active watchlist.

    With a workspace, only that workspace's terms: an upload never matches another workspace's terms."""
    query = select(TrackedEntity, Watchlist.workspace_id).join(Watchlist).where(Watchlist.active.is_(True))
    if workspace_id is not None:
        query = query.where(Watchlist.workspace_id == workspace_id)
    matchers = []
    for entity, entity_workspace in db.execute(query).all():
        phrases = {entity.normalized_term, *(normalize_term(v) for v in entity.variants)}
        alternatives = "|".join(re.escape(p).replace(r"\ ", r"\s+") for p in sorted(phrases, key=len, reverse=True))
        matchers.append(EntityMatcher(entity.id, re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)", re.IGNORECASE),
                                      entity_workspace))
    return matchers


def search_terms(db: Session) -> list[str]:
    """Terms and variants of every active watchlist, de-duplicated, for querying a source."""
    entities = db.scalars(
        select(TrackedEntity).join(Watchlist).where(Watchlist.active.is_(True)).order_by(TrackedEntity.created_at)
    ).all()
    seen: dict[str, str] = {}
    for entity in entities:
        for phrase in (entity.term, *entity.variants):
            seen.setdefault(normalize_term(phrase), phrase)
    return list(seen.values())


def match_text(text: str | None, matchers: list[EntityMatcher], workspace_id: uuid.UUID | None = None) -> list[uuid.UUID]:
    """Entities a text mentions. A record uploaded to a workspace only matches that workspace's terms."""
    if not text:
        return []
    return [m.entity_id for m in matchers
            if (workspace_id is None or m.workspace_id == workspace_id) and m.pattern.search(text)]
