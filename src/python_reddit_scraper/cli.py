"""
CLI entry point for the Reddit media downloader.

Uses Typer for CLI flags and prompt-toolkit for interactive subreddit input.
Orchestrates scraping via camoufox and downloading via the existing engine.
"""

import os
import sys
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
) -> None:
    """Download media from Reddit subreddits."""
    if video_only and image_only:
        typer.echo("❌ Cannot use --video-only and --image-only together.")
        raise typer.Exit(1)

    # Collect posts
    posts: list[dict] = []

    if from_json:
        typer.echo("🚀 Loading posts from ./input/ JSON files...")
        posts = parse_json_files("./input")
    else:
        _check_camoufox_binary()

        # Get subreddit list
        if subreddits:
            sub_list = [s.strip().lstrip("r/") for s in subreddits.split(",") if s.strip()]
        else:
            sub_list = _prompt_subreddits()

        typer.echo(f"🚀 Scraping {len(sub_list)} subreddit(s): {', '.join(f'r/{s}' for s in sub_list)}")

        from camoufox.sync_api import Camoufox

        from python_reddit_scraper.scraper import save_scraped_json, scrape_subreddit

        with Camoufox(headless=True) as browser:
            for sub in sub_list:
                sub_posts = scrape_subreddit(browser, sub, max_pages=max_pages)
                typer.echo(f"  ✅ r/{sub}: {len(sub_posts)} posts collected")
                if save_json and sub_posts:
                    path = save_scraped_json(sub_posts, sub)
                    typer.echo(f"  💾 Saved to {path}")
                posts.extend(sub_posts)

    if not posts:
        typer.echo("No posts found.")
        raise typer.Exit(1)

    typer.echo(f"\n📊 Total posts: {len(posts)}")

    # Extract media URLs
    typer.echo("🔍 Extracting media URLs...")
    all_media = extract_all_media(posts)
    typer.echo(f"   Found {len(all_media)} unique media files")

    # Apply media type filter
    all_media = filter_by_media_type(all_media, video_only=video_only, image_only=image_only)
    if video_only or image_only:
        filter_label = "videos+gifs" if video_only else "images"
        typer.echo(f"   After --{'video' if video_only else 'image'}-only filter: {len(all_media)} {filter_label}")

    if not all_media:
        typer.echo("No media files matched the filter criteria.")
        raise typer.Exit(0)

    # Create output directory
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = os.path.join("./downloads", timestamp)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    typer.echo(f"\n📥 Downloading {len(all_media)} files with {workers} workers...")
    typer.echo(f"📁 Output: {output_dir}")

    successful, failed = download_all(all_media, output_dir, workers=workers)

    typer.echo(f"\n🎉 Download complete!")
    typer.echo(f"   ✓ Successful: {successful}")
    typer.echo(f"   ✗ Failed: {failed}")
    typer.echo(f"   📁 Files saved to: {output_dir}")

    for subdir in ["images", "videos", "gifs"]:
        subdir_path = Path(output_dir, subdir)
        if subdir_path.exists():
            file_count = len(list(subdir_path.glob("*")))
            if file_count > 0:
                typer.echo(f"   📂 {subdir.capitalize()}: {file_count} files")


if __name__ == "__main__":
    app()
