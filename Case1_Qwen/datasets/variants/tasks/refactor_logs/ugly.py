"""Refactored log summarizer.

Public API:
    summarize(lines) -> list[str]
        Summarize a collection of log lines, returning sorted "LEVEL:COUNT" strings.

This module no longer uses global mutable state or mixes counting with formatting.
"""

from config import CONFIG
from counter import count_levels
from formatter import format_summary


def summarize(lines: list[str]) -> list[str]:
    """Summarize log lines into a sorted list of "LEVEL:COUNT" strings.

    This is the primary entry point. It delegates to ``counter.count_levels``
    for parsing and counting, then to ``formatter.format_summary`` for output.

    Args:
        lines: List of log lines (expected format: "<level> <message>").

    Returns:
        Sorted list of "LEVEL:COUNT" strings, sorted by count descending
        (default behaviour).

    Raises:
        ValueError: If any line cannot be parsed or if counts are empty.
    """
    counts = count_levels(lines)
    return format_summary(counts)
