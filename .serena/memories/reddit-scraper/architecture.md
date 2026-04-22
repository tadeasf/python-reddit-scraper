# Reddit Scraper Codebase Architecture

## Project Structure
- `src/python_reddit_scraper/app.py` - Typer CLI app entry point
- `src/python_reddit_scraper/cli/commands.py` - Main download() CLI command
- `src/python_reddit_scraper/cli/prompt.py` - Interactive prompts & camoufox checks
- `src/python_reddit_scraper/scraper/core.py` - Core scraping logic (scrape_subreddit)
- `src/python_reddit_scraper/scraper/parallel.py` - Multi-process parallel scraping
- `src/python_reddit_scraper/downloader/engine.py` - Concurrent file download engine
- `src/python_reddit_scraper/downloader/media.py` - Media extraction & filtering
- `src/python_reddit_scraper/downloader/state.py` - Session state persistence

## Camoufox Browser Initialization
- **Location**: `scraper/parallel.py::scrape_worker()`
- **Usage**: `from camoufox.sync_api import Camoufox; with Camoufox(headless=True) as browser:`
- **One browser per worker process** (not shared globally)
- **No proxy handling** currently in initialization
- Binary check via `camoufox.pkgman.installed_verstr()`

## Config Loading
- **No YAML/JSON config files** - only CLI arguments via Typer
- `cli/commands.py::download()` function handles all config via Option decorators
- Interactive prompts if `--subreddits` not provided
- Session state files (`.scraper-state/`) for resume mode
- JSON input files (`./input/`) for `--from-json` mode

## Scraping Logic
- **Multi-process architecture**: `concurrent.futures.ProcessPoolExecutor`
- Each process runs `scrape_worker()` with its own Camoufox browser
- `scrape_subreddit()` in core.py targets `old.reddit.com/r/{sub}.json`
- Pagination via `after` token parameter
- Retry logic with exponential backoff for HTTP errors
- Rate limit handling (HTTP 429 with backoff)
- `_fetch_json_page()` handles individual page fetches

## Concurrency Model
1. **Scraping**: ProcessPoolExecutor (multiprocessing, one per subreddit, default: cpu_count//2)
2. **Download Queue**: Threading.Queue bridges scraping to downloads
3. **Downloads**: ThreadPoolExecutor (16 threads default, configurable via --workers)
4. **Callback Pipeline**: scrape_parallel() → on_complete() → queue → run_download_queue()

## CLI Entry Points
- Main: `app.py::app` (Typer instance)
- Command: `cli/commands.py::download()`
- Modes:
  - Live scrape: `--subreddits "sub1,sub2"` (default)
  - Resume: `--resume`
  - From JSON: `--from-json`
- Key options: --max-pages (50), --workers (16), --scrape-workers (cpu//2)

## Key Class Names & Functions
- `Camoufox` - browser instance from camoufox.sync_api
- `scrape_worker()` - standalone worker function for ProcessPoolExecutor
- `scrape_parallel()` - orchestrates multi-process scraping with callbacks
- `scrape_subreddit()` - core single-subreddit scraping logic
- `_fetch_json_page()` - fetches individual paginated JSON pages with retries
- `download_all()` - concurrent file downloader with ThreadPoolExecutor
- `run_download_queue()` - consumer thread for queue-based downloads
- `SessionState` - persistent session tracking for resume capability
- `ProgressDisplay` - progress bar management across processes

## Retry & Error Handling
- **Scraping**: `_fetch_json_page()` has max_retries=3, exponential backoff 2^attempt
- **HTTP 429**: Special handling with longer backoff
- **HTTP 5xx**: Server error retry with backoff
- **Downloads**: `download_file()` has similar retry logic; supports fallback URLs
- **Permanent failures**: HTTP 400, 401, 403, 404, 410, 451 not retried
