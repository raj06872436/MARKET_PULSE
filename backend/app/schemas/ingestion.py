import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

SourceStatus = Literal["not_connected", "never_run", "running", "ok", "degraded", "failed"]


class RunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    trigger: str
    status: str
    started_at: datetime
    ended_at: datetime | None
    window_start: datetime | None
    fetched_count: int | None
    inserted_count: int | None
    duplicate_count: int | None
    rejected_count: int | None
    matched_count: int | None
    error_code: str | None
    error_detail: str | None
    coverage_json: dict | None


class RowErrorRead(BaseModel):
    row: int
    column: str | None
    message: str


class CsvImportResult(BaseModel):
    run: RunRead
    errors: list[RowErrorRead]
    unknown_columns: list[str]


class SourceRead(BaseModel):
    source: str
    label: str
    kind: Literal["api", "csv"]
    enabled: bool
    policy_reviewed_at: datetime | None
    policy_notes: str | None
    status: SourceStatus
    last_run: RunRead | None
    last_success_at: datetime | None
    record_count: int
    notes: list[str]


class SourceUpdate(BaseModel):
    enabled: bool | None = None
    # Set true to record that the source's terms, quotas and retention rules were reviewed today.
    policy_reviewed: bool | None = None
    policy_notes: str | None = None
