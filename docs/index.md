# Reddit Media Downloader

A fast Python tool that scrapes Reddit subreddits using a stealth browser and downloads all media (images, videos, GIFs) at the highest available resolution.

## Features

- **Automated scraping** — Stealth browser ([camoufox](https://github.com/daijro/camoufox)) fetches Reddit's JSON API
- **Parallel scraping** — Multiple subreddits scraped concurrently, downloads queued automatically
- **Resume support** — Interrupted downloads can be resumed with `--resume`
- **Interactive setup** — First-run prompts (or `download-reddit-media configure`) let you pick media types via a checkbox dialog, output dir, and page depth
- **Persistent defaults** — Stored in `~/.config/python_reddit_scraper/config.yaml` so you never repeat flags
- **High-quality downloads** — Selects highest resolution media automatically
- **Concurrent downloads** — 16 parallel workers for maximum speed
- **Smart organization** — Files sorted into `images/`, `videos/`, `gifs/` per subreddit
- **Granular media filtering** — Any subset of `images` / `videos` / `gifs`, or the legacy `--video-only` / `--image-only` shortcuts
- **JSON caching** — `--save-json` to cache scraped data for later reuse
- **Multi-provider proxies** — Webshare (rotating via API) and proxy-cheap (static HTTP) with per-account fallback

## Quick Example

```bash
# First-time setup — save your preferred defaults
uv run download-reddit-media configure

# Scrape and download everything from two subreddits
uv run download-reddit-media -s wallpapers,earthporn

# Videos only, save JSON for later
uv run download-reddit-media -s funny --video-only --save-json

# Resume an interrupted download
uv run download-reddit-media --resume
```

## Navigation

- [Getting Started](getting-started.md) — Installation and first run
- [CLI Reference](cli-reference.md) — All command-line options
- [API Reference](api-reference.md) — Python API documentation
