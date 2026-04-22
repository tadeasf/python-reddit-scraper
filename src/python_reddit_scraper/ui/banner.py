"""Startup banner: a single rich Rule with app name, version, mode, and target count."""

from __future__ import annotations

from rich.rule import Rule

from python_reddit_scraper import __app_name__, __version__
from python_reddit_scraper.log import log_console
from python_reddit_scraper.ui.theme import BORDER


def print_banner(mode: str, subreddit_count: int | None = None) -> None:
    """Print a one-line ``━━ app v1.1.1 • mode=live • 3 subs ━━`` rule."""
    parts = [f"{__app_name__} [bold]v{__version__}[/bold]", f"mode=[magenta]{mode}[/magenta]"]
    if subreddit_count is not None:
        parts.append(f"[cyan]{subreddit_count} sub{'s' if subreddit_count != 1 else ''}[/cyan]")
    title = f"[bold cyan] {' [bright_black]•[/bright_black] '.join(parts)} [/bold cyan]"
    log_console.print(Rule(title=title, style=BORDER, align="center"))
