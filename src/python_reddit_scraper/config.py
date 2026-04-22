"""Load user configuration from ~/.config/python_reddit_scraper/config.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

_CONFIG_PATH = Path.home() / ".config" / "python_reddit_scraper" / "config.yaml"


@dataclass(frozen=True)
class WebshareAccount:
    email: str
    api_key: str


def load_config() -> dict:
    if not _CONFIG_PATH.exists():
        return {}
    with _CONFIG_PATH.open() as f:
        return yaml.safe_load(f) or {}


def get_webshare_accounts() -> list[WebshareAccount]:
    """Return all configured Webshare accounts in order.

    Reads ``providers[].accounts[]`` entries where ``name == "webshare"`` from
    the YAML config file.
    """
    cfg = load_config()
    for provider in cfg.get("providers") or []:
        if provider.get("name") == "webshare":
            return [
                WebshareAccount(email=a["email"], api_key=a["api_key"])
                for a in provider.get("accounts") or []
            ]
    return []
