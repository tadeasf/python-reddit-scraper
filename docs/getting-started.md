# Getting Started

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) package manager (for development) **or** [pipx](https://pipx.pypa.io/) (for global install)

## Installation

### Option A: Development install (with uv)

#### 1. Clone the repository

```bash
git clone https://github.com/tadeasf/python-reddit-scraper.git
cd python-reddit-scraper
```

#### 2. Install dependencies

```bash
uv sync
```

#### 3. Download the stealth browser binary

This is a one-time setup (~80 MB):

```bash
uv run camoufox fetch
```

!!! note
    The tool will remind you to run `uv run camoufox fetch` if the binary is missing.

With this setup, run the tool via `uv run download-reddit-media`.

### Option B: Global install (use anywhere)

Install globally with [pipx](https://pipx.pypa.io/) so you can use it from any directory:

```bash
pipx install git+https://github.com/tadeasf/python-reddit-scraper.git
camoufox fetch
```

!!! tip
    After a global install you run `download-reddit-media` directly — no `uv run` prefix needed.
    The `camoufox` command is also available globally via pipx's injected scripts.

## First Run

### Interactive mode

```bash
# uv
uv run download-reddit-media

# Global install
download-reddit-media
```

You'll be prompted to enter subreddit names:

```
Enter subreddits (comma-separated): wallpapers,earthporn
```

### Direct mode

```bash
download-reddit-media -s wallpapers,earthporn
```

### Custom output directory

By default files are saved to `./downloads/` in the current working directory.
Use `-o` / `--output-dir` to change it:

```bash
download-reddit-media -s wallpapers -o ~/Pictures/reddit
```

## Output Structure

Files are organized by subreddit and media type:

```
<output-dir>/
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
