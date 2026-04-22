"""Fetch Webshare proxy list and provide per-worker proxy assignment."""

from __future__ import annotations

import requests


def fetch_proxies(api_key: str) -> list[dict]:
    """Fetch all valid proxies from the Webshare API (auto-paginates).

    Returns a list of proxy dicts suitable for passing directly to Camoufox:
        {"server": "http://host:port", "username": "...", "password": "..."}
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
