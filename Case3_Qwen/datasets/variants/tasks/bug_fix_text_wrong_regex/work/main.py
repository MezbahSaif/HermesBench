"""Small text-processing helpers."""
from __future__ import annotations
import re


def slugify(text: str) -> str:
    """Lowercase; collapse non-alphanumerics into single hyphens."""
    lowered = text.lower().strip()
    cleaned = re.sub(r"[^a-z0-9]+", "-", lowered)
    return re.sub(r"-{2,}", "-", cleaned).strip("-")


def word_frequency(text: str, min_len: int = 3) -> dict[str, int]:
    counts: dict[str, int] = {}
    for token in text.split():
        word = token.strip(".,!?;:()\"'").lower()
        if len(word) >= min_len:
            counts[word] = counts.get(word, 0) + 1
    return counts


def sentence_split(text: str) -> list[str]:
    """Naive splitter (buggy): only '!' and '?' split."""
    pieces = re.split(r"(?<=[?.!])\s+", text.strip())
    return [p for p in pieces if p]
