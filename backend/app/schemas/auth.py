import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.security import MIN_PASSWORD_LENGTH


def _email(value: str) -> str:
    value = value.strip().lower()
    local, _, domain = value.partition("@")
    if not local or "." not in domain or " " in value:
        raise ValueError("Enter a valid email address")
    return value


class Credentials(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=200)

    _normalize = field_validator("email")(lambda cls, v: _email(v))


class Registration(Credentials):
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=200)


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    created_at: datetime
