import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

EntityType = Literal["brand", "product", "keyword", "hashtag", "competitor"]


def normalize_term(value: str) -> str:
    """Canonical form used for duplicate detection: trimmed, single-spaced, case-folded."""
    return " ".join(value.split()).casefold()


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    created_at: datetime


class TrackedEntityCreate(BaseModel):
    term: str = Field(min_length=1, max_length=200)
    entity_type: EntityType
    variants: list[str] = Field(default_factory=list, max_length=50)
    competitor_group: str | None = Field(default=None, max_length=100)

    @field_validator("term")
    @classmethod
    def strip_term(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("term must not be blank")
        return value

    @field_validator("variants")
    @classmethod
    def dedupe_variants(cls, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result = []
        for raw in values:
            cleaned = " ".join(raw.split())
            key = normalize_term(cleaned)
            if cleaned and key not in seen:
                seen.add(key)
                result.append(cleaned)
        return result


class TrackedEntityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    term: str
    entity_type: EntityType
    variants: list[str]
    competitor_group: str | None
    created_at: datetime


class WatchlistCreate(BaseModel):
    workspace_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    language: str = Field(default="en", min_length=2, max_length=16)


class WatchlistUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    language: str | None = Field(default=None, min_length=2, max_length=16)
    active: bool | None = None


class WatchlistRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    language: str
    active: bool
    created_at: datetime
    entities: list[TrackedEntityRead]
