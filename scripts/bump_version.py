#!/usr/bin/env python3
"""Pre-commit hook that optionally bumps the project version.

Reads the current version from pyproject.toml, prompts the user via /dev/tty,
and (if requested) bumps major/minor/patch in both pyproject.toml and
src/python_reddit_scraper/__init__.py, then stages the changed files.
"""

import re
import subprocess
import sys
from pathlib import Path

PYPROJECT = Path("pyproject.toml")
INIT_PY = Path("src/python_reddit_scraper/__init__.py")


def read_version() -> str:
    """Extract the current version string from pyproject.toml."""
    text = PYPROJECT.read_text()
    match = re.search(r'^version\s*=\s*"(\d+\.\d+\.\d+)"', text, re.MULTILINE)
    if not match:
        print("Could not parse version from pyproject.toml", file=sys.stderr)
        sys.exit(1)
    return match.group(1)


def bump(version: str, part: str) -> str:
    """Return *version* with the chosen *part* incremented."""
    major, minor, patch = (int(x) for x in version.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def write_version(new: str) -> None:
    """Update the version in pyproject.toml and __init__.py."""
    # pyproject.toml
    text = PYPROJECT.read_text()
    text = re.sub(
        r'^(version\s*=\s*")(\d+\.\d+\.\d+)(")',
        rf"\g<1>{new}\g<3>",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    PYPROJECT.write_text(text)

    # __init__.py
    if INIT_PY.exists():
        init = INIT_PY.read_text()
        init = re.sub(
            r'^(__version__\s*=\s*")(\d+\.\d+\.\d+)(")',
            rf"\g<1>{new}\g<3>",
            init,
            count=1,
            flags=re.MULTILINE,
        )
        INIT_PY.write_text(init)


def main() -> None:
    current = read_version()
    new = bump(current, "patch")
    write_version(new)
    print(f"  Bumped version: {current} -> {new}", file=sys.stderr)

    # Stage the modified files so they're included in this commit
    subprocess.run(["git", "add", str(PYPROJECT), str(INIT_PY)], check=True)


if __name__ == "__main__":
    main()
