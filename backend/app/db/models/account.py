import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAt, JSONType, UUIDPk


class User(UUIDPk, CreatedAt, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    # scrypt hash with its own parameters and salt (app/core/security.py). Never the password itself.
    password_hash: Mapped[str | None] = mapped_column(String(255))
    # "admin" can change installation-wide settings such as sources; "member" works in their own workspaces.
    role: Mapped[str] = mapped_column(String(16), default="member", server_default="member")


class UserSession(UUIDPk, CreatedAt, Base):
    """A signed-in browser. Only a SHA-256 of the cookie token is stored, so a database leak can't sign anyone in."""

    __tablename__ = "user_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Workspace(UUIDPk, CreatedAt, Base):
    __tablename__ = "workspaces"

    # Every workspace created through the API has an owner; only the owner can read or change it.
    # Nullable so rows created before sign-in existed survive the upgrade (see docs/security.md).
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))

    watchlists: Mapped[list["Watchlist"]] = relationship(  # noqa: F821
        back_populates="workspace", cascade="all, delete-orphan", passive_deletes=True
    )


class AuditEvent(UUIDPk, Base):
    __tablename__ = "audit_events"

    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONType)
