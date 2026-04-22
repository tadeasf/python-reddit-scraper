"""Render the subreddit preflight results as a rich Table."""

from __future__ import annotations

from rich.box import ROUNDED
from rich.panel import Panel
from rich.table import Table

from python_reddit_scraper.log import log_console
from python_reddit_scraper.scraper.preflight import PreflightResult
from python_reddit_scraper.ui.theme import BORDER

_STATUS_STYLE = {
    "public": "green",
    "unverified": "yellow",
    "not_found": "red",
    "banned": "red",
    "quarantined": "yellow",
}


def print_preflight(results: list[PreflightResult]) -> None:
    """Render *results* as a bordered table inside a cyan panel."""
    table = Table(
        box=ROUNDED,
        border_style="bright_black",
        header_style="bold cyan",
        expand=False,
    )
    table.add_column("Subreddit", style="cyan", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Subs", justify="right")
    table.add_column("NSFW", justify="center")
    table.add_column("Notes", style="dim")

    for r in results:
        status_style = _STATUS_STYLE.get(r.status, "white")
        if r.status == "public":
            mark = "[green]✓[/green]"
        elif not r.ok:
            mark = "[red]✗[/red]"
        else:
            mark = "[yellow]?[/yellow]"
        status_text = f"{mark} [{status_style}]{r.status}[/{status_style}]"
        table.add_row(
            f"r/{r.sub}",
            status_text,
            _fmt_subscribers(r.subscribers) if r.subscribers is not None else "—",
            _fmt_nsfw(r.nsfw),
            r.note or "",
        )

    panel = Panel(
        table,
        title="[bold cyan] Preflight [/bold cyan]",
        border_style=BORDER,
        box=ROUNDED,
    )
    log_console.print(panel)


def _fmt_subscribers(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _fmt_nsfw(nsfw: bool | None) -> str:
    if nsfw is None:
        return "—"
    return "[red]yes[/red]" if nsfw else "[dim]no[/dim]"
