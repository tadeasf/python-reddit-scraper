"""JSON I/O for scraped Reddit data."""

import json
from pathlib import Path

from loguru import logger


def save_scraped_json(
    posts: list[dict],
    subreddit: str,
    output_dir: str = "./input",
) -> str:
    """
    Save scraped posts to a JSON file compatible with the existing parser.

    Wraps posts in Reddit's listing format so parse_json_files() can read them.
    Returns the path to the saved file.
    """
    out_path = Path(output_dir) / subreddit
    out_path.mkdir(parents=True, exist_ok=True)

    listing = {
        "kind": "Listing",
        "data": {
            "children": [{"kind": "t3", "data": post} for post in posts],
            "after": None,
        },
    }

    filepath = out_path / "scraped.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(listing, f, ensure_ascii=False, indent=2)

    return str(filepath)


def parse_json_files(input_dir: str) -> list[dict]:
    """Parse all JSON files in input directory and extract posts."""
    posts: list[dict] = []
    input_path = Path(input_dir)

    if not input_path.exists():
        logger.error("Input directory {} does not exist!", input_dir)
        return posts

    json_files = sorted(set(list(input_path.glob("*.json")) + list(input_path.glob("**/*.json"))))
    logger.info("Found {} JSON files", len(json_files))

    for json_file in json_files:
        try:
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, dict) and "data" in data and "children" in data["data"]:
                for child in data["data"]["children"]:
                    if "data" in child:
                        posts.append(child["data"])
            elif isinstance(data, dict) and "data" in data:
                posts.append(data["data"])
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
            logger.error("Error parsing {}: {}", json_file, e)

    return posts
