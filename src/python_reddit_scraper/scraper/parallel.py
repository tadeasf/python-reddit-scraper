"""Parallel multi-process scraping of multiple subreddits."""

from concurrent.futures import ProcessPoolExecutor, as_completed

from loguru import logger


def scrape_worker(
    subreddit: str, max_pages: int = 50, delay: float = 1.5
) -> tuple[str, list[dict]]:
    """
    Standalone scrape function for use with ProcessPoolExecutor.

    Each call creates its own Camoufox browser instance (Playwright sync API
    is not thread-safe, so each process must have its own browser).

    Args:
        subreddit: Subreddit name (without r/ prefix).
        max_pages: Maximum pages to fetch.
        delay: Seconds between page requests.

    Returns:
        Tuple of (subreddit_name, list_of_post_dicts).
    """
    from camoufox.sync_api import Camoufox

    from python_reddit_scraper.scraper.core import scrape_subreddit

    with Camoufox(headless=True) as browser:
        posts = scrape_subreddit(browser, subreddit, max_pages=max_pages, delay=delay)
    return subreddit, posts


def scrape_parallel(
    subreddits: list[str],
    max_pages: int = 50,
    delay: float = 1.5,
    max_workers: int = 4,
    on_complete=None,
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

    Returns:
        Dict mapping subreddit name to its list of post dicts.
    """
    results: dict[str, list[dict]] = {}
    n_workers = min(len(subreddits), max_workers)

    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        future_to_sub = {
            executor.submit(scrape_worker, sub, max_pages, delay): sub for sub in subreddits
        }
        for future in as_completed(future_to_sub):
            sub = future_to_sub[future]
            try:
                _, posts = future.result()
                results[sub] = posts
                logger.info("r/{}: {} posts collected", sub, len(posts))
                if on_complete:
                    on_complete(sub, posts)
            except Exception as exc:
                logger.error("r/{}: scraping failed -- {}", sub, exc)
                results[sub] = []

    return results
