"""
CLI commands for the Reddit media downloader.

Handles the main download command and its sub-modes (live scrape, resume).
"""

import queue
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer
from loguru import logger

from python_reddit_scraper.cli.prompt import (
    check_camoufox_binary,
    prompt_max_pages,
    prompt_media_types,
    prompt_output_dir,
    prompt_subreddits,
)
from python_reddit_scraper.config import ALL_MEDIA_TYPES, get_defaults
from python_reddit_scraper.downloader.engine import download_all, run_download_queue
from python_reddit_scraper.downloader.media import extract_all_media, filter_by_media_type

DEFAULT_OUTPUT_DIR = "./redditdownloads"
DEFAULT_MAX_PAGES = 50
DEFAULT_WORKERS = 16
DEFAULT_SCRAPE_WORKERS = 1


@dataclass(frozen=True)
class ResolvedOptions:
    media_types: frozenset[str]
    output_dir: str
    max_pages: int
    workers: int
    scrape_workers: int


def _resolve_options(
    output_dir: str | None,
    max_pages: int | None,
    workers: int | None,
    scrape_workers: int | None,
) -> ResolvedOptions:
    """Apply the CLI → config → prompt-or-default ladder for user-tunable options."""
    defaults = get_defaults()

    if defaults.media_types is not None:
        media_types: frozenset[str] = frozenset(defaults.media_types)
    else:
        media_types = prompt_media_types(default=ALL_MEDIA_TYPES)

    if output_dir is not None:
        resolved_out = output_dir
    elif defaults.output_dir is not None:
        resolved_out = defaults.output_dir
    else:
        resolved_out = prompt_output_dir(DEFAULT_OUTPUT_DIR)

    if max_pages is not None:
        resolved_pages = max_pages
    elif defaults.max_pages is not None:
        resolved_pages = defaults.max_pages
    else:
        resolved_pages = prompt_max_pages(DEFAULT_MAX_PAGES)

    resolved_workers = workers if workers is not None else (defaults.workers or DEFAULT_WORKERS)
    resolved_scrape_workers = (
        scrape_workers
        if scrape_workers is not None
        else (defaults.scrape_workers or DEFAULT_SCRAPE_WORKERS)
    )

    return ResolvedOptions(
        media_types=media_types,
        output_dir=resolved_out,
        max_pages=resolved_pages,
        workers=resolved_workers,
        scrape_workers=resolved_scrape_workers,
    )


def _load_proxies() -> list[dict] | None:
    """Load proxies for the chosen provider, with per-account fallback.

    Returns the working proxy pool or None when no providers are configured.
    Prompts for a provider when multiple are present in the YAML config.
    Prints a clear error and exits if every account for the picked provider
    has hit its bandwidth limit.
    """
    from python_reddit_scraper.cli.prompt import choose_provider
    from python_reddit_scraper.config import get_providers
    from python_reddit_scraper.scraper.proxy_handler import (
        AllAccountsExhaustedError,
        load_proxies_for_provider,
    )

    providers = get_providers()
    if not providers:
        return None

    provider = choose_provider(providers)

    try:
        from camoufox.locale import download_mmdb

        download_mmdb()
        return load_proxies_for_provider(provider)
    except AllAccountsExhaustedError as exc:
        logger.error("{}", exc)
        raise typer.Exit(1) from exc
    except Exception as exc:
        logger.warning("Could not load {} proxies, scraping without proxy: {}", provider.name, exc)
        return None


def _version_callback(value: bool) -> None:
    if value:
        from python_reddit_scraper import __app_name__, __version__

        print(f"{__app_name__} {__version__}")
        raise typer.Exit()


def _ensure_output_dir(base: str) -> str:
    """Ensure *base* exists and return it.

    The tree lives at ``{base}/{subreddit}/{media_type}/`` — flat, no timestamp
    subdirs. Re-runs against the same *base* deduplicate by skipping files that
    already exist on disk (see :func:`downloader.engine.download_all`).
    """
    Path(base).mkdir(parents=True, exist_ok=True)
    return base


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
        str | None,
        typer.Option(
            "--output-dir",
            "-o",
            help="Base directory for downloaded files. A timestamped subdirectory is created inside. "
            "If omitted, uses the value from config.yaml or prompts interactively.",
        ),
    ] = None,
    save_json: Annotated[
        bool,
        typer.Option(
            "--save-json", help="Save scraped JSON to ./input/{subreddit}/ for later reuse."
        ),
    ] = False,
    max_pages: Annotated[
        int | None,
        typer.Option(
            "--max-pages",
            help="Max pages to scrape per subreddit (100 posts/page). "
            "If omitted, uses the value from config.yaml or prompts interactively.",
        ),
    ] = None,
    workers: Annotated[
        int | None,
        typer.Option(
            "--workers",
            "-w",
            help="Number of parallel download threads. "
            "If omitted, uses the value from config.yaml (default: 16).",
        ),
    ] = None,
    scrape_workers: Annotated[
        int | None,
        typer.Option(
            "--scrape-workers",
            "-sw",
            help="Max parallel camoufox scraper processes. "
            "If omitted, uses the value from config.yaml (default: 1).",
        ),
    ] = None,
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
    if resume:
        _handle_resume(workers)
        return

    check_camoufox_binary()

    proxies = _load_proxies()

    if subreddits:
        sub_list = [s.strip().lstrip("r/") for s in subreddits.split(",") if s.strip()]
    else:
        sub_list = prompt_subreddits()

    opts = _resolve_options(output_dir, max_pages, workers, scrape_workers)
    media_types = opts.media_types
    resolved_max_pages = opts.max_pages
    session_dir = _ensure_output_dir(opts.output_dir)

    logger.info(
        "Scraping {} subreddit(s): {}",
        len(sub_list),
        ", ".join(f"r/{s}" for s in sub_list),
    )

    from python_reddit_scraper.downloader.state import SessionState
    from python_reddit_scraper.progress import ProgressDisplay
    from python_reddit_scraper.scraper.json_io import save_scraped_json
    from python_reddit_scraper.scraper.parallel import scrape_parallel

    state = SessionState(output_dir=session_dir, media_types=media_types)
    for sub in sub_list:
        state.subreddits[sub] = "pending"
    state.save()

    download_q: queue.Queue[tuple[str, list[dict]] | None] = queue.Queue()
    download_results: list[tuple[int, int]] = []

    progress = ProgressDisplay(total_subs=len(sub_list))

    def download_consumer():
        ok, fail = run_download_queue(
            download_q, session_dir, opts.workers, media_types, state, progress=progress
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
            max_pages=resolved_max_pages,
            max_workers=min(len(sub_list), opts.scrape_workers),
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


def _handle_resume(workers: int | None) -> None:
    """Resume the most recent interrupted download session."""
    defaults = get_defaults()
    resolved_workers = workers if workers is not None else (defaults.workers or DEFAULT_WORKERS)

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
        workers=resolved_workers,
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
