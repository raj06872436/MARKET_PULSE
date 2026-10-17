from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class NormalizedRecord:
    """The common shape every connector emits, before matching and storage."""

    source: str
    source_record_id: str
    published_at: datetime
    text: str | None
    permitted_url: str | None = None
    language: str | None = None
    # None means "not provided by the source", which is different from zero.
    engagement: dict[str, int] | None = None
    raw_reference: str | None = None


@dataclass
class ConnectorHealth:
    status: str  # "ok" | "degraded" | "failed" | "disabled"
    last_success_at: datetime | None = None
    quota_remaining: int | None = None
    error_code: str | None = None
    notes: list[str] = field(default_factory=list)


class SourceConnector(ABC):
    """Adapter for one approved data source.

    Add a connector only after its API access, permitted use, quotas, retention
    and display requirements have been checked and recorded.
    """

    name: str

    @abstractmethod
    def fetch(self, terms: list[str], since: datetime | None) -> Iterator[NormalizedRecord]:
        """Yield records published after `since` that match any of `terms`."""

    @abstractmethod
    def health(self) -> ConnectorHealth:
        """Report connection status, quota and the last error, so failures never read as zero mentions."""
