# Reddit Media Downloader

A fast Python tool that scrapes Reddit subreddits using a stealth browser and downloads all media (images, videos, GIFs) at the highest available resolution with real-time progress tracking.

## Features

- **Automated scraping**: Stealth browser (camoufox) fetches Reddit JSON API — no manual JSON saving
- **Parallel scraping**: Multiple subreddits scraped concurrently with separate browser instances
- **Queued downloads**: Downloads start as each subreddit finishes scraping — no waiting for all scrapes
- **Resume support**: Interrupted downloads can be resumed with `--resume`
- **Interactive setup**: First-run prompts (or `configure` subcommand) let you pick media types with a checkbox dialog, plus output dir and page depth
- **Persistent defaults**: Stores your preferences in `~/.config/python_reddit_scraper/config.yaml` so you never have to repeat flags
- **High-quality downloads**: Automatically selects highest resolution media
- **Fast concurrent downloads**: Uses 16 parallel workers for maximum speed
- **Configurable output**: `--output-dir` to choose where files are saved
- **Smart organization**: Auto-sorts files into `images/`, `videos/`, and `gifs/` per subreddit
- **Granular media filtering**: Pick any combination of `images` / `videos` / `gifs` interactively, or keep the legacy `--video-only` / `--image-only` shortcut flags
- **Real-time progress**: Beautiful progress bars for both scraping and downloading
- **Timestamped sessions**: Creates dated directories for each download session
- **Deduplication**: Avoids downloading the same file twice
- **JSON caching**: `--save-json` to cache scraped data for later reuse
- **Multi-provider proxies**: Webshare (rotating via API) and proxy-cheap (static, HTTP/HTTPS/SOCKS5) with per-account fallback

## Installation

### Development (with uv)

Clone the repo and install dependencies:

```bash
git clone https://github.com/tadeasf/python-reddit-scraper.git
cd python-reddit-scraper
uv sync
```

Then download the stealth Firefox binary (one-time setup, ~80 MB):

```bash
uv run camoufox fetch
```

### Global install (use anywhere)

Install the package globally with `pipx` so you can run it from any directory:

```bash
pipx install git+https://github.com/tadeasf/python-reddit-scraper.git
camoufox fetch
```

After this you can run `download-reddit-media` directly in any terminal without `uv run`.

## Quick Start

### Automated scraping (recommended)

Run the tool and answer the interactive prompts:

```bash
uv run download-reddit-media
# Enter subreddits (comma-separated): buildapc,dataengineering
# Media types dialog:  [x] images  [x] videos  [x] gifs   (space toggles, enter confirms)
# Output directory [./redditdownloads]: <enter>
# Max pages per subreddit [50]: <enter>
```

Or pass everything on the command line to skip every prompt:

```bash
uv run download-reddit-media --subreddits buildapc,dataengineering --max-pages 20
```

### Save your defaults (skip the prompts next time)

Run `configure` once to save your preferred media types, output directory, and page depth:

```bash
uv run download-reddit-media configure
```

Defaults are written to `~/.config/python_reddit_scraper/config.yaml` under the `defaults:` block. From then on `download-reddit-media` picks them up automatically — any explicit flag still wins.

### Download only videos or images

The legacy shortcut flags still work:

```bash
# Videos and GIFs only
uv run download-reddit-media -s wallpapers --video-only

# Images only
uv run download-reddit-media -s wallpapers --image-only
```

For finer-grained picks (e.g. images + gifs but no videos), either answer the interactive checkbox or set `defaults.media_types` in `config.yaml`.

### Resume interrupted downloads

If a download is interrupted (Ctrl+C, crash, etc.), resume it:

```bash
uv run download-reddit-media --resume
```

### Save scraped JSON for later

```bash
# Scrape and save JSON + download
uv run download-reddit-media -s buildapc --save-json

# Re-download from saved JSON (no browser needed)
uv run download-reddit-media --from-json
```

### All options

```
Usage: download-reddit-media [OPTIONS]
       download-reddit-media configure        # interactive defaults setup

Options:
  -s, --subreddits TEXT       Comma-separated subreddit names (prompts if omitted)
  -o, --output-dir TEXT       Base directory for downloads
                              (default: config.yaml → interactive prompt → ./redditdownloads)
  --video-only                Download only videos and GIFs/animations
  --image-only                Download only images
  --from-json                 Use existing JSON files in ./input/ instead of scraping
  --save-json                 Save scraped JSON to ./input/{subreddit}/
  --max-pages INTEGER         Max pages per subreddit
                              (default: config.yaml → interactive prompt → 50 ≈ 5000 posts)
  -w, --workers INTEGER       Parallel download threads (default: 16)
  -sw, --scrape-workers INT   Max parallel camoufox scrapers (default: cpu_count // 2)
  --resume                    Resume the most recent interrupted download session
  -V, --version               Show version and exit
  --help                      Show this message and exit
```

When a filter flag or value is missing, resolution order is: **CLI flag → `config.yaml` defaults → interactive prompt**.

## Configuration

All user configuration lives in `~/.config/python_reddit_scraper/config.yaml`. The file is split into two optional top-level blocks — set either, both, or neither.

```yaml
# Defaults applied when the matching CLI flag is not passed.
# Populate this by running `download-reddit-media configure` (recommended)
# or by editing the file directly.
defaults:
  media_types: [images, videos, gifs]   # any non-empty subset of these three
  output_dir: /home/you/redditdownloads
  max_pages: 50

# Proxy providers. Multiple providers and accounts are supported; the
# tool prompts when more than one provider is configured and falls back
# across accounts if one is exhausted.
providers:
  - name: webshare
    accounts:
      - email: you@example.com
        api_key: <webshare-api-key>
  - name: proxy-cheap
    accounts:
      - username: <user>
        password: <pass>
        ip_address: 178.93.44.23
        port: 46271
        protocol: http          # http (default) | https | socks5
```

### Proxy notes

- **webshare** accounts are refreshed via the Webshare API on every run.
- **proxy-cheap** accounts are static endpoints and the `protocol` field is optional; if omitted it defaults to `http`. Valid values are `http`, `https`, and `socks5` — Camoufox / Playwright honours authenticated SOCKS5 via the same `username` / `password` fields.
- If every account for the chosen provider has exhausted its bandwidth, the tool exits with a clear error rather than silently scraping direct.

## How It Works

### Parallel scraping + queued downloads

When scraping multiple subreddits, each gets its own browser process:

```
Scraper Process 1: r/wallpapers ──► finishes ──► download starts immediately
Scraper Process 2: r/earthporn  ──► finishes ──► queued, downloads after wallpapers
Scraper Process 3: r/pics       ──► finishes ──► queued, downloads after earthporn
```

### Resume support

Session state is saved to `.scraper-state/` after scraping completes. If downloading is interrupted, `--resume` picks up where it left off — no re-scraping needed. State files are auto-cleaned after successful completion.

## Output Structure

Files are automatically organized by subreddit and media type inside the
output directory (`./redditdownloads` by default, configurable with `-o`):

```bash
redditdownloads/
└── 2025-01-27_14-30-45/
    ├── wallpapers/
    │   ├── images/
    │   ├── videos/
    │   └── gifs/
    └── earthporn/
        ├── images/
        ├── videos/
        └── gifs/
```

Use `--output-dir` / `-o` to change the base path:

```bash
uv run download-reddit-media -s wallpapers -o ~/Pictures/reddit
# Files will be saved to ~/Pictures/reddit/2025-01-27_14-30-45/wallpapers/...
```

## Advanced: Manual JSON Workflow

You can still use the original manual workflow:

### 1. Prepare JSON files

Save Reddit JSON data to the `./input` directory.

**Example for r/{subreddit}:**

- **Page 1**: `https://old.reddit.com/r/subreddit.json?limit=100&raw_json=1` → Save as `./input/1.json`
- **Find pagination**: Look for the `data.after` value in `1.json` (e.g. `t3_abc123`)
- **Page 2**: `https://old.reddit.com/r/subreddit.json?limit=100&raw_json=1&after=t3_abc123` → Save as `./input/2.json`
- **Continue**: Repeat until `data.after` is null (end of subreddit)

### 2. Run from saved JSON

```bash
uv run download-reddit-media --from-json
```

## Documentation

Full documentation is available at: https://tadeasf.github.io/python-reddit-scraper/

To build docs locally:

```bash
uv run mkdocs serve
```

## Supported Media Types

| Type          | Extensions       | Details                                        |
| ------------- | ---------------- | ---------------------------------------------- |
| **Images**    | JPG, PNG, WebP   | Highest resolution available                   |
| **Videos**    | MP4, WebM, MOV   | Reddit videos with separate audio tracks       |
| **GIFs**      | GIF              | Animated GIFs and GifV (auto-converted to MP4) |
| **Galleries** | Multiple formats | All images from Reddit gallery posts           |
| **External**  | Various          | Direct media URLs from imgur, redgifs, etc.    |

## Technical Details

- **Stealth scraping**: Camoufox (anti-detect Firefox) with automatic fingerprint rotation
- **Parallel architecture**: ProcessPoolExecutor for scraping (each process gets own browser)
- **Queued downloads**: Download consumer thread processes subreddits as they finish scraping
- **Resume state**: JSON session files in `.scraper-state/` with atomic writes
- **Smart parsing**: Handles Reddit's complex data structures (galleries, videos, previews)
- **Rate limiting**: 1.5s delay between API pages + exponential backoff on 429s
- **High performance**: 16 concurrent workers for optimal download speed
- **Cross-platform**: Sanitizes filenames for Windows/Mac/Linux compatibility
- **Anti-blocking**: Proper HTTP headers and user agent rotation
- **Memory efficient**: Streams large files without loading into memory

## License

GPL-3.0

---

**Star this repo if it helped you download your favorite Reddit media!**
