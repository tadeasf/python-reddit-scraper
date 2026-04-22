"""Uniform spinner context manager backed by ``rich.status.Status``.

Usage::

    with spinner("Probing proxy accounts…"):
        result = slow_work()
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from python_reddit_scraper.log import log_console


@contextmanager
def spinner(message: str, *, spinner_style: str = "dots") -> Iterator[None]:
    """Show a spinner with *message* while the wrapped block runs.

    The spinner is automatically hidden when the block exits (success *or*
    exception), and on non-interactive stdout it degrades to a single
    ``message…`` line so piped invocations still surface progress.
    """
    if log_console.is_terminal:
        with log_console.status(f"[cyan]{message}", spinner=spinner_style):
            yield
    else:
        log_console.print(f"[cyan]{message}")
        yield
