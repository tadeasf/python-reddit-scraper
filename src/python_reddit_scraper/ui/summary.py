"""End-of-run summary rendering.

PR 1 keeps the plain loguru output (moved here from cli/commands.py). PR 2
swaps the body for a ``rich.panel.Panel`` + ``rich.table.Table``.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger


def print_summary(
    output_dir: str,
    successful: int,
    failed: int,
    subreddits: list[str],
) -> None:
    """Print final download summary with per-subreddit stats."""
    logger.success("Download complete! {} successful, {} failed", successful, failed)
    logger.info("Files saved to: {}", output_dir)

    if subreddits:
        for sub in subreddits:
            sub_path = Path(output_dir, sub)
            if not sub_path.exists():
                continue
            total = sum(1 for p in sub_path.rglob("*") if p.is_file())
            parts = []
            for media_dir in ("images", "videos", "gifs"):
                d = sub_path / media_dir
                if d.exists():
                    n = len(list(d.glob("*")))
                    if n:
                        parts.append(f"{n} {media_dir}")
            if total:
                logger.info("  r/{}: {} files ({})", sub, total, ", ".join(parts))
    else:
        for subdir in ("images", "videos", "gifs"):
            subdir_path = Path(output_dir, subdir)
            if subdir_path.exists():
                file_count = len(list(subdir_path.glob("*")))
                if file_count > 0:
                    logger.info("  {}: {} files", subdir.capitalize(), file_count)
