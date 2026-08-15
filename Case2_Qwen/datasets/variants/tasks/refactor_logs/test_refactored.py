"""Comprehensive test suite for refactored log summarizer."""

import pytest

from counter import count_levels
from formatter import format_summary
from ugly import summarize


# ---------------------------------------------------------------------------
# Counter tests  (counter.py — happy paths, boundaries, invalid inputs)
# ---------------------------------------------------------------------------

def test_count_levels_happy_path():
    """Basic counting: three INFOs and two ERRORs."""
    # Format: <token> <LEVEL> <message> -> line.split(" ")[1] = LEVEL
    lines = ["tok INFO a", "tok ERROR b", "tok INFO c", "tok ERROR d"]
    assert count_levels(lines) == {"INFO": 2, "ERROR": 2}


def test_count_levels_single_level():
    """All lines share the same level."""
    assert count_levels(["t WARN x", "t WARN y", "t WARN z"]) == {"WARN": 3}


def test_count_levels_empty_list():
    """Empty input yields an empty dict (no error)."""
    assert count_levels([]) == {}


def test_count_levels_single_line():
    """Exactly one line returns a single-entry dict."""
    assert count_levels(["t INFO hello"]) == {"INFO": 1}


def test_count_levels_many_unique_levels():
    """Many distinct levels each appearing once."""
    assert count_levels(
        ["t A", "t B", "t C"]
    ) == {"A": 1, "B": 1, "C": 1}


def test_count_levels_malformed_line_raises_value_error():
    """Line with fewer than two parts raises ValueError."""
    with pytest.raises(ValueError):
        count_levels(["only_one_part"])


def test_count_levels_empty_string_raises_value_error():
    """An empty string line raises ValueError (split yields only [''])."""
    with pytest.raises(ValueError):
        count_levels([""])


# ---------------------------------------------------------------------------
# Formatter tests  (formatter.py — happy paths, boundaries, invalid inputs)
# ---------------------------------------------------------------------------

def test_format_summary_happy_path():
    """Counts sorted descending by default."""
    counts = {"INFO": 3, "ERROR": 2}
    assert format_summary(counts) == ["INFO:3", "ERROR:2"]


def test_format_summary_empty_counts_returns_empty_list():
    """An empty dict returns an empty list (graceful fallback)."""
    assert format_summary({}) == []


def test_format_summary_ascending_sort_key():
    """Sort ascending when key is 'count' (no leading '-' prefix)."""
    counts = {"INFO": 3, "ERROR": 2}
    assert format_summary(counts, sort_key="count") == ["ERROR:2", "INFO:3"]


def test_format_summary_descending_sort_key_explicit():
    """Sort descending with explicit '-count' key."""
    counts = {"INFO": 3, "ERROR": 2}
    assert format_summary(counts, sort_key="-count") == ["INFO:3", "ERROR:2"]


# ---------------------------------------------------------------------------
# Integration tests  (ugly.py — full pipeline)
# ---------------------------------------------------------------------------

def test_summarize_happy_path():
    """Full pipeline returns sorted LEVEL:COUNT strings."""
    lines = [
        "tok INFO started",
        "tok ERROR failed",
        "tok INFO continued",
        "tok WARN slow",
    ]
    result = summarize(lines)
    assert result == ["INFO:2", "ERROR:1", "WARN:1"]


def test_summarize_malformed_lines_raises_value_error():
    """Malformed line propagates ValueError from the counter."""
    with pytest.raises(ValueError):
        summarize(["bad_line"])


def test_summarize_empty_input_returns_empty_list():
    """Empty input returns an empty list (no error)."""
    assert summarize([]) == []
