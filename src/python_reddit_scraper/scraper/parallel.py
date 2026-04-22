"""Parallel multi-process scraping of multiple subreddits."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from python_reddit_scraper.progress import ProgressDisplay

OnCompleteCallback = Callable[[str, list[dict]], None]


def scrape_worker(
    subreddit: str,
    max_pages: int = 50,
    delay: float = 1.5,
    quiet: bool = False,
    proxy: dict | None = None,
) -> tuple[str, list[dict]]:
    """
    Standalone scrape function for use with ProcessPoolExecutor.

    Each call creates its own Camoufox browser instance (Playwright sync API
    is not thread-safe, so each process must have its own browser).

    Args:
        subreddit: Subreddit name (without r/ prefix).
        max_pages: Maximum pages to fetch.
        delay: Seconds between page requests.
        quiet: Suppress per-subreddit progress output.
        proxy: Optional proxy dict with keys ``server``, ``username``, ``password``.
               When provided, ``geoip=True`` is also set so Camoufox auto-matches
               locale/timezone to the proxy's exit IP.

    Returns:
        Tuple of (subreddit_name, list_of_post_dicts).
    """
    from camoufox import DefaultAddons
    from camoufox.sync_api import Camoufox

    from python_reddit_scraper.scraper.core import scrape_subreddit

    camoufox_kwargs: dict = {
        "headless": True,
        "exclude_addons": [DefaultAddons.UBO],
    }
    if proxy:
        camoufox_kwargs["proxy"] = proxy
        camoufox_kwargs["geoip"] = True

    with Camoufox(**camoufox_kwargs) as browser:
        posts = scrape_subreddit(browser, subreddit, max_pages=max_pages, delay=delay, quiet=quiet)
    return subreddit, posts


def scrape_parallel(
    subreddits: list[str],
    max_pages: int = 50,
    delay: float = 1.5,
    max_workers: int = 4,
    on_complete: OnCompleteCallback | None = None,
    progress: ProgressDisplay | None = None,
    proxies: list[dict] | None = None,
) -> dict[str, list[dict]]:
    """
    Scrape multiple subreddits in parallel using separate processes.

    Each process gets its own Camoufox browser instance. Results are returned
    as a dict keyed by subreddit name. An optional callback is invoked as each
    subreddit finishes (useful for queueing downloads).

    Args:
        subreddits: List of subreddit names.
        max_pages: Max pages per subreddit.
        delay: Seconds between page requests per scraper.
        max_workers: Maximum concurrent scraper processes.
        on_complete: Optional callback ``(sub: str, posts: list[dict]) -> None``
            invoked as each subreddit finishes scraping.
        progress: Optional shared :class:`ProgressDisplay` for the scraping bar.
        proxies: Optional list of proxy dicts from :func:`proxy_handler.fetch_proxies`.
            Assigned round-robin across workers. When ``None``, no proxy is used.

    Returns:
        Dict mapping subreddit name to its list of post dicts.
    """
    results: dict[str, list[dict]] = {}
    n_workers = min(len(subreddits), max_workers)
    quiet = progress is not None

    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        future_to_sub: dict = {}
        for i, sub in enumerate(subreddits):
            proxy = proxies[i % len(proxies)] if proxies else None
            future = executor.submit(scrape_worker, sub, max_pages, delay, quiet=quiet, proxy=proxy)
            future_to_sub[future] = sub
            if progress:
                progress.mark_scrape_started(sub)

        for future in as_completed(future_to_sub):
            sub = future_to_sub[future]
            try:
                _, posts = future.result()
                results[sub] = posts
                logger.info("r/{}: {} posts collected", sub, len(posts))
                if progress:
                    progress.mark_scrape_done(sub)
                if on_complete:
                    on_complete(sub, posts)
            except Exception as exc:
                logger.error("r/{}: scraping failed -- {}", sub, exc)
                results[sub] = []
                if progress:
                    progress.mark_scrape_done(sub)

    return results
