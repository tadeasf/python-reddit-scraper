"""Download engine: concurrent file downloading with progress tracking."""

import os
import queue
from pathlib import Path
from urllib.request import Request, urlopen

from loguru import logger
from tqdm import tqdm

from python_reddit_scraper.downloader.media import (
    extract_all_media,
    filter_by_media_type,
    get_media_type,
)


def download_file(url: str, filepath: str, pbar: tqdm) -> bool:
    """Download a file from URL to filepath."""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0"
            ),
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        }

        req = Request(url, headers=headers)
        with urlopen(req, timeout=30) as response, open(filepath, "wb") as f:
            f.write(response.read())

        pbar.set_postfix_str(f"Downloaded: {Path(filepath).name}")
        return True

    except Exception:
        pbar.set_postfix_str(f"Failed: {Path(filepath).name}")
        return False


def download_all(
    downloads: list[dict[str, str]],
    output_dir: str,
    workers: int = 16,
    on_file_done=None,
) -> tuple[int, int]:
    """
    Download all media files concurrently.

    Args:
        downloads: List of dicts with 'url', 'filename', and optionally 'subreddit' keys.
        output_dir: Base output directory (files sorted into subdirectories).
        workers: Number of parallel download threads.
        on_file_done: Optional callback ``(url: str) -> None`` called after each
            successful download (used for resume state tracking).

    Returns:
        Tuple of (successful_count, failed_count).
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    download_pairs = []
    for media in downloads:
        media_type = get_media_type(media["filename"])
        subreddit = media.get("subreddit")
        if subreddit:
            filepath = os.path.join(output_dir, subreddit, media_type, media["filename"])
        else:
            filepath = os.path.join(output_dir, media_type, media["filename"])
        download_pairs.append((media["url"], filepath))

    if not download_pairs:
        return 0, 0

    seen_dirs: set[str] = set()
    for _, filepath in download_pairs:
        d = os.path.dirname(filepath)
        if d not in seen_dirs:
            seen_dirs.add(d)
            Path(d).mkdir(parents=True, exist_ok=True)

    successful = 0
    failed = 0

    pbar = tqdm(
        total=len(download_pairs),
        desc="Downloading",
        unit="files",
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}] {postfix}",
    )

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_download = {
            executor.submit(download_file, url, filepath, pbar): (url, filepath)
            for url, filepath in download_pairs
        }
        for future in as_completed(future_to_download):
            url, filepath = future_to_download[future]
            success = future.result()
            if success:
                successful += 1
                if on_file_done:
                    on_file_done(url)
            else:
                failed += 1
            pbar.update(1)

    pbar.close()
    return successful, failed


def run_download_queue(
    download_q: "queue.Queue[tuple[str, list[dict]] | None]",
    output_dir: str,
    workers: int,
    video_only: bool,
    image_only: bool,
    state=None,
) -> tuple[int, int]:
    """
    Consumer thread: pulls (subreddit, posts) from queue, downloads one sub at a time.

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
        media = filter_by_media_type(media, video_only=video_only, image_only=image_only)
        if not media:
            logger.info("r/{}: no media after filtering", sub)
            download_q.task_done()
            continue

        if state:
            state.set_media_manifest(state.media + media)

        logger.info("r/{}: downloading {} files...", sub, len(media))
        ok, fail = download_all(
            media,
            output_dir,
            workers=workers,
            on_file_done=state.mark_downloaded if state else None,
        )
        total_ok += ok
        total_fail += fail
        logger.info("r/{}: {} downloaded, {} failed", sub, ok, fail)
        download_q.task_done()

    return total_ok, total_fail
