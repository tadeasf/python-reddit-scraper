"""`download-reddit-media history` subcommand."""

from __future__ import annotations

from typing import Annotated

import typer

from python_reddit_scraper.history import filter_runs, history_path, load_runs
from python_reddit_scraper.ui.history_table import print_history


def history(
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Show at most this many runs (newest first)."),
    ] = 20,
    show_all: Annotated[
        bool,
        typer.Option("--all", help="Show every recorded run (overrides --limit)."),
    ] = False,
    since: Annotated[
        str | None,
        typer.Option(
            "--since",
            help="Filter to runs within the last duration, e.g. 30m, 12h, 7d.",
        ),
    ] = None,
) -> None:
    """Render past runs as a rich table."""
    runs = filter_runs(
        load_runs(),
        limit=None if show_all else limit,
        since=since,
    )
    print_history(runs, path=history_path())
