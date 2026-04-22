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

### Runtime

Shared runtime helpers used across CLI flows (env checks, config resolution).

::: python_reddit_scraper.cli.runtime
    options:
      show_root_heading: true
      members_order: source

### Configure

Interactive subcommand that writes user defaults to `config.yaml`.

::: python_reddit_scraper.cli.configure
    options:
      show_root_heading: true
      members_order: source

### History

`history` subcommand — lists past runs from the run log.

::: python_reddit_scraper.cli.history_cmd
    options:
      show_root_heading: true
      members_order: source

### Flows — Live

End-to-end scrape + download flow with a live dashboard.

::: python_reddit_scraper.cli.flows.live
    options:
      show_root_heading: true
      members_order: source

### Flows — Resume

Resume flow for continuing a previously interrupted download session.

::: python_reddit_scraper.cli.flows.resume
    options:
      show_root_heading: true
      members_order: source

## UI

### Prompts

Interactive prompts (fuzzy-completed, styled) used by the CLI flows.

::: python_reddit_scraper.ui.prompts
    options:
      show_root_heading: true
      members_order: source

### Theme

Shared color palette and `prompt_toolkit` styles.

::: python_reddit_scraper.ui.theme
    options:
      show_root_heading: true
      members_order: source

### Banner, Spinner, Summary, Tables

Rich-based UI helpers — startup banner, run summary, preflight and history tables.

::: python_reddit_scraper.ui.banner
    options:
      show_root_heading: true
      members_order: source

::: python_reddit_scraper.ui.spinner
    options:
      show_root_heading: true
      members_order: source

::: python_reddit_scraper.ui.summary
    options:
      show_root_heading: true
      members_order: source

::: python_reddit_scraper.ui.preflight_table
    options:
      show_root_heading: true
      members_order: source

::: python_reddit_scraper.ui.history_table
    options:
      show_root_heading: true
      members_order: source

## Config

User configuration loader — defaults, proxy providers, and YAML read/write.

::: python_reddit_scraper.config
    options:
      show_root_heading: true
      members_order: source
