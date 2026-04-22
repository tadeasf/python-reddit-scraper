"""Live-scrape flow: scrape subreddits from Reddit, then download media."""

from __future__ import annotations

import queue
import threading
import time
from pathlib import Path

from loguru import logger

from python_reddit_scraper.cli.runtime import check_camoufox_binary, load_proxies, resolve_options
from python_reddit_scraper.downloader.engine import run_download_queue
from python_reddit_scraper.downloader.state import SessionState
from python_reddit_scraper.progress import ProgressDisplay
from python_reddit_scraper.scraper.json_io import save_scraped_json
from python_reddit_scraper.scraper.parallel import scrape_parallel
from python_reddit_scraper.ui.banner import print_banner
from python_reddit_scraper.ui.prompts import prompt_subreddits
from python_reddit_scraper.ui.summary import print_summary


def run_live(
    subreddits: str | None,
    output_dir: str | None,
    save_json: bool,
    max_pages: int | None,
    workers: int | None,
    scrape_workers: int | None,
) -> None:
    """Scrape one or more subreddits and download all matching media."""
    check_camoufox_binary()
    proxies = load_proxies()

    if subreddits:
        sub_list = [s.strip().lstrip("r/") for s in subreddits.split(",") if s.strip()]
    else:
        sub_list = prompt_subreddits()

    opts = resolve_options(output_dir, max_pages, workers, scrape_workers)
    session_dir = _ensure_output_dir(opts.output_dir)

    print_banner("live", subreddit_count=len(sub_list))
    logger.info(
        "Scraping {} subreddit(s): {}",
        len(sub_list),
        ", ".join(f"r/{s}" for s in sub_list),
    )
    started_at = time.time()

    state = SessionState(output_dir=session_dir, media_types=opts.media_types)
    for sub in sub_list:
        state.subreddits[sub] = "pending"
    state.save()

    download_q: queue.Queue[tuple[str, list[dict]] | None] = queue.Queue()
    download_results: list[tuple[int, int]] = []
    progress = ProgressDisplay(total_subs=len(sub_list))

    def download_consumer() -> None:
        ok, fail = run_download_queue(
            download_q,
            session_dir,
            opts.workers,
            opts.media_types,
            state,
            progress=progress,
        )
        download_results.append((ok, fail))

    consumer = threading.Thread(target=download_consumer, daemon=True)
    consumer.start()

    def on_sub_complete(sub: str, posts: list[dict]) -> None:
        state.mark_subreddit_scraped(sub)
        if save_json and posts:
            path = save_scraped_json(posts, sub)
            logger.info("r/{}: saved JSON to {}", sub, path)
        state.save()
        download_q.put((sub, posts))

    with progress:
        scrape_parallel(
            sub_list,
            max_pages=opts.max_pages,
            max_workers=min(len(sub_list), opts.scrape_workers),
            on_complete=on_sub_complete,
            progress=progress,
            proxies=proxies,
        )
        download_q.put(None)
        consumer.join()

    total_ok = sum(r[0] for r in download_results)
    total_fail = sum(r[1] for r in download_results)

    print_summary(
        session_dir,
        total_ok,
        total_fail,
        list(state.subreddits.keys()),
        started_at=started_at,
    )

    if total_fail == 0:
        state.flush_and_cleanup()
    else:
        state.save()
        logger.info("Resume with: download-reddit-media --resume")


def _ensure_output_dir(base: str) -> str:
    """Ensure *base* exists and return it.

    The tree lives at ``{base}/{subreddit}/{media_type}/`` — flat, no timestamp
    subdirs. Re-runs against the same *base* deduplicate by skipping files that
    already exist on disk (see :func:`downloader.engine.download_all`).
    """
    Path(base).mkdir(parents=True, exist_ok=True)
    return base
