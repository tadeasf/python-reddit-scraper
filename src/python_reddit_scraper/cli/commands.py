"""
CLI commands for the Reddit media downloader.

Handles the main download command and its sub-modes (live scrape, resume, from-json).
"""

import os
import queue
import threading
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from loguru import logger

from python_reddit_scraper.cli.prompt import check_camoufox_binary, prompt_subreddits
from python_reddit_scraper.downloader.engine import download_all, run_download_queue
from python_reddit_scraper.downloader.media import extract_all_media, filter_by_media_type
from python_reddit_scraper.scraper.json_io import parse_json_files


def _load_proxies() -> list[dict] | None:
    """Load Webshare proxies, rotating through all configured API keys if needed.

    Returns the first working proxy pool or None when no keys are configured.
    Prints a clear error and exits if every account has hit its bandwidth limit.
    """
    from python_reddit_scraper.config import get_webshare_accounts
    from python_reddit_scraper.scraper.proxy_handler import (
        AllAccountsExhaustedError,
        fetch_proxies_with_fallback,
    )

    accounts = get_webshare_accounts()
    if not accounts:
        return None
    try:
        from camoufox.locale import download_mmdb

        download_mmdb()
        return fetch_proxies_with_fallback(accounts)
    except AllAccountsExhaustedError as exc:
        logger.error("{}", exc)
        raise typer.Exit(1) from exc
    except Exception as exc:
        logger.warning("Could not load Webshare proxies, scraping without proxy: {}", exc)
        return None


def _version_callback(value: bool) -> None:
    if value:
        from python_reddit_scraper import __app_name__, __version__

        print(f"{__app_name__} {__version__}")
        raise typer.Exit()


def _build_output_dir(base: str) -> str:
    """Create a timestamped output directory under *base* and return its path."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = os.path.join(base, timestamp)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    return output_dir


def download(
    subreddits: Annotated[
        str | None,
        typer.Option(
            "--subreddits",
            "-s",
            help="Comma-separated subreddit names (e.g. 'buildapc,dataengineering').",
        ),
    ] = None,
    output_dir: Annotated[
        str,
        typer.Option(
            "--output-dir",
            "-o",
            help="Base directory for downloaded files. A timestamped subdirectory is created inside.",
        ),
    ] = "./redditdownloads",
    video_only: Annotated[
        bool,
        typer.Option("--video-only", help="Download only videos and GIFs/animations."),
    ] = False,
    image_only: Annotated[
        bool,
        typer.Option("--image-only", help="Download only images."),
    ] = False,
    from_json: Annotated[
        bool,
        typer.Option(
            "--from-json", help="Use existing JSON files in ./input/ instead of scraping."
        ),
    ] = False,
    save_json: Annotated[
        bool,
        typer.Option(
            "--save-json", help="Save scraped JSON to ./input/{subreddit}/ for later reuse."
        ),
    ] = False,
    max_pages: Annotated[
        int,
        typer.Option("--max-pages", help="Max pages to scrape per subreddit (100 posts/page)."),
    ] = 50,
    workers: Annotated[
        int,
        typer.Option("--workers", "-w", help="Number of parallel download threads."),
    ] = 16,
    scrape_workers: Annotated[
        int,
        typer.Option(
            "--scrape-workers",
            "-sw",
            help="Max parallel camoufox scraper processes (default: cpu_count // 2).",
        ),
    ] = max(1, (os.cpu_count() or 2) // 2),
    resume: Annotated[
        bool,
        typer.Option("--resume", help="Resume the most recent interrupted download session."),
    ] = False,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            help="Show version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Download media from Reddit subreddits."""
    if video_only and image_only:
        logger.error("Cannot use --video-only and --image-only together.")
        raise typer.Exit(1)

    if resume:
        _handle_resume(workers)
        return

    if from_json:
        _handle_from_json(video_only, image_only, workers, output_dir)
        return

    check_camoufox_binary()

    proxies = _load_proxies()

    if subreddits:
        sub_list = [s.strip().lstrip("r/") for s in subreddits.split(",") if s.strip()]
    else:
        sub_list = prompt_subreddits()

    session_dir = _build_output_dir(output_dir)

    logger.info(
        "Scraping {} subreddit(s): {}",
        len(sub_list),
        ", ".join(f"r/{s}" for s in sub_list),
    )

    from python_reddit_scraper.downloader.state import SessionState
    from python_reddit_scraper.progress import ProgressDisplay
    from python_reddit_scraper.scraper.json_io import save_scraped_json
    from python_reddit_scraper.scraper.parallel import scrape_parallel

    state = SessionState(output_dir=session_dir, video_only=video_only, image_only=image_only)
    for sub in sub_list:
        state.subreddits[sub] = "pending"
    state.save()

    download_q: queue.Queue[tuple[str, list[dict]] | None] = queue.Queue()
    download_results: list[tuple[int, int]] = []

    progress = ProgressDisplay(total_subs=len(sub_list))

    def download_consumer():
        ok, fail = run_download_queue(
            download_q, session_dir, workers, video_only, image_only, state, progress=progress
        )
        download_results.append((ok, fail))

    consumer = threading.Thread(target=download_consumer, daemon=True)
    consumer.start()

    def on_sub_complete(sub: str, posts: list[dict]):
        """Called when a subreddit finishes scraping -- queues its downloads."""
        state.mark_subreddit_scraped(sub)
        if save_json and posts:
            path = save_scraped_json(posts, sub)
            logger.info("r/{}: saved JSON to {}", sub, path)
        state.save()
        download_q.put((sub, posts))

    with progress:
        scrape_parallel(
            sub_list,
            max_pages=max_pages,
            max_workers=min(len(sub_list), scrape_workers),
            on_complete=on_sub_complete,
            progress=progress,
            proxies=proxies,
        )

        download_q.put(None)
        consumer.join()

    total_ok = sum(r[0] for r in download_results)
    total_fail = sum(r[1] for r in download_results)

    _print_summary(session_dir, total_ok, total_fail, list(state.subreddits.keys()))

    if total_fail == 0:
        state.flush_and_cleanup()
    else:
        state.save()
        logger.info("Resume with: rye run download-reddit-media --resume")


def _handle_resume(workers: int) -> None:
    """Resume the most recent interrupted download session."""
    from python_reddit_scraper.downloader.state import SessionState

    state_path = SessionState.find_latest()
    if not state_path:
        logger.error("No interrupted session found in .scraper-state/")
        raise typer.Exit(1)

    logger.info("Resuming session from {}", state_path)
    state = SessionState.load(state_path)
    output_dir = state.output_dir

    # Re-scrape subreddits that were still pending (not yet scraped) when interrupted
    pending_subs = [sub for sub, status in state.subreddits.items() if status == "pending"]
    if pending_subs:
        logger.info(
            "Re-scraping {} unfinished subreddit(s): {}",
            len(pending_subs),
            ", ".join(f"r/{s}" for s in pending_subs),
        )
        try:
            from python_reddit_scraper.cli.prompt import check_camoufox_binary
            from python_reddit_scraper.scraper.parallel import scrape_parallel

            check_camoufox_binary()

            def on_sub_complete(sub: str, posts: list[dict]):
                state.mark_subreddit_scraped(sub)
                media = extract_all_media(posts)
                media = filter_by_media_type(
                    media,
                    video_only=state.video_only,
                    image_only=state.image_only,
                )
                if media:
                    state.set_media_manifest(state.media + media)
                state.save()
                logger.info("r/{}: scraped {} media items", sub, len(media))

            scrape_parallel(
                pending_subs,
                max_pages=50,
                max_workers=min(len(pending_subs), max(1, (os.cpu_count() or 2) // 2)),
                on_complete=on_sub_complete,
                proxies=_load_proxies(),
            )
        except Exception as exc:
            logger.warning("Could not re-scrape pending subreddits: {}", exc)
            logger.info("Continuing with existing media manifest")

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

    ok, fail, _errors = download_all(
        pending,
        output_dir,
        workers=workers,
        on_file_done=state.mark_downloaded,
        on_file_failed=state.mark_permanently_failed,
    )

    logger.success("Resume complete! {} successful, {} failed", ok, fail)

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


def _handle_from_json(
    video_only: bool, image_only: bool, workers: int, base_output_dir: str
) -> None:
    """Handle --from-json mode: load JSON files and download."""
    logger.info("Loading posts from ./input/ JSON files...")
    posts = parse_json_files("./input")

    if not posts:
        logger.error("No posts found.")
        raise typer.Exit(1)

    logger.info("Total posts: {}", len(posts))
    logger.info("Extracting media URLs...")
    all_media = extract_all_media(posts)
    logger.info("Found {} unique media files", len(all_media))

    all_media = filter_by_media_type(all_media, video_only=video_only, image_only=image_only)
    if video_only or image_only:
        label = "videos+gifs" if video_only else "images"
        logger.info("After filter: {} {}", len(all_media), label)

    if not all_media:
        logger.warning("No media files matched the filter criteria.")
        raise typer.Exit(0)

    session_dir = _build_output_dir(base_output_dir)

    logger.info("Downloading {} files with {} workers...", len(all_media), workers)
    ok, fail, _errors = download_all(all_media, session_dir, workers=workers)

    subs = sorted({m.get("subreddit", "") for m in all_media} - {""})
    _print_summary(session_dir, ok, fail, subs)


def _print_summary(output_dir: str, successful: int, failed: int, subreddits: list[str]) -> None:
    """Print final download summary with per-subreddit stats."""
    logger.success("Download complete! {} successful, {} failed", successful, failed)
    logger.info("Files saved to: {}", output_dir)

    if subreddits:
        for sub in subreddits:
            sub_path = Path(output_dir, sub)
            if sub_path.exists():
                total = sum(1 for _ in sub_path.rglob("*") if _.is_file())
                parts = []
                for media_dir in ["images", "videos", "gifs"]:
                    d = sub_path / media_dir
                    if d.exists():
                        n = len(list(d.glob("*")))
                        if n:
                            parts.append(f"{n} {media_dir}")
                if total:
                    logger.info("  r/{}: {} files ({})", sub, total, ", ".join(parts))
    else:
        for subdir in ["images", "videos", "gifs"]:
            subdir_path = Path(output_dir, subdir)
            if subdir_path.exists():
                file_count = len(list(subdir_path.glob("*")))
                if file_count > 0:
                    logger.info("  {}: {} files", subdir.capitalize(), file_count)
