"""
Typer application entry point for the Reddit media downloader.

Creates the Typer app instance and registers the CLI commands.
"""

import sys

import typer

import python_reddit_scraper.log  # noqa: F401 — configure logging on import
from python_reddit_scraper.cli.commands import download
from python_reddit_scraper.cli.configure import configure

app = typer.Typer(
    name="download-reddit-media",
    help="Download media from Reddit subreddits automatically using a stealth browser.",
    add_completion=False,
)

app.command()(download)


def main() -> None:
    """CLI dispatch.

    ``download-reddit-media configure`` runs the defaults-setup helper;
    everything else (including bare invocation and the old flag-driven
    calls like ``-s buildapc --video-only``) routes to ``download`` so
    the legacy UX keeps working unchanged.
    """
    if len(sys.argv) >= 2 and sys.argv[1] == "configure":
        sys.argv.pop(1)
        configure_app = typer.Typer(
            name="download-reddit-media configure",
            add_completion=False,
        )
        configure_app.command()(configure)
        configure_app()
        return
    app()


if __name__ == "__main__":
    main()
