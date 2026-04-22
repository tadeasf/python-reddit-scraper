"""Download engine: concurrent file downloading with progress tracking."""

from __future__ import annotations

import os
import queue
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from loguru import logger

if TYPE_CHECKING:
    from python_reddit_scraper.progress import ProgressDisplay

OnFileDoneCallback = Callable[[str], None]
OnFileFailedCallback = Callable[[str, str, bool], None]

from python_reddit_scraper.downloader.media import (
    extract_all_media,
    filter_by_media_type,
    get_media_type,
)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.reddit.com/",
}

# HTTP codes that should not be retried
_PERMANENT_CODES = {400, 401, 403, 404, 410, 451}
_MAX_RETRIES = 3
_BACKOFF_BASE = 1.5


def _fetch_url(url: str, filepath: str) -> None:
    """Fetch *url* into *filepath* via a ``.part`` tmp file + atomic rename.

    The tmp+rename means an interrupted download never leaves a half-written
    file at the final path — important for the cross-session dedup in
    :func:`download_all`, which treats "file exists" as "already downloaded".
    """
    import contextlib

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    tmp = filepath + ".part"
    req = Request(url, headers=_HEADERS)
    try:
        with urlopen(req, timeout=30) as response, open(tmp, "wb") as f:
            f.write(response.read())
        os.replace(tmp, filepath)
    except BaseException:
        with contextlib.suppress(OSError):
            os.remove(tmp)
        raise


def download_file(
    url: str,
    filepath: str,
    *,
    fallback_urls: list[str] | None = None,
) -> tuple[bool, str]:
    """Download a file from URL to filepath with retries.

    Returns:
        ``(True, "")`` on success, or ``(False, reason)`` on failure.
        *reason* is a short label like ``"http_403"`` or ``"timeout"``.
    """
    all_urls = [url] + (fallback_urls or [])

    for candidate_url in all_urls:
        for attempt in range(_MAX_RETRIES):
            try:
                _fetch_url(candidate_url, filepath)
                return True, ""
            except HTTPError as exc:
                code = exc.code
                reason = f"http_{code}"
                if code in _PERMANENT_CODES:
                    break  # try next fallback URL, don't retry this one
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_BACKOFF_BASE**attempt)
                    continue
            except (URLError, TimeoutError, OSError) as exc:
                reason = "timeout" if "timed out" in str(exc) else "connection_error"
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_BACKOFF_BASE**attempt)
                    continue
            except Exception as exc:
                reason = f"error_{type(exc).__name__}"
                break

    return False, reason


def download_all(
    downloads: list[dict[str, str]],
    output_dir: str,
    workers: int = 16,
    on_file_done: OnFileDoneCallback | None = None,
    on_file_failed: OnFileFailedCallback | None = None,
    progress: ProgressDisplay | None = None,
) -> tuple[int, int, Counter]:
    """Download all media files concurrently.

    Args:
        downloads: List of dicts with 'url', 'filename', optionally 'subreddit',
            'optional', and 'audio_fallbacks' keys.
        output_dir: Base output directory (files sorted into subdirectories).
        workers: Number of parallel download threads.
        on_file_done: Optional callback ``(url: str) -> None`` on success.
        on_file_failed: Optional callback ``(url: str, reason: str, permanent: bool) -> None``.
        progress: Optional shared :class:`ProgressDisplay` instance. When *None*
            (standalone / resume mode), a local ``rich.progress.Progress`` bar is
            used as a fallback.

    Returns:
        Tuple of ``(successful, failed, error_counts)`` where *error_counts*
        is a :class:`~collections.Counter` mapping reason labels to counts.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Build (url, filepath, fallback_urls, optional) tuples
    download_items: list[tuple[str, str, list[str], bool]] = []
    for media in downloads:
        media_type = get_media_type(media["filename"])
        subreddit = media.get("subreddit")
        if subreddit:
            filepath = os.path.join(output_dir, subreddit, media_type, media["filename"])
        else:
            filepath = os.path.join(output_dir, media_type, media["filename"])

        fallbacks = (
            media.get("audio_fallbacks", "").split("|") if media.get("audio_fallbacks") else []
        )
        optional = media.get("optional") == "true"
        download_items.append((media["url"], filepath, fallbacks, optional))

    if not download_items:
        return 0, 0, Counter()

    seen_dirs: set[str] = set()
    for _, filepath, _, _ in download_items:
        d = os.path.dirname(filepath)
        if d not in seen_dirs:
            seen_dirs.add(d)
            Path(d).mkdir(parents=True, exist_ok=True)

    successful = 0
    failed = 0
    skipped_optional = 0
    skipped_existing = 0
    error_counts: Counter = Counter()

    # Fallback: local rich progress bar when no shared ProgressDisplay is provided
    local_progress = None
    local_task_id = None
    if progress is None:
        import rich.progress

        local_progress = rich.progress.Progress(
            rich.progress.TextColumn("[bold blue]{task.description}"),
            rich.progress.BarColumn(),
            rich.progress.MofNCompleteColumn(),
            rich.progress.TimeElapsedColumn(),
            rich.progress.TransferSpeedColumn(),
        )
        local_progress.start()
        local_task_id = local_progress.add_task("Downloading", total=len(download_items))

    # Cross-session dedup: files already on disk are treated as successes.
    # Flat `{output_dir}/{subreddit}/{media_type}/` layout makes this a
    # reliable "I already have this post" signal across runs.
    fresh_items: list[tuple[str, str, list[str], bool]] = []
    for url, filepath, fallbacks, optional in download_items:
        if os.path.exists(filepath):
            skipped_existing += 1
            successful += 1
            if on_file_done:
                on_file_done(url)
            if progress is not None:
                progress.advance_download()
            elif local_progress is not None and local_task_id is not None:
                local_progress.advance(local_task_id)
            continue
        fresh_items.append((url, filepath, fallbacks, optional))

    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {
                executor.submit(
                    download_file,
                    url,
                    filepath,
                    fallback_urls=fallbacks,
                ): (url, filepath, optional)
                for url, filepath, fallbacks, optional in fresh_items
            }
            for future in as_completed(future_map):
                url, filepath, is_optional = future_map[future]
                success, reason = future.result()
                if success:
                    successful += 1
                    if on_file_done:
                        on_file_done(url)
                else:
                    permanent = (
                        reason.startswith("http_") and int(reason.split("_")[1]) in _PERMANENT_CODES
                    )
                    if is_optional and permanent:
                        skipped_optional += 1
                    else:
                        failed += 1
                        if progress is not None:
                            progress.mark_download_failure()
                    error_counts[reason] += 1
                    if on_file_failed:
                        on_file_failed(url, reason, permanent)

                if progress is not None:
                    progress.advance_download()
                elif local_progress is not None and local_task_id is not None:
                    local_progress.advance(local_task_id)
    finally:
        if local_progress is not None:
            local_progress.stop()

    if skipped_existing:
        logger.info(
            "Skipped {} file(s) already on disk (cross-session dedup)",
            skipped_existing,
        )
    if skipped_optional:
        logger.info(
            "Skipped {} optional files (audio tracks blocked by Reddit CDN)",
            skipped_optional,
        )
    if error_counts:
        summary = ", ".join(f"{c}x {r}" for r, c in error_counts.most_common())
        logger.warning("Download errors: {}", summary)

    return successful, failed, error_counts


def run_download_queue(
    download_q: queue.Queue[tuple[str, list[dict]] | None],
    output_dir: str,
    workers: int,
    media_types: set[str] | frozenset[str] | None,
    state=None,
    progress: ProgressDisplay | None = None,
) -> tuple[int, int]:
    """Consumer thread: pulls (subreddit, posts) from queue, downloads one sub at a time.

    Returns cumulative (successful, failed) counts.
    """
    total_ok = 0
    total_fail = 0

    while True:
        item = download_q.get()
        if item is None:
            break
        sub, posts = item

        media = extract_all_media(posts)
        media = filter_by_media_type(media, media_types=media_types)
        if not media:
            logger.info("r/{}: no media after filtering", sub)
            download_q.task_done()
            continue

        if state:
            state.set_media_manifest(state.media + media)

        if progress is not None:
            progress.init_download(total_files=len(media), sub=sub, queued=download_q.qsize())

        logger.info("r/{}: downloading {} files...", sub, len(media))
        ok, fail, _errors = download_all(
            media,
            output_dir,
            workers=workers,
            on_file_done=state.mark_downloaded if state else None,
            on_file_failed=state.mark_permanently_failed if state else None,
            progress=progress,
        )
        total_ok += ok
        total_fail += fail
        logger.info("r/{}: {} downloaded, {} failed", sub, ok, fail)
        download_q.task_done()

    return total_ok, total_fail
