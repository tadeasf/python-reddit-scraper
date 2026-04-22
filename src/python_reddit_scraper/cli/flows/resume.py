"""Resume flow: pick up a previously interrupted download session."""

from __future__ import annotations

import time
from pathlib import Path

import typer
from loguru import logger

from python_reddit_scraper.cli.runtime import check_camoufox_binary, load_proxies
from python_reddit_scraper.config import get_defaults
from python_reddit_scraper.constants import (
    DEFAULT_MAX_PAGES,
    DEFAULT_SCRAPE_WORKERS,
    DEFAULT_WORKERS,
)
from python_reddit_scraper.downloader.engine import download_all
from python_reddit_scraper.downloader.media import extract_all_media, filter_by_media_type
from python_reddit_scraper.downloader.state import SessionState
from python_reddit_scraper.ui.banner import print_banner
from python_reddit_scraper.ui.prompts import pick_resume_session
from python_reddit_scraper.ui.summary import print_summary


def run_resume(workers: int | None) -> None:
    """Resume a previously interrupted download session.

    When a single interrupted session exists it is picked automatically;
    otherwise the user picks via a radiolist dialog (Enter takes the newest).
    """
    defaults = get_defaults()
    resolved_workers = workers if workers is not None else (defaults.workers or DEFAULT_WORKERS)

    state_paths = SessionState.list_all()
    if not state_paths:
        logger.error("No interrupted session found in .scraper-state/")
        raise typer.Exit(1)

    state_path = pick_resume_session([(p, _describe_state(p)) for p in state_paths])
    if state_path is None:
        logger.info("Resume cancelled.")
        raise typer.Exit(0)

    logger.info("Resuming session from {}", state_path)
    state = SessionState.load(state_path)
    output_dir = state.output_dir

    print_banner("resume", subreddit_count=len(state.subreddits))

    pending_subs = [sub for sub, status in state.subreddits.items() if status == "pending"]
    if pending_subs:
        _rescrape_pending(state, pending_subs, defaults)

    pending = state.get_pending_media()
    total = len(state.media)
    failed_count = sum(1 for m in state.media if m.get("failed"))
    done = sum(1 for m in state.media if m.get("downloaded"))
    logger.info(
        "{}/{} downloaded, {} remaining, {} permanently failed",
        done,
        total,
        len(pending),
        failed_count,
    )

    if not pending:
        logger.success("All downloadable files complete!")
        state.flush_and_cleanup()
        return

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    started_at = time.time()

    ok, fail, _errors = download_all(
        pending,
        output_dir,
        workers=resolved_workers,
        on_file_done=state.mark_downloaded,
        on_file_failed=state.mark_permanently_failed,
    )

    print_summary(
        output_dir,
        ok,
        fail,
        list(state.subreddits.keys()),
        started_at=started_at,
        title="Resume summary",
    )

    remaining = state.get_pending_media()
    if not remaining:
        state.flush_and_cleanup()
        logger.info("State file cleaned up — all done!")
    else:
        state.save()
        logger.info(
            "{} files still pending — resume again with: download-reddit-media --resume",
            len(remaining),
        )


def _describe_state(path: str) -> str:
    """Build a short human-readable label for a state file (for the picker)."""
    try:
        state = SessionState.load(path)
    except Exception:
        return Path(path).name
    total = len(state.media) or 1
    done = sum(1 for m in state.media if m.get("downloaded"))
    pct = int(100 * done / total)
    subs = ", ".join(f"r/{s}" for s in list(state.subreddits)[:3])
    if len(state.subreddits) > 3:
        subs += f" (+{len(state.subreddits) - 3})"
    return f"{Path(path).stem}  ·  {done}/{len(state.media)} ({pct}%)  ·  {subs}"


def _rescrape_pending(state: SessionState, pending_subs: list[str], defaults) -> None:
    """Re-scrape subreddits that never finished during the original run."""
    from python_reddit_scraper.scraper.parallel import scrape_parallel

    logger.info(
        "Re-scraping {} unfinished subreddit(s): {}",
        len(pending_subs),
        ", ".join(f"r/{s}" for s in pending_subs),
    )
    try:
        check_camoufox_binary()

        def on_sub_complete(sub: str, posts: list[dict]) -> None:
            state.mark_subreddit_scraped(sub)
            media = extract_all_media(posts)
            media = filter_by_media_type(media, media_types=state.media_types)
            if media:
                state.set_media_manifest(state.media + media)
            state.save()
            logger.info("r/{}: scraped {} media items", sub, len(media))

        resume_scrape_workers = defaults.scrape_workers or DEFAULT_SCRAPE_WORKERS
        scrape_parallel(
            pending_subs,
            max_pages=defaults.max_pages or DEFAULT_MAX_PAGES,
            max_workers=min(len(pending_subs), resume_scrape_workers),
            on_complete=on_sub_complete,
            proxies=load_proxies(),
        )
    except Exception as exc:
        logger.warning("Could not re-scrape pending subreddits: {}", exc)
        logger.info("Continuing with existing media manifest")
