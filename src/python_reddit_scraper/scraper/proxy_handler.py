"""Load proxy pools for each supported provider with per-account fallback."""

from __future__ import annotations

from dataclasses import dataclass

import requests
from loguru import logger

from python_reddit_scraper.config import Provider


class AllAccountsExhaustedError(Exception):
    """Raised when every configured account for the chosen provider is unusable."""


@dataclass(frozen=True)
class WebshareAccount:
    email: str
    api_key: str


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
    """Try each Webshare account in order and return the first working proxy pool.

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


def _load_webshare(accounts: list[dict]) -> list[dict]:
    parsed = [WebshareAccount(email=a["email"], api_key=a["api_key"]) for a in accounts]
    return fetch_proxies_with_fallback(parsed)


def _load_proxy_cheap(accounts: list[dict]) -> list[dict]:
    """Materialize proxy-cheap accounts into Camoufox-ready proxy dicts.

    Each account is already a single proxy endpoint (no API call needed).
    Only HTTP proxies are supported — Camoufox is built on Playwright's
    Firefox, which does not support authenticated SOCKS5 proxies
    (Playwright raises ``Browser does not support socks5 proxy authentication``
    on launch). A leftover ``protocol`` field in the config is ignored with a
    warning so existing setups keep working while the user updates their YAML.

    Returns the full list so workers can distribute them round-robin.
    """
    if not accounts:
        raise AllAccountsExhaustedError("No proxy-cheap accounts found in config.")

    proxies: list[dict] = []
    for acct in accounts:
        protocol = acct.get("protocol")
        if protocol is not None and str(protocol).lower() != "http":
            logger.warning(
                "proxy-cheap {}:{}: `protocol: {}` is ignored — only HTTP is "
                "supported (Camoufox/Firefox cannot authenticate SOCKS5). "
                "Using HTTP.",
                acct["ip_address"],
                acct["port"],
                protocol,
            )

        label = f"{acct['ip_address']}:{acct['port']}"
        proxies.append(
            {
                "server": f"http://{label}",
                "username": acct["username"],
                "password": acct["password"],
            }
        )
        logger.info("proxy-cheap {}: loaded", label)
    return proxies


def load_proxies_for_provider(provider: Provider) -> list[dict]:
    """Dispatch to the right loader for the given provider name."""
    if provider.name == "webshare":
        return _load_webshare(provider.accounts)
    if provider.name == "proxy-cheap":
        return _load_proxy_cheap(provider.accounts)
    raise ValueError(f"Unknown proxy provider: {provider.name!r}")
