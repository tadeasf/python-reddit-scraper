# API Reference

Auto-generated documentation from source code docstrings.

## Scraper

### Core

The core scraper handles fetching Reddit JSON data via a stealth browser.

::: python_reddit_scraper.scraper.core
    options:
      show_root_heading: true
      members_order: source

### Parallel

Multi-process parallel scraping of multiple subreddits.

::: python_reddit_scraper.scraper.parallel
    options:
      show_root_heading: true
      members_order: source

### JSON I/O

JSON file reading and writing for scraped data.

::: python_reddit_scraper.scraper.json_io
    options:
      show_root_heading: true
      members_order: source

## Downloader

### Media

Media URL extraction, type detection, and filtering.

::: python_reddit_scraper.downloader.media
    options:
      show_root_heading: true
      members_order: source

### Engine

Concurrent file downloading with progress tracking.

::: python_reddit_scraper.downloader.engine
    options:
      show_root_heading: true
      members_order: source

### Session State

The state module manages resume/session persistence.

::: python_reddit_scraper.downloader.state
    options:
      show_root_heading: true
      members_order: source

## CLI

### Commands

The CLI commands module provides the main download command.

::: python_reddit_scraper.cli.commands
    options:
      show_root_heading: true
      members_order: source

### Prompt

Interactive prompts and environment checks.

::: python_reddit_scraper.cli.prompt
    options:
      show_root_heading: true
      members_order: source
