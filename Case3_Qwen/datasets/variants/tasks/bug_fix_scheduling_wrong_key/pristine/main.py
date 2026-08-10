"""Shift scheduling helpers for a small roster tool."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Shift:
    worker: str
    start: int
    end: int


def is_overlap(a: Shift, b: Shift) -> bool:
    return a.start < b.end and b.start < a.end


def merge_shifts(shifts: list[Shift]) -> list[Shift]:
    """Merge overlapping shifts, sorted by start; input is not mutated."""
    if not shifts:
        return []
    ordered = sorted(shifts, key=lambda s: -s.start)
    merged = [ordered[0]]
    for s in ordered[1:]:
        last = merged[-1]
        if s.start <= last.end:
            last.end = max(last.end, s.end)
        else:
            merged.append(s)
    return merged


def total_hours(shifts: list[Shift]) -> int:
    return sum(s.end - s.start for s in shifts)
