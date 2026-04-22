"""Typer-decorated entry points for the Reddit media downloader.

This module is intentionally thin: each command parses its arguments and
delegates straight to a flow in ``python_reddit_scraper.cli.flows``.
"""

from __future__ import annotations

from typing import Annotated

import typer


def _version_callback(value: bool) -> None:
    if value:
        from python_reddit_scraper import __app_name__, __version__

        print(f"{__app_name__} {__version__}")
        raise typer.Exit()


def download(
    subreddits: Annotated[
        str | None,
        typer.Option(
            "--subreddits",
            "-s",
            help="Comma-separated subreddit names (e.g. 'buildapc,dataengineering').",
        ),
    ] = None,
    output_dir: Annotated[
        str | None,
        typer.Option(
            "--output-dir",
            "-o",
            help="Base directory for downloaded files. "
            "If omitted, uses the value from config.yaml or prompts interactively.",
        ),
    ] = None,
    save_json: Annotated[
        bool,
        typer.Option(
            "--save-json", help="Save scraped JSON to ./input/{subreddit}/ for later reuse."
        ),
    ] = False,
    max_pages: Annotated[
        int | None,
        typer.Option(
            "--max-pages",
            help="Max pages to scrape per subreddit (100 posts/page). "
            "If omitted, uses the value from config.yaml or prompts interactively.",
        ),
    ] = None,
    workers: Annotated[
        int | None,
        typer.Option(
            "--workers",
            "-w",
            help="Number of parallel download threads. "
            "If omitted, uses the value from config.yaml (default: 16).",
        ),
    ] = None,
    scrape_workers: Annotated[
        int | None,
        typer.Option(
            "--scrape-workers",
            "-sw",
            help="Max parallel camoufox scraper processes. "
            "If omitted, uses the value from config.yaml (default: 1).",
        ),
    ] = None,
    resume: Annotated[
        bool,
        typer.Option("--resume", help="Resume the most recent interrupted download session."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Scrape and list what would be downloaded; do not write any files.",
        ),
    ] = False,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            help="Show version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Download media from Reddit subreddits."""
    if resume:
        from python_reddit_scraper.cli.flows.resume import run_resume

        run_resume(workers)
        return

    from python_reddit_scraper.cli.flows.live import run_live

    run_live(
        subreddits=subreddits,
        output_dir=output_dir,
        save_json=save_json,
        max_pages=max_pages,
        workers=workers,
        scrape_workers=scrape_workers,
        dry_run=dry_run,
    )
