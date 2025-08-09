#!/usr/bin/env python3
"""
Simple Reddit media downloader.
Parses JSON files in ./input and downloads all media at highest resolution
using 8 parallel workers.
"""

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from tqdm import tqdm


def sanitize_filename(text: str, max_length: int = 100) -> str:
    """Convert text to a safe filename."""
    text = re.sub(r"[\s\n\r\t]+", " ", text).strip()
    text = re.sub(r"[^\w\-_.()\[\]{} ]", "", text)
    if len(text) > max_length:
        text = text[: max_length - 3] + "..."
    return text or "untitled"


def get_file_extension(url: str) -> str:
    """Extract file extension from URL."""
    parsed = urlparse(url)
    path = parsed.path.lower()
    if "." in path:
        ext = path.split(".")[-1]
        # Common media extensions
        if ext in ["jpg", "jpeg", "png", "gif", "webp", "mp4", "webm", "mov"]:
            return f".{ext}"
    return ".bin"


def get_media_type(filename: str) -> str:
    """Determine media type from filename for directory sorting."""
    ext = Path(filename).suffix.lower()
    if ext in [".jpg", ".jpeg", ".png", ".webp"]:
        return "images"
    elif ext in [".gif"]:
        return "gifs"
    elif ext in [".mp4", ".webm", ".mov"]:
        return "videos"
    else:
        return "other"


def extract_media_urls(post_data: Dict) -> List[Dict[str, str]]:
    """Extract all media URLs from a Reddit post at highest resolution."""
    media_urls = []
    post_id = post_data.get("id", "unknown")
    title = post_data.get("title", "")
    safe_title = sanitize_filename(title)

    # 1. Direct media URL (highest priority)
    direct_url = post_data.get("url_overridden_by_dest")
    if direct_url and is_media_url(direct_url):
        media_urls.append(
            {
                "url": direct_url.replace("&amp;", "&"),
                "filename": f"{post_id}_{safe_title}{get_file_extension(direct_url)}",
            }
        )
        return media_urls  # If we have direct URL, prefer it

    # 2. Gallery posts
    if post_data.get("is_gallery") and post_data.get("media_metadata"):
        gallery_items = post_data.get("gallery_data", {}).get("items", [])
        media_metadata = post_data["media_metadata"]

        for i, item in enumerate(gallery_items):
            media_id = item.get("media_id")
            if media_id and media_id in media_metadata:
                meta = media_metadata[media_id]
                # Get highest quality image
                if "s" in meta and "u" in meta["s"]:
                    url = meta["s"]["u"].replace("&amp;", "&")
                    media_urls.append(
                        {
                            "url": url,
                            "filename": f"{post_id}_{safe_title}_{i+1}{get_file_extension(url)}",
                        }
                    )

    # 3. Reddit videos
    if post_data.get("is_video") or post_data.get("media"):
        media = post_data.get("media") or post_data.get("secure_media")
        if media and "reddit_video" in media:
            video = media["reddit_video"]
            if "fallback_url" in video:
                video_url = video["fallback_url"]
                media_urls.append(
                    {"url": video_url, "filename": f"{post_id}_{safe_title}_video.mp4"}
                )

                # Try to get audio too
                base_url = video_url.rsplit("/", 1)[0]
                audio_url = f"{base_url}/DASH_audio.mp4"
                media_urls.append(
                    {"url": audio_url, "filename": f"{post_id}_{safe_title}_audio.mp4"}
                )

    # 4. Preview images/GIFs
    preview = post_data.get("preview", {})
    if "images" in preview and preview["images"]:
        image_data = preview["images"][0]

        # Check for GIF variant first
        variants = image_data.get("variants", {})
        if "gif" in variants and "source" in variants["gif"]:
            gif_url = variants["gif"]["source"]["url"].replace("&amp;", "&")
            media_urls.append(
                {"url": gif_url, "filename": f"{post_id}_{safe_title}_preview.gif"}
            )
        elif "mp4" in variants and "source" in variants["mp4"]:
            mp4_url = variants["mp4"]["source"]["url"].replace("&amp;", "&")
            media_urls.append(
                {"url": mp4_url, "filename": f"{post_id}_{safe_title}_preview.mp4"}
            )
        # Get highest res image
        elif "source" in image_data:
            img_url = image_data["source"]["url"].replace("&amp;", "&")
            media_urls.append(
                {
                    "url": img_url,
                    "filename": f"{post_id}_{safe_title}_preview{get_file_extension(img_url)}",
                }
            )

    # 5. Handle gifv links (convert to mp4)
    if direct_url and direct_url.endswith(".gifv"):
        mp4_url = direct_url[:-5] + ".mp4"
        media_urls.append({"url": mp4_url, "filename": f"{post_id}_{safe_title}.mp4"})

    return media_urls


def is_media_url(url: str) -> bool:
    """Check if URL points to a media file."""
    url_lower = url.lower()
    return any(
        ext in url_lower
        for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".webm", ".mov"]
    )


def download_file(url: str, filepath: str, pbar: tqdm) -> bool:
    """Download a file from URL to filepath."""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        }

        req = Request(url, headers=headers)
        with urlopen(req, timeout=30) as response:
            with open(filepath, "wb") as f:
                f.write(response.read())

        pbar.set_postfix_str(f"Downloaded: {Path(filepath).name}")
        return True

    except Exception as e:
        pbar.set_postfix_str(f"Failed: {Path(filepath).name}")
        return False


def parse_json_files(input_dir: str) -> List[Dict]:
    """Parse all JSON files in input directory and extract posts."""
    posts = []
    input_path = Path(input_dir)

    if not input_path.exists():
        print(f"Input directory {input_dir} does not exist!")
        return posts

    json_files = list(input_path.glob("*.json"))
    print(f"Found {len(json_files)} JSON files")

    for json_file in json_files:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Handle Reddit listing format
            if isinstance(data, dict) and "data" in data and "children" in data["data"]:
                for child in data["data"]["children"]:
                    if "data" in child:
                        posts.append(child["data"])
            # Handle single post format
            elif isinstance(data, dict) and "data" in data:
                posts.append(data["data"])
            # Handle array format
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "data" in item:
                        if "children" in item["data"]:
                            for child in item["data"]["children"]:
                                if "data" in child:
                                    posts.append(child["data"])
                        else:
                            posts.append(item["data"])

        except Exception as e:
            print(f"Error parsing {json_file}: {e}")

    return posts


def main():
    """Main function to parse JSON files and download media."""
    input_dir = "./input"
    base_output_dir = "./downloads"

    # Create timestamped output directory
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = os.path.join(base_output_dir, timestamp)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Create subdirectories
    for subdir in ["images", "videos", "gifs", "other"]:
        Path(output_dir, subdir).mkdir(exist_ok=True)

    print("🚀 Starting Reddit media downloader...")
    print(f"📁 Output directory: {output_dir}")

    # Parse all JSON files
    posts = parse_json_files(input_dir)
    print(f"Found {len(posts)} posts to process")

    if not posts:
        print("No posts found. Make sure JSON files are in ./input directory")
        return

    # Extract all media URLs
    all_downloads = []
    seen_urls = set()

    print("🔍 Extracting media URLs...")
    for post in posts:
        media_urls = extract_media_urls(post)
        for media in media_urls:
            url = media["url"]
            if url not in seen_urls:
                seen_urls.add(url)
                # Sort into appropriate subdirectory
                media_type = get_media_type(media["filename"])
                filepath = os.path.join(output_dir, media_type, media["filename"])
                all_downloads.append((url, filepath))

    print(f"Found {len(all_downloads)} unique media files to download")

    if not all_downloads:
        print("No media URLs found to download")
        return

    # Download files concurrently with 16 workers
    print("📥 Starting downloads with 16 parallel workers...")

    successful = 0
    failed = 0

    # Create progress bar
    pbar = tqdm(
        total=len(all_downloads),
        desc="Downloading",
        unit="files",
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}] {postfix}",
    )

    with ThreadPoolExecutor(max_workers=16) as executor:
        # Submit all download tasks
        future_to_download = {
            executor.submit(download_file, url, filepath, pbar): (url, filepath)
            for url, filepath in all_downloads
        }

        # Process completed downloads
        for future in as_completed(future_to_download):
            success = future.result()
            if success:
                successful += 1
            else:
                failed += 1
            pbar.update(1)

    pbar.close()

    print(f"\n🎉 Download complete!")
    print(f"   ✓ Successful: {successful}")
    print(f"   ✗ Failed: {failed}")
    print(f"   📁 Files saved to: {output_dir}")

    # Show file count by type
    for subdir in ["images", "videos", "gifs"]:
        subdir_path = Path(output_dir, subdir)
        file_count = len(list(subdir_path.glob("*")))
        if file_count > 0:
            print(f"   📂 {subdir.capitalize()}: {file_count} files")


if __name__ == "__main__":
    main()
