# Reddit Media Downloader

A fast and organized Python script that parses saved Reddit JSON files and downloads all media (images, videos, GIFs) at the highest available resolution with real-time progress tracking.

## ✨ Features

- **🎯 High-quality downloads**: Automatically selects highest resolution media
- **⚡ Fast concurrent downloads**: Uses 16 parallel workers for maximum speed
- **📁 Smart organization**: Auto-sorts files into `images/`, `videos/`, and `gifs/` subdirectories
- **📊 Real-time progress**: Beautiful progress bar with download rate and time estimation
- **📅 Timestamped sessions**: Creates dated directories for each download session
- **🔄 Deduplication**: Avoids downloading the same file twice
- **🧹 Clean dependencies**: Minimal setup with only `tqdm` required

## 🚀 Installation

Install dependencies using Rye:

```bash
rye sync
```

## 📖 Usage

### 1. Prepare JSON files

Save Reddit JSON data to the `./input` directory.

**Example for r/{subreddit}:**

- **Page 1**: `https://old.reddit.com/r/subreddit.json?limit=100&raw_json=1` → Save as `./input/1.json`
- **Find pagination**: Look for the `data.after` value in `1.json` (e.g. `t3_abc123`)
- **Page 2**: `https://old.reddit.com/r/subreddit.json?limit=100&raw_json=1&after=t3_abc123` → Save as `./input/2.json`
- **Continue**: Repeat until `data.after` is null (end of subreddit)

### 2. Run the downloader

**Direct execution:**

```bash
python src/python_reddit_scraper/download_reddit_media.py
```

**Or using the installed script:**

```bash
rye run download-reddit-media
```

### 3. Watch the magic happen! ✨

The script will show a beautiful progress bar with real-time stats:

```bash
🚀 Starting Reddit media downloader...
📁 Output directory: ./downloads/2025-01-27_14-30-45
Found 150 posts to process
🔍 Extracting media URLs...
Found 285 unique media files to download
📥 Starting downloads with 16 parallel workers...
Downloading: 100%|██████████| 285/285 [02:45<00:00, 1.72files/s] Downloaded: amazing_video.mp4
```

## 📂 Output Structure

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
🎉 Download complete!
   ✓ Successful: 278
   ✗ Failed: 7
   📁 Files saved to: ./downloads/2025-01-27_14-30-45
   📂 Images: 156 files
   📂 Videos: 89 files
   📂 Gifs: 33 files
```

## 🎯 Supported Media Types

| Type | Extensions | Details |
|------|------------|---------|
| **📸 Images** | JPG, PNG, WebP | Highest resolution available |
| **🎬 Videos** | MP4, WebM, MOV | Reddit videos with separate audio tracks |
| **🎞️ GIFs** | GIF | Animated GIFs and GifV (auto-converted to MP4) |
| **🖼️ Galleries** | Multiple formats | All images from Reddit gallery posts |
| **🔗 External** | Various | Direct media URLs from imgur, redgifs, etc. |

## ⚙️ Technical Details

- **🐍 Minimal dependencies**: Python standard library + `tqdm` only
- **🧠 Smart parsing**: Handles Reddit's complex data structures (galleries, videos, previews)
- **🚀 High performance**: 16 concurrent workers for optimal download speed
- **🌍 Cross-platform**: Sanitizes filenames for Windows/Mac/Linux compatibility
- **🛡️ Anti-blocking**: Proper HTTP headers and user agent rotation
- **💾 Memory efficient**: Streams large files without loading into memory

## 📜 License

GPL-3.0

---

**⭐ Star this repo if it helped you download your favorite Reddit media!**
