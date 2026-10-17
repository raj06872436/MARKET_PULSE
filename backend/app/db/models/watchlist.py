import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAt, JSONType, UUIDPk


class Watchlist(UUIDPk, CreatedAt, Base):
    __tablename__ = "watchlists"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    language: Mapped[str] = mapped_column(String(16), default="en")
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    workspace: Mapped["Workspace"] = relationship(back_populates="watchlists")  # noqa: F821
    entities: Mapped[list["TrackedEntity"]] = relationship(
        back_populates="watchlist", cascade="all, delete-orphan", passive_deletes=True, order_by="TrackedEntity.created_at"
    )


class TrackedEntity(UUIDPk, CreatedAt, Base):
    __tablename__ = "tracked_entities"
    __table_args__ = (UniqueConstraint("watchlist_id", "normalized_term"),)

    watchlist_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("watchlists.id", ondelete="CASCADE"), index=True)
    term: Mapped[str] = mapped_column(String(200))
    normalized_term: Mapped[str] = mapped_column(String(200))
    entity_type: Mapped[str] = mapped_column(String(32))
    variants: Mapped[list[str]] = mapped_column(JSONType, default=list)
    competitor_group: Mapped[str | None] = mapped_column(String(100))

    watchlist: Mapped[Watchlist] = relationship(back_populates="entities")


class Alert(UUIDPk, CreatedAt, Base):
    __tablename__ = "alerts"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tracked_entities.id", ondelete="CASCADE"), index=True)
    rule_json: Mapped[dict] = mapped_column(JSONType)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=1440)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class AlertEvent(UUIDPk, Base):
    """One firing of an alert rule. The data date is the collected day the rule was checked on."""

    __tablename__ = "alert_events"
    __table_args__ = (UniqueConstraint("alert_id", "data_date"),)

    alert_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("alerts.id", ondelete="CASCADE"), index=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_date: Mapped[date] = mapped_column(Date)
    value: Mapped[float] = mapped_column(Float)
    threshold: Mapped[float] = mapped_column(Float)
    message: Mapped[str] = mapped_column(Text)
