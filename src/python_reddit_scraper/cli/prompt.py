"""Interactive prompts and environment checks for the CLI."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer
from loguru import logger

if TYPE_CHECKING:
    from python_reddit_scraper.config import Provider


def choose_provider(providers: list[Provider]) -> Provider:
    """Return the single provider, or prompt the user to pick when there are several."""
    if len(providers) == 1:
        return providers[0]

    from prompt_toolkit import prompt

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
    from prompt_toolkit import prompt

    raw = prompt("Enter subreddits (comma-separated): ")
    subs = [s.strip().lstrip("r/") for s in raw.split(",") if s.strip()]
    if not subs:
        logger.error("No subreddits provided. Exiting.")
        raise typer.Exit(1)
    return subs


def check_camoufox_binary() -> None:
    """Check if the camoufox Firefox binary is installed."""
    try:
        from camoufox.pkgman import installed_verstr

        ver = installed_verstr()
        if not ver:
            raise FileNotFoundError
    except Exception:
        logger.error(
            "Camoufox browser not found. Run this command first:\n\n"
            "    rye run camoufox fetch\n\n"
            "This downloads the stealth Firefox binary (~80 MB, one-time setup)."
        )
        raise typer.Exit(1) from None
