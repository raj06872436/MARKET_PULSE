"""Check a running MarketPulse end to end: sign in, then the main journey on the first watchlist.

    python deploy/smoke.py https://marketpulse.example.com demo@marketpulse.local 'the-password'

Uses only the standard library, so it runs from any machine with Python 3.11+. Read-only apart from
refreshing the template insight cards. Exits non-zero on the first failed step.
"""

import http.cookiejar
import json
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta


def main(base: str, email: str, password: str) -> None:
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def call(method: str, path: str, body: dict | None = None, raw: bool = False):
        request = urllib.request.Request(
            base.rstrip("/") + path, method=method, data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json"} if body is not None else {},
        )
        try:
            with opener.open(request, timeout=60) as response:
                data = response.read()
        except urllib.error.HTTPError as exc:
            sys.exit(f"FAIL {method} {path}: {exc.code} {exc.read()[:200]!r}")
        return data if raw else json.loads(data or b"null")

    def step(name: str, ok: bool, detail: str = "") -> None:
        print(f"{'ok  ' if ok else 'FAIL'} {name}{': ' + detail if detail else ''}")
        if not ok:
            sys.exit(1)

    step("health", call("GET", "/api/health")["status"] == "ok")
    step("frontend served", b"<div id=\"root\">" in call("GET", "/", raw=True))
    step("sign in", call("POST", "/api/auth/login", {"email": email, "password": password})["email"] == email.lower())
    watchlists = call("GET", "/api/watchlists")
    step("watchlist", bool(watchlists), f"{len(watchlists)} found")
    wl = watchlists[0]
    span = call("GET", f"/api/watchlists/{wl['id']}/data-range")
    step("data collected", span["last"] is not None, f"{span['first']} to {span['last']}")
    end = date.fromisoformat(span["last"])
    start = (end - timedelta(days=27)).isoformat()
    trends = call("GET", f"/api/trends?watchlist_id={wl['id']}")
    step("trend cards", len(trends) == len(wl["entities"]), ", ".join(f"{t['term']} {t['score']}" for t in trends))
    posts = call("GET", f"/api/records?watchlist_id={wl['id']}&start={start}&end={end}&limit=5")
    step("posts", posts["total"] > 0, f"{posts['total']} in the last 28 days")
    forecasts = call("GET", f"/api/forecasts?watchlist_id={wl['id']}")
    step("forecasts", bool(forecasts), ", ".join(f"{f['term']} {f['status']}" for f in forecasts))
    insights = call("POST", "/api/insights/generate", {"watchlist_id": wl["id"], "use_llm": False})
    step("insights", bool(insights["insights"]), f"{len(insights['insights'])} cards")
    csv = call("GET", f"/api/export/daily.csv?watchlist_id={wl['id']}&start={start}&end={end}", raw=True).decode()
    step("export", csv.startswith("date,term"), f"{csv.count(chr(10)) - 1} rows")
    call("POST", "/api/auth/logout")
    print("All checks passed.")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
