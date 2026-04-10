# Reddit Media Downloader

A fast Python tool that scrapes Reddit subreddits using a stealth browser and downloads all media (images, videos, GIFs) at the highest available resolution with real-time progress tracking.

## Features

- **Automated scraping**: Stealth browser (camoufox) fetches Reddit JSON API — no manual JSON saving
- **Interactive prompt**: Enter subreddit names interactively or via CLI flags
- **High-quality downloads**: Automatically selects highest resolution media
- **Fast concurrent downloads**: Uses 16 parallel workers for maximum speed
- **Smart organization**: Auto-sorts files into `images/`, `videos/`, and `gifs/` subdirectories
- **Media filtering**: `--video-only` or `--image-only` flags to download specific types
- **Real-time progress**: Beautiful progress bars for both scraping and downloading
- **Timestamped sessions**: Creates dated directories for each download session
- **Deduplication**: Avoids downloading the same file twice
- **JSON caching**: `--save-json` to cache scraped data for later reuse

## Installation

Install dependencies using Rye:

```bash
rye sync
```

Then download the stealth Firefox binary (one-time setup, ~80 MB):

```bash
camoufox fetch
```

## Quick Start

### Automated scraping (recommended)

Run the tool and enter subreddit names when prompted:

```bash
rye run download-reddit-media
# Enter subreddits (comma-separated): buildapc,dataengineering
```

Or pass subreddits directly:

```bash
rye run download-reddit-media --subreddits buildapc,dataengineering
```

### Download only videos or images

```bash
# Videos and GIFs only
rye run download-reddit-media -s wallpapers --video-only

# Images only
rye run download-reddit-media -s wallpapers --image-only
```

### Save scraped JSON for later

```bash
# Scrape and save JSON + download
rye run download-reddit-media -s buildapc --save-json

# Re-download from saved JSON (no browser needed)
rye run download-reddit-media --from-json
```

### All options

```
Options:
  -s, --subreddits TEXT    Comma-separated subreddit names
  --video-only             Download only videos and GIFs/animations
  --image-only             Download only images
  --from-json              Use existing JSON files in ./input/ instead of scraping
  --save-json              Save scraped JSON to ./input/{subreddit}/
  --max-pages INTEGER      Max pages per subreddit (default: 50 ≈ 5000 posts)
  -w, --workers INTEGER    Parallel download threads (default: 16)
  --help                   Show this message and exit
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
rye run download-reddit-media --from-json
```

## Output Structure

Files are automatically organized in timestamped directories with type-based sorting:

```bash
downloads/
└── 2025-01-27_14-30-45/          # Timestamped session folder
    ├── images/                    # JPG, PNG, WebP files
    │   ├── 1.jpg
    │   ├── 1xyz789.png
    │   └── ...
    ├── videos/                    # MP4, WebM, MOV files
    │   ├── 1kqz723_Amazing video_video.mp4
    │   ├── 1abc456_Reddit video_audio.mp4
    │   └── ...
    ├── gifs/                      # Animated GIF files
    │   ├── 1kpgfko.gif
    │   ├── 1def123_Funny reaction.gif
    │   └── ...
    └── other/                     # Any other file types
        └── ...
```

**Final summary shows file counts:**

```bash
Download complete!
   ✓ Successful: 278
   ✗ Failed: 7
   Files saved to: ./downloads/2025-01-27_14-30-45
   Images: 156 files
   Videos: 89 files
   Gifs: 33 files
```

## Supported Media Types

| Type | Extensions | Details |
|------|------------|---------|
| **Images** | JPG, PNG, WebP | Highest resolution available |
| **Videos** | MP4, WebM, MOV | Reddit videos with separate audio tracks |
| **GIFs** | GIF | Animated GIFs and GifV (auto-converted to MP4) |
| **Galleries** | Multiple formats | All images from Reddit gallery posts |
| **External** | Various | Direct media URLs from imgur, redgifs, etc. |

## Technical Details

- **Stealth scraping**: Camoufox (anti-detect Firefox) with automatic fingerprint rotation
- **Smart parsing**: Handles Reddit's complex data structures (galleries, videos, previews)
- **Rate limiting**: 1.5s delay between API pages + exponential backoff on 429s
- **High performance**: 16 concurrent workers for optimal download speed
- **Cross-platform**: Sanitizes filenames for Windows/Mac/Linux compatibility
- **Anti-blocking**: Proper HTTP headers and user agent rotation
- **Memory efficient**: Streams large files without loading into memory

## License

GPL-3.0

---

**⭐ Star this repo if it helped you download your favorite Reddit media!**
