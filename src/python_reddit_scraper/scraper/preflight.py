"""Subreddit preflight: probe /r/{sub}/about.json before committing to a scrape.

Catches typos, private, and banned subreddits cheaply so we don't burn time
and proxy quota on invalid targets. One HTTP request per sub, ran in parallel
via a small thread pool.

Reddit aggressively 403s pure-``urllib`` traffic from Python processes
regardless of User-Agent, so when a proxy pool is available we route the probe
through a randomly-picked entry. When a probe can't be verified (403, network
error) we mark it ``ok=True`` with status ``unverified`` — the main scrape
(which uses camoufox + proxies) will catch truly-bad subs. Only confirmed
404 / banned / quarantined subs are blocked at preflight time.
"""

from __future__ import annotations

import json
import random
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0"
    ),
    "Accept": "application/json",
}
_TIMEOUT = 15
_MAX_WORKERS = 8


@dataclass(frozen=True)
class PreflightResult:
    """Outcome of a single /r/{sub}/about.json probe.

    ``ok`` is ``True`` when the sub either verified as public *or* could not be
    verified (so the scrape should still proceed). Only confirmed-bad statuses
    (``not_found``, ``banned``, ``quarantined``) set ``ok=False``.
    """

    sub: str
    ok: bool
    status: str
    subscribers: int | None = None
    nsfw: bool | None = None
    note: str = ""


def preflight(
    subs: list[str],
    *,
    proxies: list[dict] | None = None,
) -> list[PreflightResult]:
    """Probe every subreddit in *subs* and return results in the original order.

    When *proxies* is provided, each probe goes through a randomly-picked
    entry so Reddit's aggressive blocking of Python-native traffic can be
    bypassed.
    """
    if not subs:
        return []
    pool_size = min(_MAX_WORKERS, len(subs))
    with ThreadPoolExecutor(max_workers=pool_size) as pool:
        results = list(pool.map(lambda s: _probe_one(s, proxies), subs))
    return results


def _probe_one(sub: str, proxies: list[dict] | None) -> PreflightResult:
    url = f"https://old.reddit.com/r/{sub}/about.json"
    req = Request(url, headers=_HEADERS)
    opener = _build_opener(proxies)
    try:
        with opener.open(req, timeout=_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except HTTPError as exc:
        return _from_http_error(sub, exc)
    except URLError as exc:
        return PreflightResult(sub, True, "unverified", note=f"network: {exc.reason}")
    except (OSError, TimeoutError) as exc:
        return PreflightResult(sub, True, "unverified", note=f"timeout: {exc}")
    except json.JSONDecodeError:
        return PreflightResult(sub, True, "unverified", note="unexpected response body")

    data = (payload or {}).get("data") or {}
    kind = (payload or {}).get("kind")

    if kind != "t5":
        return PreflightResult(sub, False, "not_found", note="no subreddit metadata")

    if data.get("quarantine"):
        return PreflightResult(sub, False, "quarantined", note="requires opt-in")

    return PreflightResult(
        sub=sub,
        ok=True,
        status="public",
        subscribers=_coerce_int(data.get("subscribers")),
        nsfw=bool(data.get("over18")),
    )


def _build_opener(proxies: list[dict] | None):
    """Return a urllib opener routed through a random proxy when available."""
    if not proxies:
        return _DEFAULT_OPENER
    picked = random.choice(proxies)
    server = picked.get("server")
    if not server:
        return _DEFAULT_OPENER
    user = picked.get("username")
    pw = picked.get("password")
    auth = f"{user}:{pw}@" if user and pw else ""
    netloc = server.replace("http://", "").replace("https://", "")
    proxy_url = f"http://{auth}{netloc}"
    handler = ProxyHandler({"http": proxy_url, "https": proxy_url})
    return build_opener(handler)


def _from_http_error(sub: str, exc: HTTPError) -> PreflightResult:
    code = exc.code
    # Reddit frequently 403s raw Python clients even for public subs; treat as
    # unverified rather than confirmed-private so the main scrape gets a shot.
    if code == 403:
        return PreflightResult(sub, True, "unverified", note="HTTP 403 — scrape will verify")
    if code == 404:
        return PreflightResult(sub, False, "not_found", note="doesn't exist")
    if code == 451:
        return PreflightResult(sub, False, "banned", note="legally unavailable")
    if code == 429:
        return PreflightResult(sub, True, "unverified", note="rate-limited, scrape will retry")
    return PreflightResult(sub, True, "unverified", note=f"HTTP {code}")


def _coerce_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


_DEFAULT_OPENER = build_opener()
