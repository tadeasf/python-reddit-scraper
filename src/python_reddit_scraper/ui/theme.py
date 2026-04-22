"""Central colour palette and formatting helpers.

A single coherent look across the CLI: rich markup for output, prompt_toolkit
styles for input. The two styling systems are kept in sync here so a change to
a colour in one place flows everywhere.
"""

from __future__ import annotations

from prompt_toolkit.styles import Style as PtStyle
from rich.style import Style

KEY = "bold cyan"
DEFAULT_HINT = "dim"
VALUE = "white"
OK = "bold green"
WARN = "bold yellow"
FAIL = "bold red"
MUTED = "grey50"
ACCENT = "magenta"
BANNER = "bold cyan"
BORDER = "cyan"

LEVEL_COLORS: dict[str, str] = {
    "TRACE": "dim",
    "DEBUG": "cyan",
    "INFO": "white",
    "SUCCESS": "bold green",
    "WARNING": "bold yellow",
    "ERROR": "bold red",
    "CRITICAL": "bold red on white",
}

LOGURU_FORMAT = "<dim>{time:HH:mm:ss}</dim> <level>{level: <8}</level> <dim>│</dim> {message}"


def key_value(label: str, value: object) -> str:
    """Render a ``[LABEL:] value`` line as rich-markup text."""
    return f"[{KEY}]\\[{label.upper()}:][/{KEY}] [{VALUE}]{value}[/{VALUE}]"


def label(text: str) -> str:
    """Bold-cyan ``[LABEL:]`` prefix (no trailing value)."""
    return f"[{KEY}]\\[{text.upper()}:][/{KEY}]"


PROMPT_STYLE = PtStyle.from_dict(
    {
        "": "",
        "key": "bold ansicyan",
        "hint": "ansibrightblack",
        "separator": "ansibrightblack",
        "dialog": "bg:#1a1a1a",
        "dialog.body": "bg:#1a1a1a #ffffff",
        "dialog frame.label": "bold ansicyan",
        "dialog.body radio-selected": "ansimagenta",
        "dialog.body radio-checked": "ansimagenta",
        "error": "bold ansired",
    }
)

RICH_BORDER_STYLE = Style(color="cyan")
RICH_TITLE_STYLE = Style(color="cyan", bold=True)
