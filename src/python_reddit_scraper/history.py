"""Run history: append one JSON line per invocation and read them back.

Storage: ``~/.config/python_reddit_scraper/history.jsonl`` — one JSON object
per line, newest last. Append-only for durability; corrupt lines are skipped
on read rather than failing the command.

Schema::

    {
      "timestamp": "2026-04-22T22:30:15",
      "mode": "live" | "resume" | "dry-run",
      "subreddits": ["buildapc", "pics"],
      "duration_s": 142.3,
      "successful": 1200,
      "failed": 3,
      "output_dir": "/home/you/redditdownloads"
    }
"""

from __future__ import annotations

import contextlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger

_HISTORY_PATH = Path.home() / ".config" / "python_reddit_scraper" / "history.jsonl"

_DURATION_PATTERN = re.compile(r"^(\d+)\s*([smhd])$", re.IGNORECASE)
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


@dataclass(frozen=True)
class RunRecord:
    """One recorded invocation of ``download-reddit-media``."""

    timestamp: str
    mode: str
    subreddits: list[str]
    duration_s: float
    successful: int
    failed: int
    output_dir: str

    @property
    def when(self) -> datetime | None:
        try:
            return datetime.fromisoformat(self.timestamp)
        except ValueError:
            return None


def record_run(
    *,
    mode: str,
    subreddits: list[str],
    duration_s: float,
    successful: int,
    failed: int,
    output_dir: str,
) -> None:
    """Append a single run record. Swallows I/O errors so the CLI never fails here."""
    record = RunRecord(
        timestamp=datetime.now().isoformat(timespec="seconds"),
        mode=mode,
        subreddits=list(subreddits),
        duration_s=round(duration_s, 2),
        successful=successful,
        failed=failed,
        output_dir=output_dir,
    )
    try:
        _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _HISTORY_PATH.open("a") as f:
            f.write(json.dumps(asdict(record)) + "\n")
    except OSError as exc:
        logger.warning("Could not write history entry: {}", exc)


def load_runs() -> list[RunRecord]:
    """Return every parseable record in the history file, oldest first."""
    if not _HISTORY_PATH.exists():
        return []
    runs: list[RunRecord] = []
    try:
        with _HISTORY_PATH.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                with contextlib.suppress(json.JSONDecodeError, TypeError, KeyError):
                    payload = json.loads(line)
                    runs.append(
                        RunRecord(
                            timestamp=str(payload.get("timestamp", "")),
                            mode=str(payload.get("mode", "live")),
                            subreddits=list(payload.get("subreddits") or []),
                            duration_s=float(payload.get("duration_s", 0.0)),
                            successful=int(payload.get("successful", 0)),
                            failed=int(payload.get("failed", 0)),
                            output_dir=str(payload.get("output_dir", "")),
                        )
                    )
    except OSError:
        return []
    return runs


def filter_runs(
    runs: list[RunRecord],
    *,
    limit: int | None = None,
    since: str | None = None,
) -> list[RunRecord]:
    """Return the newest-first slice matching *limit* and *since* filters.

    *since* accepts compact duration strings like ``"7d"``, ``"12h"``, ``"30m"``.
    """
    newest_first = list(reversed(runs))
    if since:
        threshold = _parse_since(since)
        if threshold is not None:
            cutoff = datetime.now() - threshold
            newest_first = [r for r in newest_first if r.when and r.when >= cutoff]
    if limit is not None and limit > 0:
        newest_first = newest_first[:limit]
    return newest_first


def _parse_since(s: str) -> timedelta | None:
    match = _DURATION_PATTERN.match(s.strip())
    if not match:
        return None
    value = int(match.group(1))
    unit = match.group(2).lower()
    return timedelta(seconds=value * _UNIT_SECONDS[unit])


def history_path() -> Path:
    """Return the path to the backing history.jsonl file."""
    return _HISTORY_PATH
