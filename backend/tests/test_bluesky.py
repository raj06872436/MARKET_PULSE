import json
from datetime import UTC, datetime

import httpx
import pytest

from app.connectors.base import ConnectorError, FetchCoverage
from app.connectors.bluesky import BlueskyConnector
from app.core.config import Settings


def post(n: int, text="Redmi Note 14 review", **overrides):
    data = {
        "uri": f"at://did:plc:abc/app.bsky.feed.post/{n}",
        "cid": f"cid{n}",
        "author": {"did": "did:plc:abc", "handle": "alice.bsky.social", "displayName": "Alice"},
        "record": {"$type": "app.bsky.feed.post", "text": text, "createdAt": "2026-10-01T10:00:00.000Z", "langs": ["en"]},
        "indexedAt": "2026-10-01T10:00:01.000Z",
        "likeCount": 5,
        "replyCount": 1,
        "repostCount": 0,
    }
    data.update(overrides)
    return data


def make(handler, **settings):
    sleeps: list[float] = []
    connector = BlueskyConnector(
        Settings(bluesky_max_pages=3, **settings), transport=httpx.MockTransport(handler), sleep=sleeps.append
    )
    return connector, sleeps


def test_maps_posts_without_profile_details():
    def handler(request):
        return httpx.Response(200, json={"posts": [post(1)]})

    connector, _ = make(handler)
    [record] = list(connector.fetch(["Redmi Note 14"], None, FetchCoverage()))
    assert record.source == "bluesky"
    assert record.source_record_id == "at://did:plc:abc/app.bsky.feed.post/1"
    assert record.permitted_url == "https://bsky.app/profile/alice.bsky.social/post/1"
    assert record.published_at == datetime(2026, 10, 1, 10, tzinfo=UTC)
    assert record.language == "en"
    # quoteCount was absent, so it is left out rather than reported as zero.
    assert record.engagement == {"likes": 5, "comments": 1, "shares": 0}
    assert "Alice" not in repr(record)


def test_follows_cursor_and_sends_since():
    seen = []

    def handler(request):
        seen.append(dict(request.url.params))
        if "cursor" not in request.url.params:
            return httpx.Response(200, json={"posts": [post(1)], "cursor": "c1"})
        return httpx.Response(200, json={"posts": [post(2)]})

    connector, _ = make(handler)
    coverage = FetchCoverage()
    records = list(connector.fetch(["poco"], datetime(2026, 10, 1, tzinfo=UTC), coverage))
    assert len(records) == 2
    assert seen[0]["since"] == "2026-10-01T00:00:00.000Z"
    assert seen[0]["sort"] == "latest"
    assert seen[1]["cursor"] == "c1"
    assert coverage.complete and coverage.pages_fetched == 2


def test_page_cap_marks_coverage_incomplete():
    counter = iter(range(100))

    def handler(request):
        return httpx.Response(200, json={"posts": [post(next(counter))], "cursor": "more"})

    connector, _ = make(handler)
    coverage = FetchCoverage()
    assert len(list(connector.fetch(["poco"], None, coverage))) == 3
    assert coverage.truncated_queries == ["poco"]
    assert not coverage.complete


def test_query_cap_records_skipped_terms():
    connector, _ = make(lambda r: httpx.Response(200, json={"posts": []}), bluesky_max_queries=1)
    coverage = FetchCoverage()
    list(connector.fetch(["a", "b", "c"], None, coverage))
    assert coverage.queries == ["a"]
    assert coverage.skipped_queries == ["b", "c"]


def test_retries_rate_limits_with_backoff():
    responses = iter([httpx.Response(429, headers={"Retry-After": "3"}), httpx.Response(503), httpx.Response(200, json={"posts": [post(1)]})])
    connector, sleeps = make(lambda r: next(responses))
    assert len(list(connector.fetch(["poco"], None, FetchCoverage()))) == 1
    assert sleeps == [3.0, 6.0]


def test_gives_up_after_repeated_rate_limits():
    connector, sleeps = make(lambda r: httpx.Response(429))
    with pytest.raises(ConnectorError) as exc:
        list(connector.fetch(["poco"], None, FetchCoverage()))
    assert exc.value.code == "rate_limited"
    assert len(sleeps) == 3


def test_forbidden_is_reported_as_auth_failure():
    connector, sleeps = make(lambda r: httpx.Response(403))
    with pytest.raises(ConnectorError) as exc:
        list(connector.fetch(["poco"], None, FetchCoverage()))
    assert exc.value.code == "auth_failed"
    assert sleeps == []


def test_network_failure_is_source_unavailable():
    def handler(request):
        raise httpx.ConnectError("boom")

    connector, _ = make(handler)
    with pytest.raises(ConnectorError) as exc:
        list(connector.fetch(["poco"], None, FetchCoverage()))
    assert exc.value.code == "source_unavailable"


def test_malformed_posts_are_counted_not_fatal():
    broken = post(2)
    del broken["record"]["createdAt"]
    connector, _ = make(lambda r: httpx.Response(200, json={"posts": [post(1), broken]}))
    coverage = FetchCoverage()
    assert len(list(connector.fetch(["poco"], None, coverage))) == 1
    assert coverage.schema_errors == 1


def test_unexpected_response_shape_fails_the_run():
    connector, _ = make(lambda r: httpx.Response(200, json={"feed": []}))
    with pytest.raises(ConnectorError) as exc:
        list(connector.fetch(["poco"], None, FetchCoverage()))
    assert exc.value.code == "schema_invalid"


def test_future_created_at_falls_back_to_indexed_time():
    p = post(1)
    p["record"]["createdAt"] = "2030-01-01T00:00:00Z"
    connector, _ = make(lambda r: httpx.Response(200, json={"posts": [p]}))
    [record] = list(connector.fetch(["poco"], None, FetchCoverage()))
    assert record.published_at == datetime(2026, 10, 1, 10, 0, 1, tzinfo=UTC)


def test_signs_in_when_credentials_are_set():
    calls = []

    def handler(request):
        calls.append((request.method, request.url.host, request.url.path, request.headers.get("authorization")))
        if request.url.path.endswith("createSession"):
            assert json.loads(request.content) == {"identifier": "me.bsky.social", "password": "app-pass"}
            return httpx.Response(200, json={"accessJwt": "token123"})
        return httpx.Response(200, json={"posts": []})

    connector, _ = make(handler, bluesky_handle="me.bsky.social", bluesky_app_password="app-pass")
    list(connector.fetch(["poco"], None, FetchCoverage()))
    assert calls[0][:3] == ("POST", "bsky.social", "/xrpc/com.atproto.server.createSession")
    assert calls[1] == ("GET", "bsky.social", "/xrpc/app.bsky.feed.searchPosts", "Bearer token123")
