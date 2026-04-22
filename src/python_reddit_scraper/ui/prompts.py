"""Interactive prompts built on prompt_toolkit.

PR 1 keeps the plain-text surface unchanged — styling, completers, and
validators land in PR 2. Only two structural changes here:

1. prompt_toolkit imports are hoisted to module scope (it is a required dep).
2. The numeric prompts now share a single ``_prompt_positive_int`` helper.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

import typer
from loguru import logger
from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import checkboxlist_dialog

from python_reddit_scraper.constants import ALL_MEDIA_TYPES

if TYPE_CHECKING:
    from python_reddit_scraper.config import Provider


def _require_tty(what: str) -> None:
    """Bail out with a clear message when a prompt would run on a non-TTY."""
    if not sys.stdin.isatty():
        logger.error(
            "No TTY available for {} prompt. Pass the relevant flag, or run "
            "`download-reddit-media configure` once on an interactive shell "
            "to save defaults.",
            what,
        )
        raise typer.Exit(1)


def choose_provider(providers: list[Provider]) -> Provider:
    """Return the single provider, or prompt the user to pick when there are several."""
    if len(providers) == 1:
        return providers[0]

    print("Available proxy providers:")
    for i, p in enumerate(providers, 1):
        suffix = "s" if len(p.accounts) != 1 else ""
        print(f"  {i}) {p.name} ({len(p.accounts)} account{suffix})")

    while True:
        raw = prompt(f"Choose [1-{len(providers)}]: ").strip()
        try:
            idx = int(raw)
        except ValueError:
            logger.warning("Enter a number between 1 and {}.", len(providers))
            continue
        if 1 <= idx <= len(providers):
            return providers[idx - 1]
        logger.warning("Out of range. Enter a number between 1 and {}.", len(providers))


def prompt_subreddits() -> list[str]:
    """Interactively prompt for subreddit names using prompt-toolkit."""
    _require_tty("subreddits")
    raw = prompt("Enter subreddits (comma-separated): ")
    subs = [s.strip().lstrip("r/") for s in raw.split(",") if s.strip()]
    if not subs:
        logger.error("No subreddits provided. Exiting.")
        raise typer.Exit(1)
    return subs


def prompt_media_types(default: set[str] | frozenset[str] | None = None) -> frozenset[str]:
    """Prompt for media types via a checkbox dialog (space toggle, enter confirm).

    Cancelling the dialog or confirming with nothing selected exits with code 1.
    """
    _require_tty("media types")
    preselected = list(default) if default else list(ALL_MEDIA_TYPES)
    values = [
        ("images", "Images (.jpg/.jpeg/.png/.webp)"),
        ("videos", "Videos (.mp4/.webm/.mov)"),
        ("gifs", "GIFs / animations (.gif)"),
    ]
    selection = checkboxlist_dialog(
        title="Media types",
        text="Space toggles, Enter confirms.",
        values=values,
        default_values=preselected,
    ).run()
    if not selection:
        logger.error("No media types selected. Exiting.")
        raise typer.Exit(1)
    return frozenset(selection)


def prompt_output_dir(default: str) -> str:
    """Prompt for an output directory; empty input returns *default*."""
    _require_tty("output directory")
    raw = prompt(f"Output directory [{default}]: ").strip()
    return os.path.expanduser(raw) if raw else default


def prompt_max_pages(default: int) -> int:
    return _prompt_positive_int("Max pages per subreddit", default, "max pages")


def prompt_workers(default: int) -> int:
    return _prompt_positive_int("Parallel download threads", default, "download workers")


def prompt_scrape_workers(default: int) -> int:
    return _prompt_positive_int(
        "Parallel scraper processes (1 = sequential)", default, "scrape workers"
    )


def _prompt_positive_int(label: str, default: int, what: str) -> int:
    _require_tty(what)
    while True:
        raw = prompt(f"{label} [{default}]: ").strip()
        if not raw:
            return default
        try:
            val = int(raw)
        except ValueError:
            logger.warning("Enter a positive integer.")
            continue
        if val <= 0:
            logger.warning("Must be greater than zero.")
            continue
        return val
