"""Fetch Webshare proxy list with multi-account fallback and bandwidth-limit rotation."""

from __future__ import annotations

import requests
from loguru import logger


class AllAccountsExhaustedError(Exception):
    """Raised when every configured Webshare API key has hit its bandwidth limit."""


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


def fetch_proxies_with_fallback(api_keys: list[str]) -> list[dict]:
    """Try each API key in order and return the first working proxy pool.

    "Working" means the API call succeeded *and* at least one valid proxy was
    returned.  An empty result is treated the same as an API error — both
    indicate the account has no usable proxies (quota exhausted, suspended, etc.)
    — so we skip to the next key.

    Raises:
        AllAccountsExhaustedError: when every key either errored or returned
            zero valid proxies, with a message listing how many accounts failed.
    """
    if not api_keys:
        raise AllAccountsExhaustedError("No Webshare API keys found in config.")

    last_error: Exception | None = None

    for idx, key in enumerate(api_keys, start=1):
        key_label = f"account #{idx}"
        try:
            proxies = fetch_proxies(key)
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            logger.warning(
                "Webshare {}: HTTP {} — skipping (bandwidth limit or invalid key)",
                key_label,
                status,
            )
            last_error = exc
            continue
        except Exception as exc:
            logger.warning("Webshare {}: unexpected error — {} — skipping", key_label, exc)
            last_error = exc
            continue

        if not proxies:
            logger.warning(
                "Webshare {}: returned 0 valid proxies — quota likely exhausted, skipping",
                key_label,
            )
            last_error = ValueError(f"{key_label} returned no valid proxies")
            continue

        logger.info("Webshare {}: {} proxies loaded", key_label, len(proxies))
        return proxies

    n = len(api_keys)
    raise AllAccountsExhaustedError(
        f"All {n} Webshare account(s) have hit their bandwidth limit or returned no valid "
        f"proxies. Last error: {last_error}. "
        f"Either wait for your monthly quota to reset or add more API keys to "
        f"~/.config/python_reddit_scraper/config.yaml (api_key, api_key2, api_key3, ...)."
    )
