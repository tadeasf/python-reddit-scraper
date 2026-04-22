"""
Session state management for resume support.

Persists scraping progress and download manifests to ``.scraper-state/``
so interrupted runs can be resumed with ``--resume``.
"""

import json
import os
import threading
from datetime import datetime
from pathlib import Path

from python_reddit_scraper.constants import ALL_MEDIA_TYPES

STATE_DIR = ".scraper-state"


def _booleans_to_media_types(video_only: bool, image_only: bool) -> frozenset[str]:
    """Translate legacy CLI booleans to a canonical media-type set."""
    if image_only:
        return frozenset({"images"})
    if video_only:
        return frozenset({"videos", "gifs"})
    return ALL_MEDIA_TYPES


class SessionState:
    """
    Manages persistent state for a single scrape+download session.

    State is saved to a JSON file in ``.scraper-state/{timestamp}.json``.
    The file tracks which subreddits have been scraped, the full media
    manifest, and which files have been successfully downloaded.

    Args:
        output_dir: The download output directory for this session.
        media_types: Allowed media types. ``None`` means "all types".
            Legacy ``video_only`` / ``image_only`` booleans are accepted
            for backward compatibility and translated on construction.
        state_path: Explicit path to a state file (used when resuming).
    """

    def __init__(
        self,
        output_dir: str,
        media_types: set[str] | frozenset[str] | None = None,
        video_only: bool = False,
        image_only: bool = False,
        state_path: str | None = None,
    ):
        self.output_dir = output_dir
        if media_types is not None:
            self.media_types: frozenset[str] = frozenset(media_types) or ALL_MEDIA_TYPES
        else:
            self.media_types = _booleans_to_media_types(video_only, image_only)

        self.subreddits: dict[str, str] = {}
        self.media: list[dict] = []
        self._lock = threading.Lock()
        self._dirty_count = 0

        if state_path:
            self.state_path = state_path
        else:
            Path(STATE_DIR).mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            self.state_path = os.path.join(STATE_DIR, f"{ts}.json")

    @property
    def video_only(self) -> bool:
        """Legacy boolean view — true when filter is videos + gifs only."""
        return self.media_types == frozenset({"videos", "gifs"})

    @property
    def image_only(self) -> bool:
        """Legacy boolean view — true when filter is images only."""
        return self.media_types == frozenset({"images"})

    def _to_dict(self) -> dict:
        return {
            "output_dir": self.output_dir,
            "filters": {
                "media_types": sorted(self.media_types),
                # Legacy keys kept for forward-compat with older readers.
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
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        filters = data.get("filters", {})
        raw_mt = filters.get("media_types")
        if raw_mt is not None:
            media_types: frozenset[str] | None = frozenset(raw_mt) & ALL_MEDIA_TYPES or None
        else:
            media_types = _booleans_to_media_types(
                filters.get("video_only", False),
                filters.get("image_only", False),
            )

        state = cls(
            output_dir=data["output_dir"],
            media_types=media_types,
            state_path=path,
        )
        state.subreddits = data.get("subreddits", {})
        state.media = data.get("media", [])
        return state

    @classmethod
    def find_latest(cls) -> str | None:
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

    @classmethod
    def list_all(cls) -> list[str]:
        """Return all state-file paths in ``.scraper-state/``, newest first."""
        state_dir = Path(STATE_DIR)
        if not state_dir.exists():
            return []
        return [str(p) for p in sorted(state_dir.glob("*.json"), reverse=True)]

    def mark_subreddit_scraped(self, sub: str) -> None:
        """Mark a subreddit as having been fully scraped."""
        self.subreddits[sub] = "scraped"

    def set_media_manifest(self, media_list: list[dict]) -> None:
        """
        Set the full media manifest (list of files to download).

        Each item should have ``url``, ``filename``, ``subreddit`` keys.
        A ``downloaded`` field is added and defaults to ``False``.
        """
        self.media = [{**m, "downloaded": m.get("downloaded", False)} for m in media_list]
        self.save()

    def mark_downloaded(self, url: str, batch_size: int = 50) -> None:
        """Mark a media URL as successfully downloaded.

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

    def mark_permanently_failed(self, url: str, reason: str, permanent: bool) -> None:
        """Mark a media URL as permanently failed (e.g. HTTP 403/404).

        These items will be skipped on future resume attempts.
        Only stores permanent failures; transient ones can be retried.
        """
        if not permanent:
            return
        with self._lock:
            for item in self.media:
                if item["url"] == url:
                    item["failed"] = True
                    item["fail_reason"] = reason
                    break
            self._dirty_count += 1
            if self._dirty_count >= 50:
                self.save()

    def get_pending_media(self) -> list[dict]:
        """Get media items that have not yet been downloaded.

        Also checks whether the file already exists on disk (handles
        the case where the file was downloaded but state wasn't saved).
        Permanently failed items (HTTP 403/404) are skipped.

        Returns:
            List of media dicts that still need downloading.
        """
        from python_reddit_scraper.downloader.media import get_media_type

        pending = []
        for item in self.media:
            if item.get("downloaded"):
                continue
            if item.get("failed"):
                continue
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
        import contextlib

        self.save()
        with contextlib.suppress(OSError):
            os.remove(self.state_path)
        with contextlib.suppress(OSError):
            os.rmdir(STATE_DIR)
