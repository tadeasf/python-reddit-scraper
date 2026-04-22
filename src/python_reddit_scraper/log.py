"""Loguru logging configuration for the Reddit media downloader."""

from loguru import logger
from rich.console import Console

_console = Console()

log_console = _console


def _rich_sink(message: str) -> None:
    _console.print(message, end="", highlight=False, markup=False)


logger.remove()

logger.add(
    _rich_sink,
    format="{time:HH:mm:ss} | {level: <8} | {message}",
    level="INFO",
    colorize=False,
)
