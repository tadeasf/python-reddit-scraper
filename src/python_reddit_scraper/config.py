"""Load user configuration from ~/.config/python_reddit_scraper/config.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from loguru import logger

_CONFIG_PATH = Path.home() / ".config" / "python_reddit_scraper" / "config.yaml"

ALL_MEDIA_TYPES: frozenset[str] = frozenset({"images", "videos", "gifs"})


@dataclass(frozen=True)
class Provider:
    """One proxy provider block from the config file.

    ``accounts`` holds the provider-specific raw dicts (shape differs per
    provider — see ``scraper.proxy_handler`` for how each is parsed).
    """

    name: str
    accounts: list[dict]


@dataclass(frozen=True)
class Defaults:
    """User-configured defaults for the download command.

    Each field is ``None`` when not configured, meaning the CLI should fall
    back to prompting the user (or to its built-in default).
    """

    media_types: tuple[str, ...] | None = None
    output_dir: str | None = None
    max_pages: int | None = None
    workers: int | None = None
    scrape_workers: int | None = None


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


def get_defaults() -> Defaults:
    """Return user-configured defaults from the ``defaults:`` block, if any."""
    cfg = load_config()
    raw = cfg.get("defaults") or {}

    media_types: tuple[str, ...] | None = None
    raw_mt = raw.get("media_types")
    if raw_mt is not None:
        if isinstance(raw_mt, str):
            raw_mt = [raw_mt]
        valid = [m for m in raw_mt if m in ALL_MEDIA_TYPES]
        invalid = [m for m in raw_mt if m not in ALL_MEDIA_TYPES]
        if invalid:
            logger.warning(
                "Ignoring unknown media_types in config: {}. Valid values: {}.",
                ", ".join(invalid),
                ", ".join(sorted(ALL_MEDIA_TYPES)),
            )
        media_types = tuple(valid) if valid else None

    output_dir = raw.get("output_dir")
    if output_dir is not None and not isinstance(output_dir, str):
        logger.warning("Ignoring non-string output_dir in config.")
        output_dir = None

    def _positive_int(key: str) -> int | None:
        val = raw.get(key)
        if val is None:
            return None
        try:
            parsed = int(val)
            if parsed <= 0:
                raise ValueError
        except (TypeError, ValueError):
            logger.warning("Ignoring invalid {} in config: {!r}", key, val)
            return None
        return parsed

    max_pages = _positive_int("max_pages")
    workers = _positive_int("workers")
    scrape_workers = _positive_int("scrape_workers")

    return Defaults(
        media_types=media_types,
        output_dir=output_dir,
        max_pages=max_pages,
        workers=workers,
        scrape_workers=scrape_workers,
    )


def save_defaults(defaults: Defaults) -> Path:
    """Merge *defaults* into the config file, preserving other top-level keys.

    Only fields that are not ``None`` are written, so partial configs stay
    partial. Returns the path that was written.
    """
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    cfg = load_config()

    block = dict(cfg.get("defaults") or {})
    if defaults.media_types is not None:
        block["media_types"] = list(defaults.media_types)
    if defaults.output_dir is not None:
        block["output_dir"] = defaults.output_dir
    if defaults.max_pages is not None:
        block["max_pages"] = defaults.max_pages
    if defaults.workers is not None:
        block["workers"] = defaults.workers
    if defaults.scrape_workers is not None:
        block["scrape_workers"] = defaults.scrape_workers
    cfg["defaults"] = block

    with _CONFIG_PATH.open("w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)
    return _CONFIG_PATH
