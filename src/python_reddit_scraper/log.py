"""Loguru logging configuration for the Reddit media downloader."""

import sys

from loguru import logger

logger.remove()

logger.add(
    sys.stderr,
    format=(
        "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
    ),
    level="INFO",
    colorize=True,
)
