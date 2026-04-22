"""Loguru logging configuration for the Reddit media downloader.

Loguru renders level-coloured output into a shared :class:`rich.console.Console`
so log lines, spinners, panels, and progress bars all share one stream and one
theme. The format is kept in :mod:`python_reddit_scraper.ui.theme` so the
palette can evolve in one place.
"""

from __future__ import annotations

from loguru import logger
from rich.console import Console

_console = Console()
log_console = _console


def _rich_sink(message: str) -> None:
    _console.print(message, end="", highlight=False, markup=False)


logger.remove()
logger.add(
    _rich_sink,
    format=("<dim>{time:HH:mm:ss}</dim> <level>{level: <8}</level> <dim>│</dim> {message}"),
    level="INFO",
    colorize=True,
)
