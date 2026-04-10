"""
Session state management for resume support.

Persists scraping progress and download manifests to `.scraper-state/`
so interrupted runs can be resumed with `--resume`.
"""

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional


STATE_DIR = ".scraper-state"


class SessionState:
    """
    Manages persistent state for a single scrape+download session.

    State is saved to a JSON file in ``.scraper-state/{timestamp}.json``.
    The file tracks which subreddits have been scraped, the full media
    manifest, and which files have been successfully downloaded.

    Args:
        output_dir: The download output directory for this session.
        video_only: Whether ``--video-only`` filter is active.
        image_only: Whether ``--image-only`` filter is active.
        state_path: Explicit path to a state file (used when resuming).
    """

    def __init__(
        self,
        output_dir: str,
        video_only: bool = False,
        image_only: bool = False,
        state_path: Optional[str] = None,
    ):
        self.output_dir = output_dir
        self.video_only = video_only
        self.image_only = image_only
        self.subreddits: dict[str, str] = {}  # sub -> "scraped"|"pending"
        self.media: list[dict] = []  # each has url, filename, subreddit, downloaded
        self._lock = threading.Lock()
        self._dirty_count = 0

        if state_path:
            self.state_path = state_path
        else:
            Path(STATE_DIR).mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            self.state_path = os.path.join(STATE_DIR, f"{ts}.json")

    def _to_dict(self) -> dict:
        return {
            "output_dir": self.output_dir,
            "filters": {
                "video_only": self.video_only,
                "image_only": self.image_only,
            },
            "subreddits": self.subreddits,
            "media": self.media,
        }

    def save(self) -> None:
        """Write current state to disk atomically."""
        tmp = self.state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._to_dict(), f, ensure_ascii=False)
        os.replace(tmp, self.state_path)
        self._dirty_count = 0

    @classmethod
    def load(cls, path: str) -> "SessionState":
        """
        Load a session state from a JSON file.

        Args:
            path: Path to the state JSON file.

        Returns:
            A populated SessionState instance.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        filters = data.get("filters", {})
        state = cls(
            output_dir=data["output_dir"],
            video_only=filters.get("video_only", False),
            image_only=filters.get("image_only", False),
            state_path=path,
        )
        state.subreddits = data.get("subreddits", {})
        state.media = data.get("media", [])
        return state

    @classmethod
    def find_latest(cls) -> Optional[str]:
        """
        Find the most recent state file in the state directory.

        Returns:
            Path to the newest state file, or None if none exist.
        """
        state_dir = Path(STATE_DIR)
        if not state_dir.exists():
            return None
        files = sorted(state_dir.glob("*.json"), reverse=True)
        return str(files[0]) if files else None

    def mark_subreddit_scraped(self, sub: str) -> None:
        """Mark a subreddit as having been fully scraped."""
        self.subreddits[sub] = "scraped"

    def set_media_manifest(self, media_list: list[dict]) -> None:
        """
        Set the full media manifest (list of files to download).

        Each item should have ``url``, ``filename``, ``subreddit`` keys.
        A ``downloaded`` field is added and defaults to ``False``.
        """
        self.media = [
            {**m, "downloaded": m.get("downloaded", False)}
            for m in media_list
        ]
        self.save()

    def mark_downloaded(self, url: str, batch_size: int = 50) -> None:
        """
        Mark a media URL as successfully downloaded.

        State is flushed to disk every ``batch_size`` completions for performance.

        Args:
            url: The URL that was downloaded.
            batch_size: How often to flush state to disk.
        """
        with self._lock:
            for item in self.media:
                if item["url"] == url:
                    item["downloaded"] = True
                    break
            self._dirty_count += 1
            if self._dirty_count >= batch_size:
                self.save()

    def get_pending_media(self) -> list[dict]:
        """
        Get media items that have not yet been downloaded.

        Also checks whether the file already exists on disk (handles
        the case where the file was downloaded but state wasn't saved).

        Returns:
            List of media dicts that still need downloading.
        """
        from python_reddit_scraper.download_reddit_media import get_media_type

        pending = []
        for item in self.media:
            if item.get("downloaded"):
                continue
            # Double-check: file might exist on disk even if state says not downloaded
            media_type = get_media_type(item["filename"])
            sub = item.get("subreddit")
            if sub:
                filepath = os.path.join(self.output_dir, sub, media_type, item["filename"])
            else:
                filepath = os.path.join(self.output_dir, media_type, item["filename"])
            if os.path.exists(filepath):
                item["downloaded"] = True
                continue
            pending.append(item)
        return pending

    def flush_and_cleanup(self) -> None:
        """Save final state and remove the state file on completion."""
        self.save()
        try:
            os.remove(self.state_path)
        except OSError:
            pass
        # Remove state dir if empty
        try:
            os.rmdir(STATE_DIR)
        except OSError:
            pass
