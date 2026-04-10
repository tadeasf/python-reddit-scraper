"""
CLI entry point for the Reddit media downloader.

Uses Typer for CLI flags and prompt-toolkit for interactive subreddit input.
Orchestrates parallel scraping via camoufox and queued downloading.
"""

import os
import queue
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer

from python_reddit_scraper.download_reddit_media import (
    download_all,
    extract_all_media,
    filter_by_media_type,
    parse_json_files,
)

app = typer.Typer(
    name="download-reddit-media",
    help="Download media from Reddit subreddits automatically using a stealth browser.",
    add_completion=False,
)


def _prompt_subreddits() -> list[str]:
    """Interactively prompt for subreddit names using prompt-toolkit."""
    from prompt_toolkit import prompt

    raw = prompt("Enter subreddits (comma-separated): ")
    subs = [s.strip().lstrip("r/") for s in raw.split(",") if s.strip()]
    if not subs:
        typer.echo("No subreddits provided. Exiting.")
        raise typer.Exit(1)
    return subs


def _check_camoufox_binary() -> None:
    """Check if the camoufox Firefox binary is installed."""
    try:
        from camoufox.pkgman import installed_verstr

        ver = installed_verstr()
        if not ver:
            raise FileNotFoundError
    except Exception:
        typer.echo(
            "⚠️  Camoufox browser not found. Run this command first:\n"
            "\n"
            "    camoufox fetch\n"
            "\n"
            "This downloads the stealth Firefox binary (~80 MB, one-time setup)."
        )
        raise typer.Exit(1)


def _run_download_queue(
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
            typer.echo(f"  ⏭  r/{sub}: no media after filtering")
            download_q.task_done()
            continue

        if state:
            state.set_media_manifest(state.media + media)

        typer.echo(f"  📥 r/{sub}: downloading {len(media)} files...")
        ok, fail = download_all(
            media,
            output_dir,
            workers=workers,
            on_file_done=state.mark_downloaded if state else None,
        )
        total_ok += ok
        total_fail += fail
        typer.echo(f"  ✅ r/{sub}: {ok} downloaded, {fail} failed")
        download_q.task_done()

    return total_ok, total_fail


@app.command()
def download(
    subreddits: Annotated[
        Optional[str],
        typer.Option(
            "--subreddits", "-s",
            help="Comma-separated subreddit names (e.g. 'buildapc,dataengineering').",
        ),
    ] = None,
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
        typer.Option("--from-json", help="Use existing JSON files in ./input/ instead of scraping."),
    ] = False,
    save_json: Annotated[
        bool,
        typer.Option("--save-json", help="Save scraped JSON to ./input/{subreddit}/ for later reuse."),
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
        typer.echo("❌ Cannot use --video-only and --image-only together.")
        raise typer.Exit(1)

    # --- Resume mode ---
    if resume:
        _handle_resume(workers)
        return

    # --- From-JSON mode (sequential, no scraping) ---
    if from_json:
        _handle_from_json(video_only, image_only, workers)
        return

    # --- Live scrape mode (parallel) ---
    _check_camoufox_binary()

    if subreddits:
        sub_list = [s.strip().lstrip("r/") for s in subreddits.split(",") if s.strip()]
    else:
        sub_list = _prompt_subreddits()

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = os.path.join("./downloads", timestamp)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    typer.echo(f"🚀 Scraping {len(sub_list)} subreddit(s): {', '.join(f'r/{s}' for s in sub_list)}")

    from python_reddit_scraper.scraper import save_scraped_json, scrape_parallel
    from python_reddit_scraper.state import SessionState

    state = SessionState(output_dir=output_dir, video_only=video_only, image_only=image_only)
    for sub in sub_list:
        state.subreddits[sub] = "pending"
    state.save()

    # Download queue + consumer thread
    download_q: queue.Queue[tuple[str, list[dict]] | None] = queue.Queue()
    download_results: list[tuple[int, int]] = []

    def download_consumer():
        ok, fail = _run_download_queue(
            download_q, output_dir, workers, video_only, image_only, state
        )
        download_results.append((ok, fail))

    consumer = threading.Thread(target=download_consumer, daemon=True)
    consumer.start()

    def on_sub_complete(sub: str, posts: list[dict]):
        """Called when a subreddit finishes scraping — queues its downloads."""
        state.mark_subreddit_scraped(sub)
        if save_json and posts:
            path = save_scraped_json(posts, sub)
            typer.echo(f"  💾 r/{sub}: saved to {path}")
        state.save()
        download_q.put((sub, posts))

    # Parallel scrape — on_complete queues downloads as each sub finishes
    all_posts = scrape_parallel(
        sub_list,
        max_pages=max_pages,
        max_workers=min(len(sub_list), 4),
        on_complete=on_sub_complete,
    )

    # Signal consumer to finish after all subs are queued
    download_q.put(None)
    consumer.join()

    total_ok = sum(r[0] for r in download_results)
    total_fail = sum(r[1] for r in download_results)

    _print_summary(output_dir, total_ok, total_fail, list(all_posts.keys()))

    # Clean up state on success
    if total_fail == 0:
        state.flush_and_cleanup()
    else:
        state.save()
        typer.echo(f"  💡 Resume with: rye run download-reddit-media --resume")


def _handle_resume(workers: int) -> None:
    """Resume the most recent interrupted download session."""
    from python_reddit_scraper.state import SessionState

    state_path = SessionState.find_latest()
    if not state_path:
        typer.echo("❌ No interrupted session found in .scraper-state/")
        raise typer.Exit(1)

    typer.echo(f"🔄 Resuming session from {state_path}")
    state = SessionState.load(state_path)
    output_dir = state.output_dir

    pending = state.get_pending_media()
    total = len(state.media)
    done = total - len(pending)
    typer.echo(f"   {done}/{total} files already downloaded, {len(pending)} remaining")

    if not pending:
        typer.echo("✅ All files already downloaded!")
        state.flush_and_cleanup()
        return

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    ok, fail = download_all(
        pending,
        output_dir,
        workers=workers,
        on_file_done=state.mark_downloaded,
    )

    typer.echo(f"\n🎉 Resume complete!")
    typer.echo(f"   ✓ Successful: {ok}")
    typer.echo(f"   ✗ Failed: {fail}")

    if fail == 0:
        state.flush_and_cleanup()
        typer.echo("   🧹 State file cleaned up")
    else:
        state.save()
        typer.echo(f"   💡 Resume again with: rye run download-reddit-media --resume")


def _handle_from_json(video_only: bool, image_only: bool, workers: int) -> None:
    """Handle --from-json mode: load JSON files and download."""
    typer.echo("🚀 Loading posts from ./input/ JSON files...")
    posts = parse_json_files("./input")

    if not posts:
        typer.echo("No posts found.")
        raise typer.Exit(1)

    typer.echo(f"\n📊 Total posts: {len(posts)}")
    typer.echo("🔍 Extracting media URLs...")
    all_media = extract_all_media(posts)
    typer.echo(f"   Found {len(all_media)} unique media files")

    all_media = filter_by_media_type(all_media, video_only=video_only, image_only=image_only)
    if video_only or image_only:
        label = "videos+gifs" if video_only else "images"
        typer.echo(f"   After filter: {len(all_media)} {label}")

    if not all_media:
        typer.echo("No media files matched the filter criteria.")
        raise typer.Exit(0)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = os.path.join("./downloads", timestamp)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    typer.echo(f"\n📥 Downloading {len(all_media)} files with {workers} workers...")
    ok, fail = download_all(all_media, output_dir, workers=workers)

    subs = sorted({m.get("subreddit", "") for m in all_media} - {""})
    _print_summary(output_dir, ok, fail, subs)


def _print_summary(output_dir: str, successful: int, failed: int, subreddits: list[str]) -> None:
    """Print final download summary with per-subreddit stats."""
    typer.echo(f"\n🎉 Download complete!")
    typer.echo(f"   ✓ Successful: {successful}")
    typer.echo(f"   ✗ Failed: {failed}")
    typer.echo(f"   📁 Files saved to: {output_dir}")

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
                typer.echo(f"   📂 r/{sub}: {total} files ({', '.join(parts)})")
    else:
        for subdir in ["images", "videos", "gifs"]:
            subdir_path = Path(output_dir, subdir)
            if subdir_path.exists():
                file_count = len(list(subdir_path.glob("*")))
                if file_count > 0:
                    typer.echo(f"   📂 {subdir.capitalize()}: {file_count} files")


if __name__ == "__main__":
    app()
