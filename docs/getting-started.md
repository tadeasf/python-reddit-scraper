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

You'll be prompted for everything that isn't already configured:

1. **Subreddits** — `Enter subreddits (comma-separated): wallpapers,earthporn`
2. **Media types** — a checkbox dialog with `[x] images  [x] videos  [x] gifs`; press <kbd>Space</kbd> to toggle, <kbd>Enter</kbd> to confirm.
3. **Output directory** — press <kbd>Enter</kbd> to accept the shown default (`./redditdownloads`) or type a path (including `~`).
4. **Max pages per subreddit** — press <kbd>Enter</kbd> to accept `50` or type a positive integer.

Any option you pass on the command line (`-s`, `-o`, `--video-only`, `--max-pages`, …) skips the matching prompt. Any option you've saved via `configure` is loaded from `~/.config/python_reddit_scraper/config.yaml` and also skips the prompt.

### Saving defaults with `configure`

Run `configure` once to persist your preferred media types, output directory, and page depth:

```bash
download-reddit-media configure
```

This writes (or updates) the `defaults:` block in `~/.config/python_reddit_scraper/config.yaml` while leaving any `providers:` block intact. Re-run `configure` any time to change them.

### Direct mode (all flags)

```bash
download-reddit-media -s wallpapers,earthporn --video-only --max-pages 20 -o ~/Pictures/reddit
```

### Resolution order

For each option, the first rule that matches wins:

1. CLI flag (e.g. `--video-only`, `-o /tmp/x`).
2. `defaults:` block in `~/.config/python_reddit_scraper/config.yaml`.
3. Interactive prompt (requires a TTY — scripts should pass the flags instead).

### Custom output directory

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

## Configuration File

User configuration lives in `~/.config/python_reddit_scraper/config.yaml`. Both top-level blocks are optional.

```yaml
defaults:
  media_types: [images, videos, gifs]   # non-empty subset of these three
  output_dir: /home/you/redditdownloads
  max_pages: 50

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
```

!!! tip
    Use `download-reddit-media configure` to write the `defaults:` block — it preserves your `providers:` block on write.

### Proxy providers

- **webshare** — rotating proxies fetched via API on every run. Multiple accounts are tried in order; empty/invalid accounts are skipped.
- **proxy-cheap** — static HTTP endpoints. **SOCKS5 is not supported**: Camoufox is built on Playwright's Firefox, which cannot authenticate against SOCKS5 proxies (`Browser does not support socks5 proxy authentication`). Request an HTTP endpoint from your proxy-cheap dashboard.

## Next Steps

- See [CLI Reference](cli-reference.md) for all available options
- See [API Reference](api-reference.md) for using the Python API directly
