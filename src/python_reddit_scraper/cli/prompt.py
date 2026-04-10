"""Interactive prompts and environment checks for the CLI."""

import typer
from loguru import logger


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
