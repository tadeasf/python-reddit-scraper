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
    ] = "./downloads",
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
    resume: Annotated[
        bool,
        typer.Option("--resume", help="Resume the most recent interrupted download session."),
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
    from python_reddit_scraper.scraper.json_io import save_scraped_json
    from python_reddit_scraper.scraper.parallel import scrape_parallel

    state = SessionState(output_dir=session_dir, video_only=video_only, image_only=image_only)
    for sub in sub_list:
        state.subreddits[sub] = "pending"
    state.save()

    download_q: queue.Queue[tuple[str, list[dict]] | None] = queue.Queue()
    download_results: list[tuple[int, int]] = []

    def download_consumer():
        ok, fail = run_download_queue(
            download_q, session_dir, workers, video_only, image_only, state
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

    scrape_parallel(
        sub_list,
        max_pages=max_pages,
        max_workers=min(len(sub_list), 4),
        on_complete=on_sub_complete,
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

    pending = state.get_pending_media()
    total = len(state.media)
    done = total - len(pending)
    logger.info("{}/{} files already downloaded, {} remaining", done, total, len(pending))

    if not pending:
        logger.success("All files already downloaded!")
        state.flush_and_cleanup()
        return

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    ok, fail = download_all(
        pending,
        output_dir,
        workers=workers,
        on_file_done=state.mark_downloaded,
    )

    logger.success("Resume complete! {} successful, {} failed", ok, fail)

    if fail == 0:
        state.flush_and_cleanup()
        logger.info("State file cleaned up")
    else:
        state.save()
        logger.info("Resume again with: rye run download-reddit-media --resume")


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
    ok, fail = download_all(all_media, session_dir, workers=workers)

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
