"""
Typer application entry point for the Reddit media downloader.

Creates the Typer app instance and registers the CLI commands.
"""

import typer

import python_reddit_scraper.log  # noqa: F401 — configure logging on import
from python_reddit_scraper.cli.commands import download

app = typer.Typer(
    name="download-reddit-media",
    help="Download media from Reddit subreddits automatically using a stealth browser.",
    add_completion=False,
)

app.command()(download)

if __name__ == "__main__":
    app()
