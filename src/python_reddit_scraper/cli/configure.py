"""Interactive `configure` subcommand — writes defaults to config.yaml."""

from __future__ import annotations

from python_reddit_scraper.config import Defaults, get_defaults, save_defaults
from python_reddit_scraper.constants import ALL_MEDIA_TYPES
from python_reddit_scraper.ui.prompts import (
    prompt_max_pages,
    prompt_media_types,
    prompt_output_dir,
    prompt_scrape_workers,
    prompt_workers,
)
from python_reddit_scraper.ui.summary import print_defaults_panel


def configure() -> None:
    """Interactively write download defaults to ~/.config/python_reddit_scraper/config.yaml."""
    existing = get_defaults()

    media_default = (
        set(existing.media_types) if existing.media_types is not None else set(ALL_MEDIA_TYPES)
    )
    media_types = prompt_media_types(default=media_default)

    output_default = existing.output_dir or "./redditdownloads"
    output_dir = prompt_output_dir(output_default)

    pages_default = existing.max_pages if existing.max_pages is not None else 50
    max_pages = prompt_max_pages(pages_default)

    workers_default = existing.workers if existing.workers is not None else 16
    workers = prompt_workers(workers_default)

    scrape_workers_default = existing.scrape_workers if existing.scrape_workers is not None else 1
    scrape_workers = prompt_scrape_workers(scrape_workers_default)

    path = save_defaults(
        Defaults(
            media_types=tuple(sorted(media_types)),
            output_dir=output_dir,
            max_pages=max_pages,
            workers=workers,
            scrape_workers=scrape_workers,
        )
    )
    print_defaults_panel(
        path,
        {
            "media_types": ", ".join(sorted(media_types)),
            "output_dir": output_dir,
            "max_pages": max_pages,
            "workers": workers,
            "scrape_workers": scrape_workers,
        },
    )
