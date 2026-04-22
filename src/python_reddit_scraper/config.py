"""Load user configuration from ~/.config/python_reddit_scraper/config.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

_CONFIG_PATH = Path.home() / ".config" / "python_reddit_scraper" / "config.yaml"


@dataclass(frozen=True)
class Provider:
    """One proxy provider block from the config file.

    ``accounts`` holds the provider-specific raw dicts (shape differs per
    provider — see ``scraper.proxy_handler`` for how each is parsed).
    """

    name: str
    accounts: list[dict]


def load_config() -> dict:
    if not _CONFIG_PATH.exists():
        return {}
    with _CONFIG_PATH.open() as f:
        return yaml.safe_load(f) or {}


def get_providers() -> list[Provider]:
    """Return all configured proxy providers in the order they appear in YAML."""
    cfg = load_config()
    return [
        Provider(name=p["name"], accounts=list(p.get("accounts") or []))
        for p in (cfg.get("providers") or [])
    ]
