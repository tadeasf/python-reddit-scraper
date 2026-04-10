"""Media URL extraction, type detection, and filtering."""

import re
from pathlib import Path
from urllib.parse import urlparse


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


def is_media_url(url: str) -> bool:
    """Check if URL points to a media file."""
    url_lower = url.lower()
    return any(
        ext in url_lower
        for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".webm", ".mov"]
    )


def _build_audio_entries(video_url: str, post_id: str, safe_title: str) -> list[dict[str, str]]:
    """Build audio download entries for a Reddit video.

    Generates candidate audio URLs with ``?source=fallback`` and marks them
    as optional so the downloader can gracefully skip 403 responses.
    """
    base_url = video_url.rsplit("/", 1)[0]
    # Primary: DASH_audio.mp4 with fallback param (matches video URL pattern)
    # Alternatives: newer DASH_AUDIO_128/64 format used by some Reddit videos
    audio_urls = [
        f"{base_url}/DASH_audio.mp4?source=fallback",
        f"{base_url}/DASH_AUDIO_128.mp4?source=fallback",
        f"{base_url}/DASH_AUDIO_64.mp4?source=fallback",
    ]
    return [
        {
            "url": audio_urls[0],
            "filename": f"{post_id}_{safe_title}_audio.mp4",
            "optional": "true",
            "audio_fallbacks": "|".join(audio_urls[1:]),
        }
    ]


def extract_media_urls(post_data: dict) -> list[dict[str, str]]:
    """Extract all media URLs from a Reddit post at highest resolution."""
    if post_data is None or not isinstance(post_data, dict):
        return []

    media_urls: list[dict[str, str]] = []
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
        return media_urls

    # 2. Gallery posts
    if post_data.get("is_gallery") and post_data.get("media_metadata"):
        gallery_data = post_data.get("gallery_data") or {}
        gallery_items = gallery_data.get("items", [])
        media_metadata = post_data["media_metadata"]

        for i, item in enumerate(gallery_items):
            media_id = item.get("media_id")
            if media_id and media_id in media_metadata:
                meta = media_metadata[media_id]
                if "s" in meta and "u" in meta["s"]:
                    url = meta["s"]["u"].replace("&amp;", "&")
                    media_urls.append(
                        {
                            "url": url,
                            "filename": f"{post_id}_{safe_title}_{i + 1}{get_file_extension(url)}",
                        }
                    )

    # 3. Reddit-hosted videos (media.reddit_video)
    if post_data.get("is_video") or post_data.get("media"):
        media = post_data.get("media") or post_data.get("secure_media")
        if media and isinstance(media, dict) and "reddit_video" in media:
            video = media["reddit_video"]
            if "fallback_url" in video:
                video_url = video["fallback_url"]
                media_urls.append(
                    {"url": video_url, "filename": f"{post_id}_{safe_title}_video.mp4"}
                )
                media_urls.extend(_build_audio_entries(video_url, post_id, safe_title))

    # 4. Reddit video preview (embedded videos from redgifs, external hosts, etc.)
    preview = post_data.get("preview", {})
    if isinstance(preview, dict):
        rvp = preview.get("reddit_video_preview")
        if rvp and isinstance(rvp, dict) and "fallback_url" in rvp:
            video_url = rvp["fallback_url"]
            existing_video_urls = {m["url"] for m in media_urls}
            if video_url not in existing_video_urls:
                media_urls.append(
                    {"url": video_url, "filename": f"{post_id}_{safe_title}_video.mp4"}
                )

    # 5. Crossposted videos -- check parent post for video data
    crosspost_list = post_data.get("crosspost_parent_list")
    if crosspost_list and isinstance(crosspost_list, list):
        for cp in crosspost_list:
            if not isinstance(cp, dict):
                continue
            cp_media = cp.get("media") or cp.get("secure_media")
            if cp_media and isinstance(cp_media, dict) and "reddit_video" in cp_media:
                video = cp_media["reddit_video"]
                if "fallback_url" in video:
                    video_url = video["fallback_url"]
                    existing_video_urls = {m["url"] for m in media_urls}
                    if video_url not in existing_video_urls:
                        media_urls.append(
                            {
                                "url": video_url,
                                "filename": f"{post_id}_{safe_title}_video.mp4",
                            }
                        )
                        media_urls.extend(_build_audio_entries(video_url, post_id, safe_title))

    # 6. Preview images/GIFs
    if isinstance(preview, dict) and "images" in preview and preview["images"]:
        image_data = preview["images"][0]

        variants = image_data.get("variants", {})
        if "gif" in variants and "source" in variants["gif"]:
            gif_url = variants["gif"]["source"]["url"].replace("&amp;", "&")
            media_urls.append({"url": gif_url, "filename": f"{post_id}_{safe_title}_preview.gif"})
        elif "mp4" in variants and "source" in variants["mp4"]:
            mp4_url = variants["mp4"]["source"]["url"].replace("&amp;", "&")
            media_urls.append({"url": mp4_url, "filename": f"{post_id}_{safe_title}_preview.mp4"})
        elif "source" in image_data:
            has_video = any(get_media_type(m["filename"]) == "videos" for m in media_urls)
            if not has_video:
                img_url = image_data["source"]["url"].replace("&amp;", "&")
                media_urls.append(
                    {
                        "url": img_url,
                        "filename": f"{post_id}_{safe_title}_preview{get_file_extension(img_url)}",
                    }
                )

    # 7. Handle gifv links (convert to mp4)
    if direct_url and direct_url.endswith(".gifv"):
        mp4_url = direct_url[:-5] + ".mp4"
        media_urls.append({"url": mp4_url, "filename": f"{post_id}_{safe_title}.mp4"})

    # 8. Redgifs/external oembed thumbnail as last resort
    if not media_urls:
        media = post_data.get("media") or post_data.get("secure_media")
        if media and isinstance(media, dict):
            oembed = media.get("oembed")
            if oembed and isinstance(oembed, dict):
                thumb = oembed.get("thumbnail_url")
                if thumb and is_media_url(thumb):
                    media_urls.append(
                        {
                            "url": thumb.replace("&amp;", "&"),
                            "filename": f"{post_id}_{safe_title}_thumb{get_file_extension(thumb)}",
                        }
                    )

    return media_urls


def extract_all_media(posts: list[dict]) -> list[dict[str, str]]:
    """
    Extract all media URLs from a list of posts, deduplicating by URL.

    Returns list of dicts with 'url', 'filename', and 'subreddit' keys.
    """
    all_media: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for post in posts:
        if post is None or not isinstance(post, dict):
            continue
        subreddit = post.get("subreddit", "unknown")
        media_urls = extract_media_urls(post)
        for media in media_urls:
            url = media["url"]
            if url not in seen_urls:
                seen_urls.add(url)
                media["subreddit"] = subreddit
                all_media.append(media)

    return all_media


def filter_by_media_type(
    downloads: list[dict[str, str]],
    video_only: bool = False,
    image_only: bool = False,
) -> list[dict[str, str]]:
    """
    Filter media list by type.

    Args:
        downloads: List of dicts with 'url' and 'filename' keys.
        video_only: Keep only videos + gifs (animations).
        image_only: Keep only images.

    Returns:
        Filtered list.
    """
    if not video_only and not image_only:
        return downloads

    filtered = []
    for item in downloads:
        media_type = get_media_type(item["filename"])
        if (video_only and media_type in ("videos", "gifs")) or (
            image_only and media_type == "images"
        ):
            filtered.append(item)

    return filtered
