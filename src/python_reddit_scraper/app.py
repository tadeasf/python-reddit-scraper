"""
Typer application entry point for the Reddit media downloader.

Creates the Typer app instance and registers the CLI commands.
"""

import sys

import typer

import python_reddit_scraper.log  # noqa: F401 — configure logging on import
from python_reddit_scraper.cli.commands import download
from python_reddit_scraper.cli.configure import configure
from python_reddit_scraper.cli.history_cmd import history

app = typer.Typer(
    name="download-reddit-media",
    help="Download media from Reddit subreddits automatically using a stealth browser.",
    add_completion=False,
)

app.command()(download)


_SUBCOMMANDS = {
    "configure": configure,
    "history": history,
}


def main() -> None:
    """CLI dispatch.

    Recognised subcommands (``configure``, ``history``) are routed to their own
    tiny Typer apps so they don't need to share option signatures with the
    default ``download`` command. Everything else (including bare invocation)
    routes to ``download``.
    """
    if len(sys.argv) >= 2 and sys.argv[1] in _SUBCOMMANDS:
        name = sys.argv.pop(1)
        subcommand = _SUBCOMMANDS[name]
        sub_app = typer.Typer(name=f"download-reddit-media {name}", add_completion=False)
        sub_app.command()(subcommand)
        sub_app()
        return
    app()


if __name__ == "__main__":
    main()
