"""Live-scrape flow: scrape subreddits from Reddit, then download media."""

from __future__ import annotations

import queue
import threading
import time
from collections import Counter
from pathlib import Path

import typer
from loguru import logger

from python_reddit_scraper.cli.runtime import check_camoufox_binary, load_proxies, resolve_options
from python_reddit_scraper.constants import ALL_MEDIA_TYPES
from python_reddit_scraper.downloader.engine import run_download_queue
from python_reddit_scraper.downloader.media import extract_all_media, filter_by_media_type
from python_reddit_scraper.downloader.state import SessionState
from python_reddit_scraper.history import record_run
from python_reddit_scraper.progress import ProgressDisplay
from python_reddit_scraper.scraper.json_io import save_scraped_json
from python_reddit_scraper.scraper.parallel import scrape_parallel
from python_reddit_scraper.scraper.preflight import preflight
from python_reddit_scraper.ui.banner import print_banner
from python_reddit_scraper.ui.preflight_table import print_preflight
from python_reddit_scraper.ui.prompts import prompt_subreddits
from python_reddit_scraper.ui.spinner import spinner
from python_reddit_scraper.ui.summary import print_dry_run, print_summary


def run_live(
    subreddits: str | None,
    output_dir: str | None,
    save_json: bool,
    max_pages: int | None,
    workers: int | None,
    scrape_workers: int | None,
    dry_run: bool = False,
) -> None:
    """Scrape one or more subreddits and download all matching media.

    With ``dry_run=True`` the media URLs are extracted and counted but nothing
    is written to disk — useful for validating a large run before committing.
    """
    if subreddits:
        sub_list = [s.strip().lstrip("r/") for s in subreddits.split(",") if s.strip()]
    else:
        sub_list = prompt_subreddits()

    check_camoufox_binary()
    proxies = load_proxies()

    sub_list = _run_preflight(sub_list, proxies)

    opts = resolve_options(output_dir, max_pages, workers, scrape_workers)
    session_dir = _ensure_output_dir(opts.output_dir)

    print_banner("dry-run" if dry_run else "live", subreddit_count=len(sub_list))
    logger.info(
        "Scraping {} subreddit(s): {}",
        len(sub_list),
        ", ".join(f"r/{s}" for s in sub_list),
    )
    started_at = time.time()

    if dry_run:
        total = _run_dry(sub_list, opts, proxies, started_at)
        record_run(
            mode="dry-run",
            subreddits=sub_list,
            duration_s=time.time() - started_at,
            successful=total,
            failed=0,
            output_dir=session_dir,
        )
        return

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

    record_run(
        mode="live",
        subreddits=list(state.subreddits.keys()),
        duration_s=time.time() - started_at,
        successful=total_ok,
        failed=total_fail,
        output_dir=session_dir,
    )

    if total_fail == 0:
        state.flush_and_cleanup()
    else:
        state.save()
        logger.info("Resume with: download-reddit-media --resume")


def _run_preflight(sub_list: list[str], proxies: list[dict] | None) -> list[str]:
    """Probe each sub, show a results table, and return the scrapable subs.

    Reddit aggressively blocks raw-Python probes, so we pass the loaded proxy
    pool through to :func:`preflight`. Subs we couldn't verify are *kept*
    (the main scrape will catch truly-bad ones); only confirmed-bad statuses
    (``not_found``, ``banned``, ``quarantined``) are dropped. Exits when
    every sub is confirmed bad.
    """
    with spinner(f"Preflighting {len(sub_list)} subreddit(s)…"):
        results = preflight(sub_list, proxies=proxies)
    print_preflight(results)
    keep = [r.sub for r in results if r.ok]
    if not keep:
        logger.error("No valid subreddits after preflight. Exiting.")
        raise typer.Exit(1)
    dropped = [r.sub for r in results if not r.ok]
    if dropped:
        logger.warning("Skipping {} invalid subreddit(s): {}", len(dropped), ", ".join(dropped))
    return keep


def _run_dry(sub_list, opts, proxies, started_at: float) -> int:
    """Scrape metadata only; print a dry-run summary; write nothing.

    Returns the total count of media that *would* have been downloaded so the
    caller can record it in history.
    """
    media_types = opts.media_types or ALL_MEDIA_TYPES
    counts: dict[str, Counter[str]] = {sub: Counter() for sub in sub_list}
    progress = ProgressDisplay(total_subs=len(sub_list))

    def on_sub_complete(sub: str, posts: list[dict]) -> None:
        media = filter_by_media_type(extract_all_media(posts), media_types=media_types)
        for item in media:
            counts[sub][_media_category(item["filename"])] += 1
        progress.init_download(total_files=len(media), sub=sub, queued=0)

    with progress:
        scrape_parallel(
            sub_list,
            max_pages=opts.max_pages,
            max_workers=min(len(sub_list), opts.scrape_workers),
            on_complete=on_sub_complete,
            progress=progress,
            proxies=proxies,
        )

    print_dry_run(counts, started_at=started_at)
    return sum(sum(c.values()) for c in counts.values())


def _media_category(filename: str) -> str:
    from python_reddit_scraper.downloader.media import get_media_type

    return get_media_type(filename)


def _ensure_output_dir(base: str) -> str:
    """Ensure *base* exists and return it.

    The tree lives at ``{base}/{subreddit}/{media_type}/`` — flat, no timestamp
    subdirs. Re-runs against the same *base* deduplicate by skipping files that
    already exist on disk (see :func:`downloader.engine.download_all`).
    """
    Path(base).mkdir(parents=True, exist_ok=True)
    return base
