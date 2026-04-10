# Getting Started

## Prerequisites

- Python 3.10+
- [Rye](https://rye.astral.sh/) package manager

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/tadeasf/python-reddit-scraper.git
cd python-reddit-scraper
```

### 2. Install dependencies

```bash
rye sync
```

### 3. Download the stealth browser binary

This is a one-time setup (~80 MB):

```bash
rye run camoufox fetch
```

!!! note
    The tool will remind you to run `rye run camoufox fetch` if the binary is missing.

## First Run

### Interactive mode

```bash
rye run download-reddit-media
```

You'll be prompted to enter subreddit names:

```
Enter subreddits (comma-separated): wallpapers,earthporn
```

### Direct mode

```bash
rye run download-reddit-media -s wallpapers,earthporn
```

## Output Structure

Files are organized by subreddit and media type:

```
downloads/
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

## Next Steps

- See [CLI Reference](cli-reference.md) for all available options
- See [API Reference](api-reference.md) for using the Python API directly
