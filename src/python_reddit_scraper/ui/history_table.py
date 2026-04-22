"""Render ``download-reddit-media history`` output as a rich Panel+Table."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rich.box import ROUNDED
from rich.panel import Panel
from rich.table import Table

from python_reddit_scraper.history import RunRecord
from python_reddit_scraper.log import log_console
from python_reddit_scraper.ui.theme import BORDER

_MODE_STYLE = {
    "live": "cyan",
    "resume": "magenta",
    "dry-run": "yellow",
}


def print_history(runs: list[RunRecord], *, path: Path) -> None:
    """Render *runs* (newest first) with a subtitle pointing to the source file."""
    if not runs:
        panel = Panel(
            "[dim]No runs recorded yet.[/dim]",
            title="[bold cyan] History [/bold cyan]",
            subtitle=f"[dim]{path}[/dim]",
            border_style=BORDER,
            box=ROUNDED,
        )
        log_console.print(panel)
        return

    table = Table(
        box=ROUNDED,
        border_style="bright_black",
        header_style="bold cyan",
        expand=False,
    )
    table.add_column("When", no_wrap=True, style="dim")
    table.add_column("Mode", no_wrap=True)
    table.add_column("Subreddits", overflow="fold")
    table.add_column("OK", justify="right", style="green")
    table.add_column("Fail", justify="right", style="red")
    table.add_column("Duration", justify="right", no_wrap=True)
    table.add_column("Output", overflow="fold", style="dim")

    for r in runs:
        mode_style = _MODE_STYLE.get(r.mode, "white")
        table.add_row(
            _fmt_when(r.when),
            f"[{mode_style}]{r.mode}[/{mode_style}]",
            _fmt_subs(r.subreddits),
            str(r.successful) if r.successful else "—",
            str(r.failed) if r.failed else "—",
            _fmt_duration(r.duration_s),
            r.output_dir,
        )

    panel = Panel(
        table,
        title=f"[bold cyan] History — last {len(runs)} run(s) [/bold cyan]",
        subtitle=f"[dim]{path}[/dim]",
        border_style=BORDER,
        box=ROUNDED,
    )
    log_console.print(panel)


def _fmt_when(when: datetime | None) -> str:
    if when is None:
        return "—"
    return when.strftime("%Y-%m-%d %H:%M")


def _fmt_subs(subs: list[str]) -> str:
    if not subs:
        return "—"
    if len(subs) <= 3:
        return ", ".join(f"r/{s}" for s in subs)
    return ", ".join(f"r/{s}" for s in subs[:3]) + f" (+{len(subs) - 3})"


def _fmt_duration(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    mins, secs = divmod(int(seconds), 60)
    if mins < 60:
        return f"{mins}m {secs}s"
    hrs, mins = divmod(mins, 60)
    return f"{hrs}h {mins}m"
