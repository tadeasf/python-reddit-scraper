# CLI Reference

## Usage

```bash
# Development (uv)
uv run download-reddit-media [OPTIONS]
uv run download-reddit-media configure

# Global install
download-reddit-media [OPTIONS]
download-reddit-media configure
```

Two entry points:

- **`download-reddit-media [OPTIONS]`** — the download command (default, zero-arg invocation works too).
- **`download-reddit-media configure`** — interactive wizard that saves defaults into `~/.config/python_reddit_scraper/config.yaml`.

## Resolution order

For every tunable option, the first rule that matches wins:

1. Explicit CLI flag.
2. `defaults:` block in `~/.config/python_reddit_scraper/config.yaml`.
3. Interactive prompt (requires a TTY).

## Options

### Subreddit Selection

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--subreddits` | `-s` | _(interactive prompt)_ | Comma-separated subreddit names |
| `--from-json` | | `false` | Load posts from `./input/` JSON files instead of scraping |

### Media Filtering

| Option | Default | Description |
|--------|---------|-------------|
| `--video-only` | `false` | Download only videos and GIFs/animations (shortcut for `media_types: [videos, gifs]`) |
| `--image-only` | `false` | Download only images (shortcut for `media_types: [images]`) |

!!! warning
    `--video-only` and `--image-only` are mutually exclusive.

!!! tip "Pick arbitrary combinations"
    The shortcut flags cover the three common cases. For a custom mix (e.g. images + gifs, videos only without gifs), either answer the interactive checkbox dialog or set `defaults.media_types` in `config.yaml` and omit the shortcut flags.

### Scraping Control

| Option | Default | Description |
|--------|---------|-------------|
| `--max-pages` | _(config.yaml → prompt → `50`)_ | Max pages per subreddit (100 posts/page, so 50 ≈ 5000 posts) |
| `--save-json` | `false` | Save scraped JSON to `./input/{subreddit}/` for later reuse |
| `--scrape-workers` / `-sw` | `cpu_count // 2` | Max parallel Camoufox scraper processes |

### Download Control

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output-dir` | `-o` | _(config.yaml → prompt → `./redditdownloads`)_ | Base directory for downloaded files (timestamped subdirectory created inside) |
| `--workers` | `-w` | `16` | Number of parallel download threads |
| `--resume` | | `false` | Resume the most recent interrupted download session |

### General

| Option | Short | Description |
|--------|-------|-------------|
| `--version` | `-V` | Show version and exit |
| `--help` | | Show help message and exit |

## The `configure` subcommand

```bash
download-reddit-media configure
```

Walks you through the same prompts you'd see on a fresh interactive run, pre-filling from any existing saved values:

1. **Media types** checkbox dialog (<kbd>Space</kbd> toggles, <kbd>Enter</kbd> confirms).
2. **Output directory** (empty input keeps the current / built-in default).
3. **Max pages per subreddit** (empty input keeps the current / built-in default).

Results are merged into `~/.config/python_reddit_scraper/config.yaml` under the `defaults:` block; the `providers:` block (if any) is preserved byte-for-byte compatible.

## Examples

### Basic usage

```bash
# Interactive — prompts for every unset option
download-reddit-media

# Direct — pass everything on command line
download-reddit-media -s buildapc,dataengineering --video-only --max-pages 20

# Custom output directory
download-reddit-media -s wallpapers -o ~/Pictures/reddit
```

### First-time setup

```bash
# Save defaults once
download-reddit-media configure

# Subsequent runs: only the subreddit list is prompted for (and even that
# can be passed via -s)
download-reddit-media
```

### Filtered downloads

```bash
# Videos and animated GIFs only (shortcut flag)
download-reddit-media -s wallpapers --video-only

# Images only (shortcut flag)
download-reddit-media -s wallpapers --image-only

# Images + gifs, no videos (set in config.yaml, then run without filter flags)
download-reddit-media configure
# -> deselect "videos" in the checkbox dialog
download-reddit-media -s wallpapers
```

### JSON caching

```bash
# Scrape + save JSON + download
download-reddit-media -s buildapc --save-json

# Re-download from saved JSON (no browser needed)
download-reddit-media --from-json
```

### Resume interrupted downloads

```bash
# Start a large download
download-reddit-media -s funny,pics,wallpapers

# If interrupted (Ctrl+C, crash, etc.), resume:
download-reddit-media --resume
```

State files live in `.scraper-state/` next to the output directory and carry both the subreddit queue and the chosen media-type filter, so resumes pick up exactly where they left off.

### Advanced

```bash
# Limit scraping depth and download threads
download-reddit-media -s pics --max-pages 10 -w 8

# Combine flags
download-reddit-media -s earthporn --video-only --save-json --max-pages 20 -o /data/reddit
```
