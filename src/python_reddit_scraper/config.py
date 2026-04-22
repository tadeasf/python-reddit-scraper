"""Load user configuration from ~/.config/python_reddit_scraper/config.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml

_CONFIG_PATH = Path.home() / ".config" / "python_reddit_scraper" / "config.yaml"


def load_config() -> dict:
    if not _CONFIG_PATH.exists():
        return {}
    with _CONFIG_PATH.open() as f:
        return yaml.safe_load(f) or {}


def get_webshare_api_keys() -> list[str]:
    """Return all configured Webshare API keys in order.

    Reads ``api_key``, ``api_key2``, ``api_key3``, ... from the config file.
    """
    cfg = load_config()
    keys: list[str] = []
    if v := cfg.get("api_key"):
        keys.append(v)
    i = 2
    while v := cfg.get(f"api_key{i}"):
        keys.append(v)
        i += 1
    return keys
