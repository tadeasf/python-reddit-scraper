# Python Reddit Scraper

## Purpose
CLI tool for scraping and downloading media (images, videos, GIFs) from Reddit subreddits.

## Tech Stack
- Python 3.10+, managed with uv/hatch
- Typer for CLI, loguru for logging, tqdm for progress, camoufox for scraping
- Uses urllib.request for downloads (no requests/httpx)

## Project Structure
```
src/python_reddit_scraper/
├── app.py                # Typer app entrypoint
├── log.py                # Logging config
├── cli/
│   ├── commands.py       # CLI commands (download, _handle_resume, _handle_from_json)
│   └── prompt.py         # Interactive prompts
├── downloader/
│   ├── engine.py         # download_file, download_all, run_download_queue
│   ├── media.py          # URL extraction, media type detection
│   └── state.py          # SessionState class for resume persistence
└── scraper/
    ├── core.py           # Reddit scraping logic
    ├── parallel.py       # Parallel scraping
    └── json_io.py        # JSON save/load
```

## Entry point
`download-reddit-media` → `python_reddit_scraper.app:app`

## Commands
- `uv run ruff check src/` — lint
- `uv run ruff format src/` — format
- `uv run download-reddit-media` — run the tool

## Style
- ruff for linting/formatting, line-length 100
- Type hints used, loguru for logging
- No docstrings on simple functions, docstrings on complex ones
