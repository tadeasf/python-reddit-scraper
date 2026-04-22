"""Interactive prompts built on prompt_toolkit — styled, fuzzy-completed, live-validated.

Every single-line prompt renders through :func:`styled_prompt` so the visual
style (`[LABEL:]` in bold cyan + dim default hint) stays consistent. Dialogs
use the palette from :mod:`python_reddit_scraper.ui.theme`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from loguru import logger
from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, FuzzyWordCompleter, PathCompleter
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.shortcuts import checkboxlist_dialog, radiolist_dialog
from prompt_toolkit.validation import Validator

from python_reddit_scraper.constants import ALL_MEDIA_TYPES
from python_reddit_scraper.ui.theme import PROMPT_STYLE

if TYPE_CHECKING:
    from python_reddit_scraper.config import Provider

_HISTORY_PATH = Path.home() / ".config" / "python_reddit_scraper" / "subreddit_history.txt"
_SUBREDDITS_SEED = Path(__file__).resolve().parent.parent.parent.parent / "subreddits.txt"


def _require_tty(what: str) -> None:
    """Bail out with a clear message when a prompt would run on a non-TTY."""
    if not sys.stdin.isatty():
        logger.error(
            "No TTY available for {} prompt. Pass the relevant flag, or run "
            "`download-reddit-media configure` once on an interactive shell "
            "to save defaults.",
            what,
        )
        raise typer.Exit(1)


def styled_prompt(
    label: str,
    *,
    default: str | None = None,
    validator: Validator | None = None,
    completer: Completer | None = None,
) -> str:
    """Render a prompt as `[LABEL:] (default) ` and return the user's answer.

    An empty answer returns *default* when provided, otherwise returns ``""``.
    """
    fragments: list[tuple[str, str]] = [("class:key", f"[{label.upper()}:]")]
    if default not in (None, ""):
        fragments.append(("class:hint", f" ({default})"))
    fragments.append(("", " "))

    raw = prompt(
        FormattedText(fragments),
        style=PROMPT_STYLE,
        validator=validator,
        validate_while_typing=False,
        completer=completer,
        complete_while_typing=bool(completer),
    ).strip()
    if not raw and default is not None:
        return str(default)
    return raw


def choose_provider(providers: list[Provider]) -> Provider:
    """Return the single provider, or let the user pick via a radiolist dialog."""
    if len(providers) == 1:
        return providers[0]

    _require_tty("proxy provider")
    values = [
        (
            p,
            f"{p.name} — {len(p.accounts)} account{'s' if len(p.accounts) != 1 else ''}",
        )
        for p in providers
    ]
    selected = radiolist_dialog(
        title="Proxy provider",
        text="Pick the proxy provider to use for this run.",
        values=values,
        style=PROMPT_STYLE,
    ).run()
    if selected is None:
        logger.error("No provider selected. Exiting.")
        raise typer.Exit(1)
    return selected


def prompt_subreddits() -> list[str]:
    """Prompt for comma-separated subreddit names with fuzzy completion."""
    _require_tty("subreddits")
    completer = FuzzyWordCompleter(_load_subreddit_vocabulary())
    raw = styled_prompt("SUBREDDITS", default=None, completer=completer)
    subs = [s.strip().lstrip("r/") for s in raw.split(",") if s.strip()]
    if not subs:
        logger.error("No subreddits provided. Exiting.")
        raise typer.Exit(1)
    _append_to_history(subs)
    return subs


def pick_resume_session(sessions: list[tuple[str, str]]) -> str | None:
    """Prompt the user to pick one of *sessions* to resume.

    *sessions* is a list of ``(path, label)`` pairs in newest-first order.
    Returns the chosen path, or ``None`` if the dialog was cancelled.
    Auto-returns the only option when ``len(sessions) == 1``.
    """
    if not sessions:
        return None
    if len(sessions) == 1:
        return sessions[0][0]

    _require_tty("resume session")
    selected = radiolist_dialog(
        title="Resume which session?",
        text="Pick an interrupted session (newest first).",
        values=[(path, label) for path, label in sessions],
        default=sessions[0][0],
        style=PROMPT_STYLE,
    ).run()
    return selected


def prompt_media_types(default: set[str] | frozenset[str] | None = None) -> frozenset[str]:
    """Prompt for media types via a checkbox dialog (space toggles, enter confirms)."""
    _require_tty("media types")
    preselected = list(default) if default else list(ALL_MEDIA_TYPES)
    values = [
        ("images", "Images (.jpg/.jpeg/.png/.webp)"),
        ("videos", "Videos (.mp4/.webm/.mov)"),
        ("gifs", "GIFs / animations (.gif)"),
    ]
    selection = checkboxlist_dialog(
        title="Media types",
        text="Space toggles, Enter confirms.",
        values=values,
        default_values=preselected,
        style=PROMPT_STYLE,
    ).run()
    if not selection:
        logger.error("No media types selected. Exiting.")
        raise typer.Exit(1)
    return frozenset(selection)


def prompt_output_dir(default: str) -> str:
    """Prompt for an output directory with tab-completion; empty input returns *default*."""
    _require_tty("output directory")
    raw = styled_prompt("OUTPUT DIR", default=default, completer=PathCompleter(expanduser=True))
    return os.path.expanduser(raw) if raw and raw != default else raw


def prompt_max_pages(default: int) -> int:
    return _prompt_positive_int("MAX PAGES", default, "max pages")


def prompt_workers(default: int) -> int:
    return _prompt_positive_int("DOWNLOAD WORKERS", default, "download workers")


def prompt_scrape_workers(default: int) -> int:
    return _prompt_positive_int("SCRAPE WORKERS", default, "scrape workers")


def _prompt_positive_int(label: str, default: int, what: str) -> int:
    _require_tty(what)
    validator = Validator.from_callable(
        _is_blank_or_positive_int,
        error_message="Enter a positive integer (or leave blank for the default).",
        move_cursor_to_end=True,
    )
    raw = styled_prompt(label, default=str(default), validator=validator)
    return int(raw) if raw else default


def _is_blank_or_positive_int(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    try:
        return int(stripped) > 0
    except ValueError:
        return False


def _load_subreddit_vocabulary() -> list[str]:
    """Build the completer source: deduped names from subreddits.txt + user history."""
    vocab: set[str] = set()
    for path in (_SUBREDDITS_SEED, _HISTORY_PATH):
        if not path.exists():
            continue
        try:
            text = path.read_text()
        except OSError:
            continue
        for chunk in text.replace("\n", ",").split(","):
            name = chunk.strip().lstrip("r/")
            if name:
                vocab.add(name)
    return sorted(vocab, key=str.lower)


def _append_to_history(subs: list[str]) -> None:
    """Record *subs* in the rolling history so the completer learns from use."""
    try:
        _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _HISTORY_PATH.open("a") as f:
            f.write(",".join(subs) + "\n")
    except OSError:
        pass
