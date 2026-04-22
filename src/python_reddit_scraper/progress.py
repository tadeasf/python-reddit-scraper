"""Unified progress display for scraping and downloading using rich."""

from __future__ import annotations

import threading

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    ProgressColumn,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.text import Text

from python_reddit_scraper.log import log_console as console


class _RateColumn(ProgressColumn):
    """Render a "{files}/s" rate column; hidden when no throughput yet."""

    def render(self, task) -> Text:
        elapsed = task.elapsed or 0.0
        if elapsed <= 0 or task.completed <= 0:
            return Text("—/s", style="grey50")
        rate = task.completed / elapsed
        if rate >= 10:
            return Text(f"{rate:.0f}/s", style="bright_black")
        return Text(f"{rate:.2f}/s", style="bright_black")


class ProgressDisplay:
    """Thread-safe dual progress bar display for scraping + downloading.

    Usage::

        with ProgressDisplay(total_subs=5) as pd:
            pd.mark_scrape_started("pics")
            pd.mark_scrape_done("pics")
            pd.init_download(total_files=120, sub="pics", queued=3)
            pd.advance_download()
    """

    def __init__(self, total_subs: int) -> None:
        self._lock = threading.Lock()
        self._active_subs: set[str] = set()
        self._total_subs = total_subs
        self._download_total: int = 0
        self._download_failures: int = 0

        self._progress = Progress(
            SpinnerColumn(style="cyan"),
            TextColumn("[bold cyan]{task.description:<11}"),
            BarColumn(bar_width=30, complete_style="green", finished_style="bold green"),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            _RateColumn(),
            TimeElapsedColumn(),
            TextColumn("[dim]eta[/dim]"),
            TimeRemainingColumn(compact=True),
            TextColumn("{task.fields[status]}"),
            console=console,
            transient=False,
            expand=False,
        )

        self._scrape_task = self._progress.add_task(
            "Scraping",
            total=total_subs,
            status="[yellow]waiting…[/yellow]",
        )
        self._download_task = self._progress.add_task(
            "Downloading",
            total=0,
            status="[yellow]waiting for scrapes…[/yellow]",
            visible=True,
        )

    # -- context manager --

    def __enter__(self):
        self._progress.start()
        return self

    def __exit__(self, *exc):
        self._progress.stop()

    def start(self) -> None:
        self._progress.start()

    def stop(self) -> None:
        self._progress.stop()

    # -- scraping --

    def mark_scrape_started(self, sub: str) -> None:
        with self._lock:
            self._active_subs.add(sub)
            self._progress.update(self._scrape_task, status=self._scrape_status())

    def mark_scrape_done(self, sub: str) -> None:
        with self._lock:
            self._active_subs.discard(sub)
            self._progress.advance(self._scrape_task)
            self._progress.update(self._scrape_task, status=self._scrape_status())

    def _scrape_status(self) -> str:
        n = len(self._active_subs)
        if n == 0:
            return "[dim]idle[/dim]"
        if n == 1:
            sub = next(iter(self._active_subs))
            return f"[green]active:[/green] [cyan]r/{sub}[/cyan]"
        return f"[green]active:[/green] [cyan]{n} subreddits[/cyan]"

    # -- downloading --

    def init_download(self, total_files: int, sub: str, queued: int) -> None:
        """Add to total files and update the current subreddit label."""
        with self._lock:
            self._download_total += total_files
            self._progress.update(
                self._download_task,
                total=self._download_total,
                status=self._download_status(sub, queued),
            )

    def advance_download(self) -> None:
        self._progress.advance(self._download_task)

    def mark_download_failure(self) -> None:
        with self._lock:
            self._download_failures += 1

    def update_download_status(self, sub: str, queued: int) -> None:
        with self._lock:
            self._progress.update(
                self._download_task,
                status=self._download_status(sub, queued),
            )

    def _download_status(self, sub: str, queued: int) -> str:
        parts = [f"[cyan]r/{sub}[/cyan]"]
        if queued > 0:
            parts.append(f"[dim]{queued} queued[/dim]")
        if self._download_failures:
            parts.append(f"[bold red]{self._download_failures} failed[/bold red]")
        return " [bright_black]•[/bright_black] ".join(parts)
