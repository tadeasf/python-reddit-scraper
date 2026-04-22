"""Fetch Webshare proxy list with multi-account fallback and bandwidth-limit rotation."""

from __future__ import annotations

import requests
from loguru import logger

from python_reddit_scraper.config import WebshareAccount


class AllAccountsExhaustedError(Exception):
    """Raised when every configured Webshare account has hit its bandwidth limit."""


def fetch_proxies(api_key: str) -> list[dict]:
    """Fetch all *valid* proxies for one Webshare API key (auto-paginates).

    Returns Camoufox-ready dicts:
        {"server": "http://host:port", "username": "...", "password": "..."}

    Raises ``requests.HTTPError`` when the API signals an account-level problem
    (e.g. 401 invalid key, 402 payment required / bandwidth exceeded).
    Returns an empty list when the account is valid but has zero active proxies.
    """
    proxies: list[dict] = []
    url = "https://proxy.webshare.io/api/v2/proxy/list/?mode=direct&page=1&page_size=100"
    headers = {"Authorization": f"Token {api_key}"}

    while url:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        for p in data["results"]:
            if p["valid"]:
                proxies.append(
                    {
                        "server": f"http://{p['proxy_address']}:{p['port']}",
                        "username": p["username"],
                        "password": p["password"],
                    }
                )
        url = data.get("next")

    return proxies


def fetch_proxies_with_fallback(accounts: list[WebshareAccount]) -> list[dict]:
    """Try each account in order and return the first working proxy pool.

    "Working" means the API call succeeded *and* at least one valid proxy was
    returned.  An empty result is treated the same as an API error — both
    indicate the account has no usable proxies (quota exhausted, suspended, etc.)
    — so we skip to the next account.

    Raises:
        AllAccountsExhaustedError: when every account either errored or returned
            zero valid proxies, with a message listing how many accounts failed.
    """
    if not accounts:
        raise AllAccountsExhaustedError("No Webshare accounts found in config.")

    last_error: Exception | None = None

    for account in accounts:
        label = account.email
        try:
            proxies = fetch_proxies(account.api_key)
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            logger.warning(
                "Webshare {}: HTTP {} — skipping (bandwidth limit or invalid key)",
                label,
                status,
            )
            last_error = exc
            continue
        except Exception as exc:
            logger.warning("Webshare {}: unexpected error — {} — skipping", label, exc)
            last_error = exc
            continue

        if not proxies:
            logger.warning(
                "Webshare {}: returned 0 valid proxies — quota likely exhausted, skipping",
                label,
            )
            last_error = ValueError(f"{label} returned no valid proxies")
            continue

        logger.info("Webshare {}: {} proxies loaded", label, len(proxies))
        return proxies

    n = len(accounts)
    raise AllAccountsExhaustedError(
        f"All {n} Webshare account(s) have hit their bandwidth limit or returned no valid "
        f"proxies. Last error: {last_error}. "
        f"Either wait for your monthly quota to reset or add more accounts to "
        f"~/.config/python_reddit_scraper/config.yaml under providers[].accounts."
    )
