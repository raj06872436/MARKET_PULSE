import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAt, JSONType, UUIDPk


class User(UUIDPk, CreatedAt, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True)
    status: Mapped[str] = mapped_column(String(32), default="active")


class Workspace(UUIDPk, CreatedAt, Base):
    __tablename__ = "workspaces"

    # Nullable until authentication lands; every workspace will then have an owner.
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
