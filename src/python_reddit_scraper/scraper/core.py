"""
Camoufox-based Reddit JSON scraper with pagination.

Navigates old.reddit.com JSON API using a stealth Firefox browser,
follows pagination tokens, and returns raw post data.
"""

import json
import time

from loguru import logger
from tqdm import tqdm


def scrape_subreddit(
    browser,
    subreddit: str,
    max_pages: int = 50,
    delay: float = 1.5,
) -> list[dict]:
    """
    Scrape a subreddit's posts via Reddit's old JSON API.

    Args:
        browser: A camoufox Browser instance (from sync context manager).
        subreddit: Subreddit name (without r/ prefix).
        max_pages: Maximum number of pages to fetch (100 posts per page).
        delay: Seconds to wait between page requests.

    Returns:
        List of post data dicts (the 'data' field of each child).
    """
    posts: list[dict] = []
    after: str | None = None
    base_url = f"https://old.reddit.com/r/{subreddit}.json?limit=100&raw_json=1"

    page = browser.new_page()
    pbar = tqdm(
        total=max_pages,
        desc=f"r/{subreddit}",
        unit="page",
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} pages [{elapsed}] {postfix}",
    )

    try:
        for page_num in range(max_pages):
            url = base_url
            if after:
                url += f"&after={after}"

            data = _fetch_json_page(page, url, subreddit)
            if data is None:
                break

            children = data.get("data", {}).get("children", [])
            if not children:
                break

            for child in children:
                if "data" in child:
                    posts.append(child["data"])

            pbar.update(1)
            pbar.set_postfix_str(f"{len(posts)} posts")

            after = data.get("data", {}).get("after")
            if after is None:
                break

            if page_num < max_pages - 1:
                time.sleep(delay)
    finally:
        pbar.close()
        page.close()

    return posts


def _fetch_json_page(
    page,
    url: str,
    subreddit: str,
    max_retries: int = 3,
) -> dict | None:
    """
    Fetch a single JSON page with retry and exponential backoff.

    Returns parsed JSON dict, or None on permanent failure.
    """
    for attempt in range(max_retries):
        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=30000)

            if response is None:
                return None

            status = response.status
            if status == 200:
                raw = response.text()
                return json.loads(raw)

            if status == 429:
                wait = 2 ** (attempt + 1)
                logger.warning(
                    "r/{}: Rate limited (429), retrying in {}s (attempt {}/{})",
                    subreddit,
                    wait,
                    attempt + 1,
                    max_retries,
                )
                time.sleep(wait)
                continue

            if status >= 500:
                wait = 2**attempt
                logger.warning(
                    "r/{}: Server error ({}), retrying in {}s (attempt {}/{})",
                    subreddit,
                    status,
                    wait,
                    attempt + 1,
                    max_retries,
                )
                time.sleep(wait)
                continue

            logger.error("r/{}: HTTP {} -- skipping page", subreddit, status)
            return None

        except json.JSONDecodeError:
            try:
                raw_text = page.evaluate("document.body.textContent")
                return json.loads(raw_text)
            except Exception:
                logger.error("r/{}: Failed to parse JSON response", subreddit)
                return None
        except Exception as e:
            wait = 2**attempt
            logger.warning(
                "r/{}: {}: {}, retrying in {}s (attempt {}/{})",
                subreddit,
                type(e).__name__,
                e,
                wait,
                attempt + 1,
                max_retries,
            )
            time.sleep(wait)

    logger.error("r/{}: Failed after {} attempts -- skipping page", subreddit, max_retries)
    return None
