"""In-process rate limits for expensive or abusable endpoints.

A sliding window per (rule, key). This is per process: with several API workers each keeps its own
counts, so the effective limit is the per-process limit times the number of workers. That is enough
for one container; a shared store such as Redis is the step up when running more.
"""

import math
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import HTTPException, Request, status


@dataclass(frozen=True)
class Rule:
    name: str
    limit: int
    window_seconds: int


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, rule: Rule, key: str) -> float | None:
        """Record a hit. Returns seconds to wait if the limit is exceeded, else None."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[(rule.name, key)]
            while hits and hits[0] <= now - rule.window_seconds:
                hits.popleft()
            if len(hits) >= rule.limit:
                return hits[0] + rule.window_seconds - now
            hits.append(now)
            return None

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()

LOGIN = Rule("login", 10, 15 * 60)
REGISTER = Rule("register", 5, 60 * 60)
IMPORT = Rule("import", 10, 60)
FORECAST = Rule("forecast", 20, 60)
INSIGHTS = Rule("insights", 10, 60)
INSIGHTS_LLM = Rule("insights_llm", 5, 60 * 60)
ANALYSIS = Rule("analysis", 5, 60)
SYNC = Rule("sync", 5, 60)
EXPORT = Rule("export", 30, 60)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce(rule: Rule, key: str) -> None:
    wait = limiter.check(rule, key)
    if wait is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many requests. Try again in {max(1, math.ceil(wait))} seconds.",
            headers={"Retry-After": str(max(1, math.ceil(wait)))},
        )
