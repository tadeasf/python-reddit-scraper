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


def get_webshare_api_key() -> str | None:
    return load_config().get("api_key")
