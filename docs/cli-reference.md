# CLI Reference

## Usage

```bash
rye run download-reddit-media [OPTIONS]
```

## Options

### Subreddit Selection

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--subreddits` | `-s` | _(interactive prompt)_ | Comma-separated subreddit names |
| `--from-json` | | `false` | Load posts from `./input/` JSON files instead of scraping |

### Media Filtering

| Option | Default | Description |
|--------|---------|-------------|
| `--video-only` | `false` | Download only videos and GIFs/animations |
| `--image-only` | `false` | Download only images (JPG, PNG, WebP) |

!!! warning
    `--video-only` and `--image-only` are mutually exclusive.

### Scraping Control

| Option | Default | Description |
|--------|---------|-------------|
| `--max-pages` | `50` | Max pages per subreddit (100 posts/page, so 50 = ~5000 posts) |
| `--save-json` | `false` | Save scraped JSON to `./input/{subreddit}/` for later reuse |

### Download Control

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--workers` | `-w` | `16` | Number of parallel download threads |
| `--resume` | | `false` | Resume the most recent interrupted download session |

### General

| Option | Description |
|--------|-------------|
| `--help` | Show help message and exit |

## Examples

### Basic usage

```bash
# Interactive — prompts for subreddit names
rye run download-reddit-media

# Direct — pass subreddits on command line
rye run download-reddit-media -s buildapc,dataengineering
```

### Filtered downloads

```bash
# Videos and animated GIFs only
rye run download-reddit-media -s wallpapers --video-only

# Images only (JPG, PNG, WebP)
rye run download-reddit-media -s wallpapers --image-only
```

### JSON caching

```bash
# Scrape + save JSON + download
rye run download-reddit-media -s buildapc --save-json

# Re-download from saved JSON (no browser needed)
rye run download-reddit-media --from-json
```

### Resume interrupted downloads

```bash
# Start a large download
rye run download-reddit-media -s funny,pics,wallpapers

# If interrupted (Ctrl+C, crash, etc.), resume:
rye run download-reddit-media --resume
```

### Advanced

```bash
# Limit scraping depth and download threads
rye run download-reddit-media -s pics --max-pages 10 -w 8

# Combine flags
rye run download-reddit-media -s earthporn --video-only --save-json --max-pages 20
```
