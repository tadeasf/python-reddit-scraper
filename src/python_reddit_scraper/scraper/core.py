"""
Camoufox-based Reddit JSON scraper with pagination.

Navigates old.reddit.com JSON API using a stealth Firefox browser,
follows pagination tokens, and returns raw post data.
"""

import json
import time
from urllib.parse import urlparse

from loguru import logger
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

_REDDIT_HOSTS = (
    "reddit.com",
    "redditstatic.com",
    "redditmedia.com",
    "redd.it",
)


def _only_reddit(route, request) -> None:
    """Playwright route handler: allow reddit hosts, abort everything else.

    Stops Camoufox/addon traffic to CDNs and filter-list hosts from eating
    proxy bandwidth — the scraper only needs the reddit JSON endpoint.
    """
    host = (urlparse(request.url).hostname or "").lower()
    if any(host == h or host.endswith("." + h) for h in _REDDIT_HOSTS):
        route.continue_()
    else:
        route.abort()


def scrape_subreddit(
    browser,
    subreddit: str,
    max_pages: int = 50,
    delay: float = 1.5,
    quiet: bool = False,
) -> list[dict]:
    """
    Scrape a subreddit's posts via Reddit's old JSON API.

    Args:
        browser: A camoufox Browser instance (from sync context manager).
        subreddit: Subreddit name (without r/ prefix).
        max_pages: Maximum number of pages to fetch (100 posts per page).
        delay: Seconds to wait between page requests.
        quiet: If True, suppress all progress output.

    Returns:
        List of post data dicts (the 'data' field of each child).
    """
    posts: list[dict] = []
    after: str | None = None
    base_url = f"https://old.reddit.com/r/{subreddit}.json?limit=100&raw_json=1"

    page = browser.new_page()
    page.context.route("**/*", _only_reddit)
    progress = (
        None
        if quiet
        else Progress(
            SpinnerColumn(),
            TextColumn(f"r/{subreddit}"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("pages"),
            TimeElapsedColumn(),
            TextColumn("{task.fields[postfix]}"),
        )
    )
    task_id = None
    if progress is not None:
        progress.start()
        task_id = progress.add_task(f"r/{subreddit}", total=max_pages, postfix="")

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

            if progress is not None and task_id is not None:
                progress.update(task_id, advance=1, postfix=f"{len(posts)} posts")

            after = data.get("data", {}).get("after")
            if after is None:
                break

            if page_num < max_pages - 1:
                time.sleep(delay)
    finally:
        if progress is not None:
            progress.stop()
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
            response = page.goto(url, wait_until="domcontentloaded", timeout=60000)

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
