"""Unified progress display for scraping and downloading using rich."""

import threading

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

console = Console()


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

        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold]{task.description}"),
            BarColumn(bar_width=30),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TextColumn("{task.fields[status]}"),
            console=console,
            transient=False,
        )

        self._scrape_task = self._progress.add_task(
            "Scraping",
            total=total_subs,
            status="waiting…",
        )
        self._download_task = self._progress.add_task(
            "Downloading",
            total=0,
            status="waiting for scrapes…",
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
            self._progress.update(
                self._scrape_task,
                status=self._scrape_status(),
            )

    def mark_scrape_done(self, sub: str) -> None:
        with self._lock:
            self._active_subs.discard(sub)
            self._progress.advance(self._scrape_task)
            self._progress.update(
                self._scrape_task,
                status=self._scrape_status(),
            )

    def _scrape_status(self) -> str:
        if not self._active_subs:
            return "idle"
        names = ", ".join(f"r/{s}" for s in sorted(self._active_subs))
        return f"active: {names}"

    # -- downloading --

    def init_download(self, total_files: int, sub: str, queued: int) -> None:
        """Set (or add to) total files and update the current subreddit label."""
        with self._lock:
            current_total = self._progress.tasks[self._download_task.id].total or 0
            self._progress.update(
                self._download_task,
                total=current_total + total_files,
                status=self._download_status(sub, queued),
            )

    def advance_download(self) -> None:
        self._progress.advance(self._download_task)

    def update_download_status(self, sub: str, queued: int) -> None:
        with self._lock:
            self._progress.update(
                self._download_task,
                status=self._download_status(sub, queued),
            )

    def _download_status(self, sub: str, queued: int) -> str:
        parts = [f"r/{sub}"]
        if queued > 0:
            parts.append(f"{queued} queued")
        return " • ".join(parts)
