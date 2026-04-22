"""Runtime environment setup: camoufox check, proxy loading, option resolution.

This module is the glue between user-provided CLI arguments / YAML defaults
and the concrete values the scraper and downloader need. It contains no UI
styling — presentation is the responsibility of ``python_reddit_scraper.ui``.
"""

from __future__ import annotations

from dataclasses import dataclass

import typer
from loguru import logger

from python_reddit_scraper.config import get_defaults, get_providers
from python_reddit_scraper.constants import (
    ALL_MEDIA_TYPES,
    DEFAULT_MAX_PAGES,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SCRAPE_WORKERS,
    DEFAULT_WORKERS,
)
from python_reddit_scraper.ui.prompts import (
    choose_provider,
    prompt_max_pages,
    prompt_media_types,
    prompt_output_dir,
)
from python_reddit_scraper.ui.spinner import spinner


@dataclass(frozen=True)
class ResolvedOptions:
    media_types: frozenset[str]
    output_dir: str
    max_pages: int
    workers: int
    scrape_workers: int


def resolve_options(
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


def check_camoufox_binary() -> None:
    """Verify the stealth Firefox binary required by camoufox is installed."""
    with spinner("Verifying Camoufox binary…"):
        try:
            from camoufox.pkgman import installed_verstr

            ver = installed_verstr()
            if not ver:
                raise FileNotFoundError
        except Exception:
            logger.error(
                "Camoufox browser not found. Run this command first:\n\n"
                "    uv run camoufox fetch\n\n"
                "This downloads the stealth Firefox binary (~80 MB, one-time setup)."
            )
            raise typer.Exit(1) from None


def load_proxies() -> list[dict] | None:
    """Load proxies for the chosen provider, with per-account fallback.

    Returns the working proxy pool or ``None`` when no providers are configured.
    Prompts for a provider when multiple are present in the YAML config.
    Exits with a clear error when every account for the picked provider has
    hit its bandwidth limit.
    """
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

        with spinner("Downloading GeoIP database…"):
            download_mmdb()
        with spinner(f"Probing {provider.name} accounts…"):
            return load_proxies_for_provider(provider)
    except AllAccountsExhaustedError as exc:
        logger.error("{}", exc)
        raise typer.Exit(1) from exc
    except Exception as exc:
        logger.warning("Could not load {} proxies, scraping without proxy: {}", provider.name, exc)
        return None
