"""Bluesky connector using the documented app.bsky.feed.searchPosts endpoint.

Stores only the post text, timestamps, language, public URL and engagement counts.
No profile details are kept beyond the handle that is part of the public post URL.
"""

import logging
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

import httpx

from app.connectors.base import ConnectorError, ConnectorHealth, FetchCoverage, NormalizedRecord, SourceConnector
from app.core.config import Settings

logger = logging.getLogger(__name__)

PAGE_SIZE = 100
MAX_ATTEMPTS = 4
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


class BlueskyConnector(SourceConnector):
    name = "bluesky"
    version = "bluesky-1"

    def __init__(
        self,
        settings: Settings,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.settings = settings
        self.sleep = sleep
        self.client = httpx.Client(
            transport=transport,
            timeout=httpx.Timeout(15.0),
            headers={"User-Agent": "MarketPulse/0.1 (+https://github.com/raj06872436/MARKET_PULSE)"},
        )
        self._token: str | None = None

    @property
    def authenticated(self) -> bool:
        return bool(self.settings.bluesky_handle and self.settings.bluesky_app_password)

    def _base(self) -> str:
        return self.settings.bluesky_auth_base if self.authenticated else self.settings.bluesky_public_base

    def _login(self) -> None:
        response = self._request(
            "POST",
            f"{self.settings.bluesky_auth_base}/xrpc/com.atproto.server.createSession",
            json={"identifier": self.settings.bluesky_handle, "password": self.settings.bluesky_app_password},
        )
        try:
            self._token = response.json()["accessJwt"]
        except (ValueError, KeyError):
            raise ConnectorError("schema_invalid", "Bluesky sign-in response had no access token") from None

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        delay = 1.0
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = self.client.request(method, url, **kwargs)
            except httpx.TimeoutException:
                if attempt == MAX_ATTEMPTS:
                    raise ConnectorError("timeout", "Bluesky did not respond in time") from None
            except httpx.TransportError as exc:
                if attempt == MAX_ATTEMPTS:
                    raise ConnectorError("source_unavailable", f"Could not reach Bluesky ({type(exc).__name__})") from None
            else:
                if response.status_code < 400:
                    return response
                if response.status_code in (401, 403):
                    raise ConnectorError(
                        "auth_failed",
                        f"Bluesky refused the request (HTTP {response.status_code}). "
                        "Search may need a signed-in account: set BLUESKY_HANDLE and BLUESKY_APP_PASSWORD.",
                    )
                if response.status_code not in RETRYABLE_STATUS:
                    raise ConnectorError("source_unavailable", f"Bluesky returned HTTP {response.status_code}")
                if attempt == MAX_ATTEMPTS:
                    code = "rate_limited" if response.status_code == 429 else "source_unavailable"
                    raise ConnectorError(code, f"Bluesky returned HTTP {response.status_code} after {attempt} attempts")
                retry_after = response.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    delay = max(delay, min(float(retry_after), 60.0))
            logger.info("Bluesky request failed on attempt %d, retrying in %.0fs", attempt, delay)
            self.sleep(delay)
            delay *= 2
        raise AssertionError("unreachable")

    def _to_record(self, post: dict) -> NormalizedRecord | None:
        try:
            uri = post["uri"]
            record = post["record"]
            text = record["text"]
            created = _parse_time(record["createdAt"])
            indexed = _parse_time(post.get("indexedAt") or record["createdAt"])
        except (KeyError, TypeError, ValueError):
            return None
        # Clients can set createdAt freely; distrust timestamps well after the server saw the post.
        if created > indexed + timedelta(days=1):
            created = indexed
        handle = (post.get("author") or {}).get("handle")
        rkey = uri.rsplit("/", 1)[-1]
        engagement = {
            name: post[key]
            for name, key in (("likes", "likeCount"), ("comments", "replyCount"), ("shares", "repostCount"), ("quotes", "quoteCount"))
            if isinstance(post.get(key), int)
        }
        langs = record.get("langs") or []
        return NormalizedRecord(
            source=self.name,
            source_record_id=uri,
            published_at=created,
            text=text,
            permitted_url=f"https://bsky.app/profile/{handle}/post/{rkey}" if handle else None,
            language=langs[0] if langs and isinstance(langs[0], str) else None,
            engagement=engagement or None,
        )

    def fetch(self, terms: list[str], since: datetime | None, coverage: FetchCoverage) -> Iterator[NormalizedRecord]:
        if self.authenticated and self._token is None:
            self._login()
        headers = {"Authorization": f"Bearer {self._token}"} if self._token else {}
        queries = terms[: self.settings.bluesky_max_queries]
        coverage.skipped_queries = terms[self.settings.bluesky_max_queries :]

        for query in queries:
            coverage.queries.append(query)
            params: dict[str, str | int] = {"q": query, "sort": "latest", "limit": PAGE_SIZE}
            if since is not None:
                params["since"] = since.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            for page in range(self.settings.bluesky_max_pages):
                response = self._request(
                    "GET", f"{self._base()}/xrpc/app.bsky.feed.searchPosts", params=params, headers=headers
                )
                coverage.pages_fetched += 1
                try:
                    body = response.json()
                    posts = body["posts"]
                except (ValueError, KeyError):
                    raise ConnectorError("schema_invalid", "Bluesky search response was not in the expected format") from None
                for post in posts:
                    record = self._to_record(post)
                    if record is None:
                        coverage.schema_errors += 1
                    else:
                        yield record
                cursor = body.get("cursor")
                if not cursor or not posts:
                    break
                if page == self.settings.bluesky_max_pages - 1:
                    coverage.truncated_queries.append(query)
                    break
                params["cursor"] = cursor

    def health(self) -> ConnectorHealth:
        mode = "signed-in account" if self.authenticated else "public API, no sign-in"
        return ConnectorHealth(status="ok", notes=[f"Using the {mode}."])
