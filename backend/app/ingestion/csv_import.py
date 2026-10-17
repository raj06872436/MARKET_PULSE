"""Parse and validate an uploaded CSV of records. See docs/csv-format.md for the format."""

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.connectors.base import NormalizedRecord

REQUIRED_COLUMNS = ("source_record_id", "published_at", "text")
ENGAGEMENT_COLUMNS = ("likes", "comments", "shares", "views")
OPTIONAL_COLUMNS = ("url", "language", *ENGAGEMENT_COLUMNS)
DATASET_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
EARLIEST = datetime(2000, 1, 1, tzinfo=UTC)
MAX_ERRORS_REPORTED = 50


class CsvFormatError(ValueError):
    """The file as a whole can't be read (encoding, header, size). Row problems are reported per row instead."""


@dataclass
class RowError:
    row: int
    column: str | None
    message: str


@dataclass
class ParsedCsv:
    records: list[NormalizedRecord] = field(default_factory=list)
    errors: list[RowError] = field(default_factory=list)
    rejected: int = 0
    unknown_columns: list[str] = field(default_factory=list)

    def reject(self, row: int, column: str | None, message: str) -> None:
        self.rejected += 1
        if len(self.errors) < MAX_ERRORS_REPORTED:
            self.errors.append(RowError(row, column, message))


def source_name(dataset: str) -> str:
    if not DATASET_PATTERN.fullmatch(dataset):
        raise CsvFormatError("Dataset name must be 1-48 lowercase letters, digits, '-' or '_'")
    return f"csv:{dataset}"


def parse_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise CsvFormatError(f"Unknown timezone '{name}'") from None


def _parse_timestamp(value: str, default_tz: ZoneInfo, now: datetime) -> datetime:
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=default_tz)
    parsed = parsed.astimezone(UTC)
    if parsed < EARLIEST or parsed > now + timedelta(days=1):
        raise ValueError("date is outside the plausible range")
    return parsed


def _parse_count(value: str) -> int | None:
    value = value.strip().replace(",", "")
    if value == "":
        return None
    count = int(value)
    if count < 0:
        raise ValueError("must not be negative")
    return count


def parse_csv(raw: bytes, dataset: str, default_tz: ZoneInfo, max_rows: int) -> ParsedCsv:
    source = source_name(dataset)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise CsvFormatError("File must be UTF-8 encoded") from None

    reader = csv.DictReader(io.StringIO(text))
    header = [h.strip() for h in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise CsvFormatError(f"Missing required column(s): {', '.join(missing)}")
    reader.fieldnames = header

    result = ParsedCsv(unknown_columns=[c for c in header if c not in REQUIRED_COLUMNS + OPTIONAL_COLUMNS])
    now = datetime.now(UTC)
    for row_number, row in enumerate(reader, start=2):
        if row_number - 1 > max_rows:
            raise CsvFormatError(f"File has more than {max_rows} rows; split it into smaller files")
        if None in row:
            result.reject(row_number, None, "row has more fields than the header")
            continue
        values = {k: (v or "").strip() for k, v in row.items()}

        record_id = values["source_record_id"]
        if not record_id:
            result.reject(row_number, "source_record_id", "is required")
            continue
        if not values["text"]:
            result.reject(row_number, "text", "is required")
            continue
        try:
            published_at = _parse_timestamp(values["published_at"], default_tz, now)
        except ValueError as exc:
            result.reject(row_number, "published_at", f"invalid timestamp ({exc})")
            continue

        engagement: dict[str, int] = {}
        bad_column = None
        for column in ENGAGEMENT_COLUMNS:
            if column not in values:
                continue
            try:
                count = _parse_count(values[column])
            except ValueError:
                bad_column = column
                break
            if count is not None:
                engagement[column] = count
        if bad_column:
            result.reject(row_number, bad_column, "must be a whole number of 0 or more")
            continue

        result.records.append(
            NormalizedRecord(
                source=source,
                source_record_id=record_id[:256],
                published_at=published_at,
                text=values["text"],
                permitted_url=values.get("url") or None,
                language=(values.get("language") or None),
                # Columns that are absent or blank stay out of the dict; no engagement at all is null, not zero.
                engagement=engagement or None,
            )
        )
    return result
