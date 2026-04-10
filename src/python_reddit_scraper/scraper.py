"""
Camoufox-based Reddit JSON scraper with pagination.

Navigates old.reddit.com JSON API using a stealth Firefox browser,
follows pagination tokens, and returns raw post data.
Supports both single-browser sequential scraping and parallel multi-process scraping.
"""

import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Optional

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
    after: Optional[str] = None
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


def scrape_worker(subreddit: str, max_pages: int = 50, delay: float = 1.5) -> tuple[str, list[dict]]:
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
            executor.submit(scrape_worker, sub, max_pages, delay): sub
            for sub in subreddits
        }
        for future in as_completed(future_to_sub):
            sub = future_to_sub[future]
            try:
                _, posts = future.result()
                results[sub] = posts
                tqdm.write(f"  ✅ r/{sub}: {len(posts)} posts collected")
                if on_complete:
                    on_complete(sub, posts)
            except Exception as exc:
                tqdm.write(f"  ❌ r/{sub}: scraping failed — {exc}")
                results[sub] = []

    return results


def _fetch_json_page(
    page,
    url: str,
    subreddit: str,
    max_retries: int = 3,
) -> Optional[dict]:
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
                tqdm.write(
                    f"  ⏳ r/{subreddit}: Rate limited (429), "
                    f"retrying in {wait}s (attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(wait)
                continue

            if status >= 500:
                wait = 2 ** attempt
                tqdm.write(
                    f"  ⚠️  r/{subreddit}: Server error ({status}), "
                    f"retrying in {wait}s (attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(wait)
                continue

            tqdm.write(f"  ❌ r/{subreddit}: HTTP {status} — skipping page")
            return None

        except json.JSONDecodeError:
            # Firefox may wrap JSON in HTML; try extracting from body text
            try:
                raw_text = page.evaluate("document.body.textContent")
                return json.loads(raw_text)
            except Exception:
                tqdm.write(f"  ❌ r/{subreddit}: Failed to parse JSON response")
                return None
        except Exception as e:
            wait = 2 ** attempt
            tqdm.write(
                f"  ⚠️  r/{subreddit}: {type(e).__name__}: {e}, "
                f"retrying in {wait}s (attempt {attempt + 1}/{max_retries})"
            )
            time.sleep(wait)

    tqdm.write(f"  ❌ r/{subreddit}: Failed after {max_retries} attempts — skipping page")
    return None


def save_scraped_json(
    posts: list[dict],
    subreddit: str,
    output_dir: str = "./input",
) -> str:
    """
    Save scraped posts to a JSON file compatible with the existing parser.

    Wraps posts in Reddit's listing format so parse_json_files() can read them.
    Returns the path to the saved file.
    """
    from pathlib import Path

    out_path = Path(output_dir) / subreddit
    out_path.mkdir(parents=True, exist_ok=True)

    listing = {
        "kind": "Listing",
        "data": {
            "children": [{"kind": "t3", "data": post} for post in posts],
            "after": None,
        },
    }

    filepath = out_path / "scraped.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(listing, f, ensure_ascii=False, indent=2)

    return str(filepath)
