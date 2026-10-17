from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime


class ConnectorError(Exception):
    """A source-side failure. `code` is stored on the run so the UI can say what went wrong.

    Codes: not_configured, auth_failed, rate_limited, quota_exhausted, source_unavailable,
    timeout, schema_invalid.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class FetchCoverage:
    """What a fetch actually covered, so incomplete coverage is never mistaken for low volume."""

    queries: list[str] = field(default_factory=list)
    skipped_queries: list[str] = field(default_factory=list)
    truncated_queries: list[str] = field(default_factory=list)
    pages_fetched: int = 0
    schema_errors: int = 0

    @property
    def complete(self) -> bool:
        return not (self.skipped_queries or self.truncated_queries or self.schema_errors)


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
    version: str

    @abstractmethod
    def fetch(self, terms: list[str], since: datetime | None, coverage: FetchCoverage) -> Iterator[NormalizedRecord]:
        """Yield records published after `since` that match any of `terms`.

        Record what was and wasn't searched in `coverage`. Raise ConnectorError on source failures;
        records already yielded are kept.
        """

    @abstractmethod
    def health(self) -> ConnectorHealth:
        """Report connection status, quota and the last error, so failures never read as zero mentions."""
