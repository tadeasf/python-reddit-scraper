# Reddit Media Downloader

A fast Python tool that scrapes Reddit subreddits using a stealth browser and downloads all media (images, videos, GIFs) at the highest available resolution.

## Features

- **Automated scraping** — Stealth browser ([camoufox](https://github.com/nickheal/camoufox)) fetches Reddit's JSON API
- **Parallel scraping** — Multiple subreddits scraped concurrently, downloads queued automatically
- **Resume support** — Interrupted downloads can be resumed with `--resume`
- **Interactive prompt** — Enter subreddit names interactively or via CLI flags
- **High-quality downloads** — Selects highest resolution media automatically
- **Concurrent downloads** — 16 parallel workers for maximum speed
- **Smart organization** — Files sorted into `images/`, `videos/`, `gifs/` per subreddit
- **Media filtering** — `--video-only` or `--image-only` flags
- **JSON caching** — `--save-json` to cache scraped data for later reuse

## Quick Example

```bash
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
