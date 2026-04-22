"""Unified progress display for scraping and downloading using rich."""

import threading

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from python_reddit_scraper.log import log_console as console


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
        n = len(self._active_subs)
        if n == 0:
            return "idle"
        if n == 1:
            sub = next(iter(self._active_subs))
            return f"active: r/{sub}"
        return f"active: {n} subreddits"

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
