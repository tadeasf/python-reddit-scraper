"""End-of-run summary rendering.

Two callers:

- ``print_summary`` — after a live scrape or resume run; per-subreddit counts.
- ``print_defaults_panel`` — after ``configure`` saves; echoes the persisted values.
"""

from __future__ import annotations

import time
from pathlib import Path

from rich.box import ROUNDED
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from python_reddit_scraper.log import log_console
from python_reddit_scraper.ui.theme import BORDER, KEY, VALUE

_MEDIA_DIRS = ("images", "videos", "gifs")


def print_summary(
    output_dir: str,
    successful: int,
    failed: int,
    subreddits: list[str],
    *,
    started_at: float | None = None,
    title: str = "Download summary",
) -> None:
    """Render a rich Panel+Table summary of what was downloaded."""
    table = Table(
        box=ROUNDED,
        border_style="bright_black",
        header_style="bold cyan",
        expand=False,
    )
    table.add_column("Subreddit", style="cyan", no_wrap=True)
    for name in _MEDIA_DIRS:
        table.add_column(name.capitalize(), justify="right")
    table.add_column("Total", justify="right", style="bold")
    table.add_column("Size", justify="right", style="green")

    total_files = 0
    total_bytes = 0
    for sub in subreddits or ():
        sub_path = Path(output_dir, sub)
        if not sub_path.exists():
            table.add_row(f"r/{sub}", "—", "—", "—", "0", "—")
            continue
        counts = {name: _count_files(sub_path / name) for name in _MEDIA_DIRS}
        size = _dir_size(sub_path)
        files = sum(counts.values())
        total_files += files
        total_bytes += size
        table.add_row(
            f"r/{sub}",
            *[str(counts[n]) if counts[n] else "—" for n in _MEDIA_DIRS],
            str(files),
            _fmt_bytes(size),
        )

    elapsed = time.time() - started_at if started_at else None
    summary_line = _status_line(successful, failed, elapsed)

    panel = Panel(
        _stack(table, summary_line),
        title=f"[bold cyan] {title} [/bold cyan]",
        subtitle=f"[dim]{output_dir}[/dim]",
        border_style=BORDER,
        box=ROUNDED,
    )
    log_console.print(panel)


def print_defaults_panel(path: Path, defaults: dict) -> None:
    """Echo the saved configure defaults as a KEY/value table inside a panel."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style=KEY, no_wrap=True)
    table.add_column(style=VALUE)
    for key, value in defaults.items():
        table.add_row(f"[{KEY}]\\[{key.upper()}:][/{KEY}]", str(value))

    panel = Panel(
        table,
        title="[bold cyan] Saved defaults [/bold cyan]",
        subtitle=f"[dim]{path}[/dim]",
        border_style=BORDER,
        box=ROUNDED,
    )
    log_console.print(panel)


def _stack(*renderables) -> Table:
    """Stack renderables vertically inside a single-column grid."""
    grid = Table.grid(expand=False)
    grid.add_column()
    for item in renderables:
        grid.add_row(item)
    return grid


def _status_line(successful: int, failed: int, elapsed: float | None) -> Text:
    text = Text()
    text.append("  ")
    text.append(f"{successful} succeeded", style="bold green")
    if failed:
        text.append("  ·  ", style="bright_black")
        text.append(f"{failed} failed", style="bold red")
    if elapsed is not None:
        text.append("  ·  ", style="bright_black")
        text.append(_fmt_duration(elapsed), style="dim")
    return text


def _count_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for p in path.iterdir() if p.is_file())


def _dir_size(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def _fmt_bytes(n: int) -> str:
    if n <= 0:
        return "—"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} TB"


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    mins, secs = divmod(int(seconds), 60)
    if mins < 60:
        return f"{mins}m {secs}s"
    hrs, mins = divmod(mins, 60)
    return f"{hrs}h {mins}m"
