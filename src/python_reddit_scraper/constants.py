"""Shared constants: media type vocabulary and CLI defaults."""

from __future__ import annotations

ALL_MEDIA_TYPES: frozenset[str] = frozenset({"images", "videos", "gifs"})

DEFAULT_OUTPUT_DIR = "./redditdownloads"
DEFAULT_MAX_PAGES = 50
DEFAULT_WORKERS = 16
DEFAULT_SCRAPE_WORKERS = 1
