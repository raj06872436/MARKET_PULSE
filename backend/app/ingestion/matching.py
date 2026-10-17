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


def build_matchers(db: Session) -> list[EntityMatcher]:
    """One case-insensitive, whole-word pattern per tracked entity in an active watchlist."""
    entities = db.scalars(
        select(TrackedEntity).join(Watchlist).where(Watchlist.active.is_(True))
    ).all()
    matchers = []
    for entity in entities:
        phrases = {entity.normalized_term, *(normalize_term(v) for v in entity.variants)}
        alternatives = "|".join(re.escape(p).replace(r"\ ", r"\s+") for p in sorted(phrases, key=len, reverse=True))
        matchers.append(EntityMatcher(entity.id, re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)", re.IGNORECASE)))
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


def match_text(text: str | None, matchers: list[EntityMatcher]) -> list[uuid.UUID]:
    if not text:
        return []
    return [m.entity_id for m in matchers if m.pattern.search(text)]
