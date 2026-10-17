import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ModelVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task: str
    name: str
    version: str
    preprocessing_version: str | None
    status: str
    evaluation_json: dict | None
    created_at: datetime


class ScoringResult(BaseModel):
    model: ModelVersionRead
    scored: int
