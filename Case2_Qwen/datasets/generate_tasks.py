"""HermesBench task-variant generator (Software Engineering domain).

Borrows the saif.py pattern: combinatorial per-family seed spaces, strict
self-validation (every variant is scored with the real graders: the reference
solution must score >= 1.0 and a buggy counterpart must score < 1.0), content
dedup via variant names, and resumable output.

Families (difficulty medium -> complex, all fully deterministic, no LLM):

  bug_fix            medium   fix a seeded logic bug in a ~50-line module
  implement_function medium   implement a function from a spec + stub file
  refactor           medium   split a god function; banned anti-patterns
  fastapi_setup      medium   build a small FastAPI app (static checks)
  docker_configure   medium   Dockerfile + compose for a provided app
  write_tests        hard     tests must pass on good module, fail on buggy
  cli_tool           complex  build a CLI tool; stdout compared exactly

Each round emits a dataset CSV (`round_<n>_se.csv`) with fresh parameter
combinations; `family` stays constant so recovery-rate analysis can match
variants across rounds.

Usage:
    python datasets/generate_tasks.py --list
    python datasets/generate_tasks.py --rounds 5 --per-family 2 --seed 42
    python datasets/generate_tasks.py --families bug_fix,cli_tool --rounds 2
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

BENCH_ROOT = Path(__file__).resolve().parent.parent
if str(BENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(BENCH_ROOT))

from benchmark.graders import grade  # noqa: E402
from benchmark.task_loader import Task  # noqa: E402

GEN_VERSION = "2.0-se"

ROLE = (
    "You are a software engineer working on a real codebase. Be precise: "
    "write clean, working code and verify your own work before finishing."
)
OUTPUT_RULE = (
    "Edit the files in the workdir using your file tools. When you provide "
    "code in your reply, wrap each file in a code fence named after the file "
    "path (e.g. ```python\n# main.py\n...\n```)."
)
CONTEXT_RULE = "Workdir files you may need: {files}."


def _task_row(name: str, family: str, difficulty: str, prompt: str,
              check_type: str, expected: str, banned: list[str]) -> dict:
    return {
        "name": name,
        "family": family,
        "difficulty": difficulty,
        "prompt": prompt,
        "check_type": check_type,
        "expected": expected,
        "threshold": 0.8 if "+" in check_type else 0.7,
        "rubric": (
            f"{family} ({difficulty}): correct, working solution that "
            "satisfies every automated check."
        ),
        "banned": banned,
    }


def _work_files(fixtures: list[tuple[str, str]]) -> str:
    return ", ".join(rel for rel, _ in fixtures)


# ---------------------------------------------------------------- bug_fix
def _bug_fix_variants() -> list[dict]:
    specs = [
        _BUG_FIX_FINANCE,
        _BUG_FIX_TEXT,
        _BUG_FIX_SCHEDULING,
    ]
    out = []
    for domain in specs:
        for bug_kind, buggy in domain["buggy"].items():
            name = f"bug_fix_{domain['slug']}_{bug_kind}"
            prompt = (
                f"{ROLE}\n\n"
                f"{CONTEXT_RULE.format(files='main.py')}\n\n"
                f"TASK: The module `main.py` contains a software defect "
                f"({domain['blurb']}). Find the bug and fix it IN PLACE in "
                f"{domain['work']}. Do not change the module's public API, "
                f"do not add new dependencies, do not weaken behavior.\n"
                f"Files in the workdir are yours to edit.\n"
                f"Difficulty: {domain['difficulty']}.\n"
                f"{OUTPUT_RULE}\n"
                f"Expected: the fixed module passes all of the project's "
                f"unit tests (run them if you can)."
            )
            variant = _task_row(
                name, "bug_fix", "medium", prompt,
                "file_code_exec", "main.py\n" + domain["tests"], [],
            )
            variant["fixtures"] = [("main.py", buggy)]
            variant["reference"] = {"file": "main.py", "content": domain["good"]}
            variant["negative"] = {"file": "main.py", "content": buggy}
            out.append(variant)
    return out


_BUG_FIX_FINANCE = {
    "slug": "finance",
    "blurb": "invoice total computation",
    "work": "main.py (invoice parsing, subtotal, bulk discount, tax)",
    "difficulty": "medium (a ~50-line module with a seeded logic bug)",
    "good": '''"""Invoice processing utilities.

Provides parsing and totals for a small invoicing tool.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class LineItem:
    sku: str
    name: str
    qty: int
    unit_price: float


def parse_lines(rows: list[str]) -> list[LineItem]:
    """Parse 'sku,name,qty,price' rows into LineItem objects.

    Malformed rows are skipped.
    """
    items = []
    for row in rows:
        parts = [p.strip() for p in row.split(",")]
        if len(parts) != 4:
            continue
        try:
            items.append(LineItem(parts[0], parts[1], int(parts[2]),
                                  float(parts[3])))
        except ValueError:
            continue
    return items


def compute_subtotal(items: list[LineItem]) -> float:
    total = 0.0
    for it in items:
        total += it.qty * it.unit_price
    return round(total, 2)


def apply_bulk_discount(subtotal: float, min_amount: float = 500.0,
                        rate: float = 0.10) -> float:
    """Subtotals at or above min_amount get rate % off."""
    if subtotal >= min_amount:
        return round(subtotal * (1.0 - rate), 2)
    return round(subtotal, 2)


def compute_tax(amount: float, tax_rate: float = 0.075) -> float:
    return round(amount * tax_rate, 2)
''',
    "buggy": {
        "offbyone": '''"""Invoice processing utilities.

Provides parsing and totals for a small invoicing tool.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class LineItem:
    sku: str
    name: str
    qty: int
    unit_price: float


def parse_lines(rows: list[str]) -> list[LineItem]:
    """Parse 'sku,name,qty,price' rows into LineItem objects.

    Malformed rows are skipped.
    """
    items = []
    for row in rows:
        parts = [p.strip() for p in row.split(",")]
        if len(parts) != 4:
            continue
        try:
            items.append(LineItem(parts[0], parts[1], int(parts[2]),
                                  float(parts[3])))
        except ValueError:
            continue
    return items


def compute_subtotal(items: list[LineItem]) -> float:
    total = 0.0
    for it in items[:-1]:
        total += it.qty * it.unit_price
    return round(total, 2)


def apply_bulk_discount(subtotal: float, min_amount: float = 500.0,
                        rate: float = 0.10) -> float:
    """Subtotals at or above min_amount get rate % off."""
    if subtotal >= min_amount:
        return round(subtotal * (1.0 - rate), 2)
    return round(subtotal, 2)


def compute_tax(amount: float, tax_rate: float = 0.075) -> float:
    return round(amount * tax_rate, 2)
''',
        "wrong_compare": '''"""Invoice processing utilities.

Provides parsing and totals for a small invoicing tool.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class LineItem:
    sku: str
    name: str
    qty: int
    unit_price: float


def parse_lines(rows: list[str]) -> list[LineItem]:
    """Parse 'sku,name,qty,price' rows into LineItem objects.

    Malformed rows are skipped.
    """
    items = []
    for row in rows:
        parts = [p.strip() for p in row.split(",")]
        if len(parts) != 4:
            continue
        try:
            items.append(LineItem(parts[0], parts[1], int(parts[2]),
                                  float(parts[3])))
        except ValueError:
            continue
    return items


def compute_subtotal(items: list[LineItem]) -> float:
    total = 0.0
    for it in items:
        total += it.qty * it.unit_price
    return round(total, 2)


def apply_bulk_discount(subtotal: float, min_amount: float = 500.0,
                        rate: float = 0.10) -> float:
    """Subtotals strictly above min_amount get rate % off."""
    if subtotal > min_amount:
        return round(subtotal * (1.0 - rate), 2)
    return round(subtotal, 2)


def compute_tax(amount: float, tax_rate: float = 0.075) -> float:
    return round(amount * tax_rate, 2)
''',
        "bad_default": '''"""Invoice processing utilities.

Provides parsing and totals for a small invoicing tool.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class LineItem:
    sku: str
    name: str
    qty: int
    unit_price: float


def parse_lines(rows: list[str]) -> list[LineItem]:
    """Parse 'sku,name,qty,price' rows into LineItem objects.

    Malformed rows are skipped.
    """
    items = []
    for row in rows:
        parts = [p.strip() for p in row.split(",")]
        if len(parts) != 4:
            continue
        try:
            items.append(LineItem(parts[0], parts[1], int(parts[2]),
                                  float(parts[3])))
        except ValueError:
            continue
    return items


def compute_subtotal(items: list[LineItem]) -> float:
    total = 0.0
    for it in items:
        total += it.qty * it.unit_price
    return round(total, 2)


def apply_bulk_discount(subtotal: float, min_amount: float = 500.0,
                        rate: float = 0.10) -> float:
    """Subtotals at or above min_amount get rate % off."""
    if subtotal >= min_amount:
        return round(subtotal * (1.0 - rate), 2)
    return round(subtotal, 2)


def compute_tax(amount: float, tax_rate: float = 0.25) -> float:
    return round(amount * tax_rate, 2)
''',
        "wrong_accum": '''"""Invoice processing utilities.

Provides parsing and totals for a small invoicing tool.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class LineItem:
    sku: str
    name: str
    qty: int
    unit_price: float


def parse_lines(rows: list[str]) -> list[LineItem]:
    """Parse 'sku,name,qty,price' rows into LineItem objects.

    Malformed rows are skipped.
    """
    items = []
    for row in rows:
        parts = [p.strip() for p in row.split(",")]
        if len(parts) != 4:
            continue
        try:
            items.append(LineItem(parts[0], parts[1], int(parts[2]),
                                  float(parts[3])))
        except ValueError:
            continue
    return items


def compute_subtotal(items: list[LineItem]) -> float:
    total = 0.0
    for it in items:
        total += it.unit_price
    return round(total, 2)


def apply_bulk_discount(subtotal: float, min_amount: float = 500.0,
                        rate: float = 0.10) -> float:
    """Subtotals at or above min_amount get rate % off."""
    if subtotal >= min_amount:
        return round(subtotal * (1.0 - rate), 2)
    return round(subtotal, 2)


def compute_tax(amount: float, tax_rate: float = 0.075) -> float:
    return round(amount * tax_rate, 2)
''',
    },
    "tests": '''check("parses 3 rows",
      len(mod.parse_lines(["a,x,2,1.5", "b,y,3,2.0", "c,z,1,0.5"])) == 3)
check("skips malformed",
      len(mod.parse_lines(["a,x,2,1.5", "oops", "b,y,3,2.0"])) == 2)
items = mod.parse_lines(["a,x,2,1.5", "b,y,3,2.0"])
check("subtotal", mod.compute_subtotal(items) == 9.0)
check("subtotal counts last item",
      mod.compute_subtotal(mod.parse_lines(["a,x,1,1.0", "b,y,1,1.0", "c,z,1,1.0"])) == 3.0)
check("bulk at boundary", mod.apply_bulk_discount(500.0) == 450.0)
check("bulk above", mod.apply_bulk_discount(600.0) == 540.0)
check("no bulk below", mod.apply_bulk_discount(499.99) == 499.99)
check("tax default", mod.compute_tax(100.0) == 7.5)
check("tax explicit", mod.compute_tax(100.0, 0.10) == 10.0)
check("qty matters", mod.compute_subtotal(mod.parse_lines(["a,x,4,1.0"])) == 4.0)
''',
}

_BUG_FIX_TEXT = {
    "slug": "text",
    "blurb": "text-processing helpers",
    "work": "main.py (slugify, word frequency, sentence splitting)",
    "difficulty": "medium (a ~40-line module with a seeded logic bug)",
    "good": '''"""Small text-processing helpers."""
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
        word = token.strip(".,!?;:()\\"'").lower()
        if len(word) >= min_len:
            counts[word] = counts.get(word, 0) + 1
    return counts


def sentence_split(text: str) -> list[str]:
    """Naive splitter: '.', '!', '?' followed by whitespace/end."""
    pieces = re.split(r"(?<=[.!?])\\s+", text.strip())
    return [p for p in pieces if p]
''',
    "buggy": {
        "swapped": '''"""Small text-processing helpers."""
from __future__ import annotations
import re


def slugify(text: str) -> str:
    """Lowercase; collapse non-alphanumerics into single hyphens."""
    lowered = text.strip()
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", lowered)
    return re.sub(r"-{2,}", "-", cleaned).strip("-")


def word_frequency(text: str, min_len: int = 3) -> dict[str, int]:
    counts: dict[str, int] = {}
    for token in text.split():
        word = token.strip(".,!?;:()\\"'").lower()
        if len(word) >= min_len:
            counts[word] = counts.get(word, 0) + 1
    return counts


def sentence_split(text: str) -> list[str]:
    """Naive splitter: '.', '!', '?' followed by whitespace/end."""
    pieces = re.split(r"(?<=[.!?])\\s+", text.strip())
    return [p for p in pieces if p]
''',
        "offbyone": '''"""Small text-processing helpers."""
from __future__ import annotations
import re


def slugify(text: str) -> str:
    """Lowercase; collapse non-alphanumerics into single hyphens."""
    lowered = text.lower().strip()
    cleaned = re.sub(r"[^a-z0-9]+", "-", lowered)
    return re.sub(r"-{2,}", "-", cleaned).strip("-")


def word_frequency(text: str, min_len: int = 3) -> dict[str, int]:
    counts: dict[str, int] = {}
    for token in text.split()[:-1]:
        word = token.strip(".,!?;:()\\"'").lower()
        if len(word) >= min_len:
            counts[word] = counts.get(word, 0) + 1
    return counts


def sentence_split(text: str) -> list[str]:
    """Naive splitter: '.', '!', '?' followed by whitespace/end."""
    pieces = re.split(r"(?<=[.!?])\\s+", text.strip())
    return [p for p in pieces if p]
''',
        "wrong_compare": '''"""Small text-processing helpers."""
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
        word = token.strip(".,!?;:()\\"'").lower()
        if len(word) > min_len:
            counts[word] = counts.get(word, 0) + 1
    return counts


def sentence_split(text: str) -> list[str]:
    """Naive splitter: '.', '!', '?' followed by whitespace/end."""
    pieces = re.split(r"(?<=[.!?])\\s+", text.strip())
    return [p for p in pieces if p]
''',
        "wrong_regex": '''"""Small text-processing helpers."""
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
        word = token.strip(".,!?;:()\\"'").lower()
        if len(word) >= min_len:
            counts[word] = counts.get(word, 0) + 1
    return counts


def sentence_split(text: str) -> list[str]:
    """Naive splitter (buggy): only '!' and '?' split."""
    pieces = re.split(r"(?<=[!?])\\s+", text.strip())
    return [p for p in pieces if p]
''',
    },
    "tests": '''check("slug lower", mod.slugify("Hello World") == "hello-world")
check("slug punct", mod.slugify("Hi, there!!  Plan B") == "hi-there-plan-b")
freq = mod.word_frequency("the cat and the dog, the mouse")
check("freq counts", freq["the"] == 3)
check("freq min_len includes 3", freq["and"] == 1)
check("freq counts last word",
      mod.word_frequency("alpha beta gamma")["gamma"] == 1)
f2 = mod.word_frequency("a to the bee")
check("freq excludes short", "to" not in f2)
check("splits on period", len(mod.sentence_split("Hello. World.")) == 2)
check("splits mixed", len(mod.sentence_split("One. Two! Three?")) == 3)
check("no trailing empty", mod.sentence_split("Bye!") == ["Bye!"])
''',
}

_BUG_FIX_SCHEDULING = {
    "slug": "scheduling",
    "blurb": "shift-scheduling logic",
    "work": "main.py (overlap detection, merging, hours)",
    "difficulty": "medium (a ~40-line module with a seeded logic bug)",
    "good": '''"""Shift scheduling helpers for a small roster tool."""
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
    ordered = sorted(shifts, key=lambda s: (s.start, s.end))
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
''',
    "buggy": {
        "wrong_compare": '''"""Shift scheduling helpers for a small roster tool."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Shift:
    worker: str
    start: int
    end: int


def is_overlap(a: Shift, b: Shift) -> bool:
    return a.start <= b.end and b.start <= a.end


def merge_shifts(shifts: list[Shift]) -> list[Shift]:
    """Merge overlapping shifts, sorted by start; input is not mutated."""
    if not shifts:
        return []
    ordered = sorted(shifts, key=lambda s: (s.start, s.end))
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
''',
        "wrong_key": '''"""Shift scheduling helpers for a small roster tool."""
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
''',
        "wrong_accum": '''"""Shift scheduling helpers for a small roster tool."""
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
    ordered = sorted(shifts, key=lambda s: (s.start, s.end))
    merged = [ordered[0]]
    for s in ordered[1:]:
        last = merged[-1]
        if s.start <= last.end:
            last.end = max(last.end, s.end)
        else:
            merged.append(s)
    return merged


def total_hours(shifts: list[Shift]) -> int:
    return sum(s.start for s in shifts)
''',
        "offbyone": '''"""Shift scheduling helpers for a small roster tool."""
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
    ordered = sorted(shifts, key=lambda s: (s.start, s.end))
    merged = [ordered[0]]
    for s in ordered[1:-1]:
        last = merged[-1]
        if s.start <= last.end:
            last.end = max(last.end, s.end)
        else:
            merged.append(s)
    return merged


def total_hours(shifts: list[Shift]) -> int:
    return sum(s.end - s.start for s in shifts)
''',
    },
    "tests": '''a = mod.Shift("a", 0, 2)
b = mod.Shift("b", 2, 4)
check("no touch overlap", not mod.is_overlap(a, b))
check("real overlap", mod.is_overlap(a, mod.Shift("x", 1, 3)))
m = mod.merge_shifts([mod.Shift("a", 4, 6), mod.Shift("a", 0, 2), mod.Shift("a", 1, 3)])
check("merge pairs", len(m) == 2)
check("merge keeps last", m[-1].end == 6)
m2 = mod.merge_shifts([mod.Shift("a", 0, 2), mod.Shift("a", 2, 4)])
check("merge touching", len(m2) == 1)
check("total hours",
      mod.total_hours([mod.Shift("a", 0, 2), mod.Shift("b", 3, 8)]) == 7)
check("empty total", mod.total_hours([]) == 0)
check("merge does not mutate", (lambda s: (mod.merge_shifts(s), len(s)))([mod.Shift("a", 1, 3), mod.Shift("a", 0, 2)])[1] == 2)
''',
}

# -------------------------------------------------------- implement_function
def _implement_variants() -> list[dict]:
    specs = [
        _IMPLEMENT_MAX_PROFIT, _IMPLEMENT_MERGE_INTERVALS, _IMPLEMENT_KNAPSACK,
        _IMPLEMENT_EDIT_DISTANCE, _IMPLEMENT_FLATTEN_JSON, _IMPLEMENT_LRU,
    ]
    out = []
    for spec in specs:
        stub, good, tests, blurb, name_short = (
            spec["stub"], spec["good"], spec["tests"], spec["blurb"],
            spec["slug"],
        )
        name = f"implement_{name_short}"
        prompt = (
            f"{ROLE}\n\n"
            f"{CONTEXT_RULE.format(files='solution.py')}\n\n"
            f"TASK: Implement the function described in `solution.py` "
            f"({blurb}). Replace the `raise NotImplementedError` body with a "
            f"correct, efficient implementation in `solution.py`. Handle "
            f"edge cases (empty inputs, boundaries). Do not change the "
            f"signature. The project's hidden unit tests will be run against "
            f"your file.\n"
            f"Difficulty: hard (non-trivial algorithm, edge cases).\n"
            f"{OUTPUT_RULE}\n"
            f"Expected: every hidden unit test passes."
        )
        variant = _task_row(
            name, "implement_function", "hard", prompt,
            "file_code_exec", "solution.py\n" + tests, [],
        )
        variant["fixtures"] = [("solution.py", stub)]
        variant["reference"] = {"file": "solution.py", "content": good}
        variant["negative"] = {"file": "solution.py", "content": stub}
        out.append(variant)
    return out


_IMPLEMENT_MAX_PROFIT = {
    "slug": "max_profit",
    "blurb": "maximum profit from one buy and one sell",
    "stub": '''def max_profit(prices: list[float]) -> float:
    """Return the maximum profit achievable by buying once and selling once
    later (sell index must be after buy index). Return 0.0 if impossible.

    Example: max_profit([7, 1, 5, 3, 6, 4]) == 5.0
    """
    raise NotImplementedError
''',
    "good": '''def max_profit(prices: list[float]) -> float:
    if len(prices) < 2:
        return 0.0
    best = 0.0
    min_seen = prices[0]
    for p in prices[1:]:
        best = max(best, p - min_seen)
        min_seen = min(min_seen, p)
    return best
''',
    "tests": '''check("example", mod.max_profit([7, 1, 5, 3, 6, 4]) == 5.0)
check("strictly falling", mod.max_profit([5, 4, 3, 2, 1]) == 0.0)
check("single", mod.max_profit([3]) == 0.0)
check("empty", mod.max_profit([]) == 0.0)
check("later only", mod.max_profit([10, 1, 1, 1]) == 0.0)
check("big jump", mod.max_profit([1, 2, 3, 100, 0, 50]) == 99.0)
check("float", mod.max_profit([1.5, 2.5, 1.0]) == 1.0)
''',
}

_IMPLEMENT_MERGE_INTERVALS = {
    "slug": "merge_intervals",
    "blurb": "merge overlapping intervals",
    "stub": '''def merge_intervals(intervals: list[list[int]]) -> list[list[int]]:
    """Merge all overlapping intervals and return them sorted by start.
    Touching intervals ([1,2] and [2,3]) merge as well.

    Example: merge_intervals([[1, 3], [2, 6], [8, 10], [15, 18]])
             == [[1, 6], [8, 10], [15, 18]]
    """
    raise NotImplementedError
''',
    "good": '''def merge_intervals(intervals: list[list[int]]) -> list[list[int]]:
    if not intervals:
        return []
    out = []
    for s, e in sorted(intervals):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out
''',
    "tests": '''check("example", mod.merge_intervals([[1, 3], [2, 6], [8, 10], [15, 18]])
      == [[1, 6], [8, 10], [15, 18]])
check("touching merge", mod.merge_intervals([[1, 2], [2, 3]]) == [[1, 3]])
check("empty", mod.merge_intervals([]) == [])
check("single", mod.merge_intervals([[5, 7]]) == [[5, 7]])
check("unsorted input", mod.merge_intervals([[10, 12], [1, 2], [2, 4]])
      == [[1, 4], [10, 12]])
check("no overlap", mod.merge_intervals([[1, 2], [3, 4]]) == [[1, 2], [3, 4]])
check("contained", mod.merge_intervals([[1, 10], [2, 3]]) == [[1, 10]])
''',
}

_IMPLEMENT_KNAPSACK = {
    "slug": "knapsack",
    "blurb": "0/1 knapsack dynamic programming",
    "stub": '''def knapsack(capacity: int, weights: list[int], values: list[int]) -> int:
    """Return the maximum total value achievable with total weight
    <= capacity. Each item may be used at most once (0/1 knapsack).

    Example: knapsack(10, [5, 4, 6, 3], [10, 40, 30, 50]) == 90
    """
    raise NotImplementedError
''',
    "good": '''def knapsack(capacity: int, weights: list[int], values: list[int]) -> int:
    n = len(weights)
    dp = [0] * (capacity + 1)
    for i in range(n):
        for w in range(capacity, weights[i] - 1, -1):
            dp[w] = max(dp[w], dp[w - weights[i]] + values[i])
    return dp[capacity]
''',
    "tests": '''check("example", mod.knapsack(10, [5, 4, 6, 3], [10, 40, 30, 50]) == 90)
check("zero capacity", mod.knapsack(0, [1, 2], [5, 9]) == 0)
check("heavy items", mod.knapsack(3, [4, 5], [100, 200]) == 0)
check("exact fit", mod.knapsack(6, [2, 3, 4], [3, 4, 5]) == 8)
check("no reuse", mod.knapsack(5, [2, 2, 2], [1, 1, 1]) == 2)
check("empty", mod.knapsack(5, [], []) == 0)
check("choose heavy value", mod.knapsack(8, [8, 1, 1, 1], [20, 2, 2, 2]) == 20)
''',
}

_IMPLEMENT_EDIT_DISTANCE = {
    "slug": "edit_distance",
    "blurb": "Levenshtein edit distance",
    "stub": '''def edit_distance(a: str, b: str) -> int:
    """Return the Levenshtein distance between a and b: the minimum number
    of single-character insertions, deletions or substitutions needed to
    turn a into b.

    Example: edit_distance("kitten", "sitting") == 3
    """
    raise NotImplementedError
''',
    "good": '''def edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + (ca != cb))
        prev = cur
    return prev[len(b)]
''',
    "tests": '''check("example", mod.edit_distance("kitten", "sitting") == 3)
check("identical", mod.edit_distance("abc", "abc") == 0)
check("empty vs", mod.edit_distance("", "xyz") == 3)
check("vs empty", mod.edit_distance("abc", "") == 3)
check("one char", mod.edit_distance("a", "b") == 1)
check("insertion", mod.edit_distance("abc", "abxc") == 1)
check("long", mod.edit_distance("abcdef", "azced") == 3)
''',
}

_IMPLEMENT_FLATTEN_JSON = {
    "slug": "flatten_json",
    "blurb": "flatten nested JSON objects",
    "stub": '''def flatten_json(data: dict, prefix: str = "") -> dict:
    """Flatten nested dicts into dotted keys. Lists and other values are
    kept as-is (recursion stops at non-dict values).

    Example: flatten_json({"a": {"b": 1}, "c": [1, 2]})
             == {"a.b": 1, "c": [1, 2]}
    """
    raise NotImplementedError
''',
    "good": '''def flatten_json(data: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in data.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(flatten_json(v, key))
        else:
            out[key] = v
    return out
''',
    "tests": '''check("example", mod.flatten_json({"a": {"b": 1}, "c": [1, 2]})
      == {"a.b": 1, "c": [1, 2]})
check("deep", mod.flatten_json({"x": {"y": {"z": 2}}}) == {"x.y.z": 2})
check("mixed", mod.flatten_json({"a": 1, "b": {"c": 2}}) == {"a": 1, "b.c": 2})
check("empty", mod.flatten_json({}) == {})
check("list kept", mod.flatten_json({"l": [{"n": 1}]}) == {"l": [{"n": 1}]})
check("empty inner", mod.flatten_json({"a": {}, "b": 1}) == {"b": 1})
''',
}

_IMPLEMENT_LRU = {
    "slug": "lru_cache",
    "blurb": "LRU cache with capacity",
    "stub": '''from collections import OrderedDict


class LRUCache:
    """Least-recently-used cache with fixed capacity (>= 1).

    get(key) returns the stored value or -1. Every get/put refreshes
    recency. put(key, value) inserts/updates and evicts the
    least-recently-used entry when at capacity.
    """

    def __init__(self, capacity: int):
        raise NotImplementedError

    def get(self, key: int) -> int:
        raise NotImplementedError

    def put(self, key: int, value: int) -> None:
        raise NotImplementedError
''',
    "good": '''from collections import OrderedDict


class LRUCache:
    def __init__(self, capacity: int):
        self.cap = capacity
        self.store = OrderedDict()

    def get(self, key: int) -> int:
        if key not in self.store:
            return -1
        self.store.move_to_end(key)
        return self.store[key]

    def put(self, key: int, value: int) -> None:
        if key in self.store:
            self.store.move_to_end(key)
        self.store[key] = value
        if len(self.store) > self.cap:
            self.store.popitem(last=False)
''',
    "tests": '''c = mod.LRUCache(2)
c.put(1, 10); c.put(2, 20)
check("hit", c.get(1) == 10)
c.put(3, 30)
check("evicts lru", c.get(2) == -1)
check("keeps recent", c.get(1) == 10 and c.get(3) == 30)
c.put(4, 40)
check("evicts second lru", c.get(1) == -1)
check("refresh on put", c.get(3) == 30 and c.get(4) == 40)
check("miss on empty", mod.LRUCache(1).get(9) == -1)
_upd = mod.LRUCache(2)
_upd.put(1, 1)
_upd.put(1, 2)
check("update preserves", _upd.get(1) == 2)
''',
}

# ---------------------------------------------------------------- refactor
def _refactor_variants() -> list[dict]:
    specs = [_REFACTOR_INVOICE, _REFACTOR_CONFIG, _REFACTOR_LOGS]
    out = []
    for spec in specs:
        name = f"refactor_{spec['slug']}"
        prompt = (
            f"{ROLE}\n\n"
            f"{CONTEXT_RULE.format(files='ugly.py')}\n\n"
            f"TASK: Refactor `ugly.py` ({spec['blurb']}). The code works but "
            f"violates basic engineering standards: it relies on module-level "
            f"global state and duplicate logic. Rewrite it as clean, "
            f"well-structured code: split the logic into small focused "
            f"functions with docstrings, use module-level constants instead "
            f"of mutable globals, and remove all duplicated blocks. The "
            f"public API (function names and signatures) must stay identical "
            f"and the behavior must be preserved exactly.\n"
            f"Difficulty: medium-hard (structural refactor, behavior must "
            f"not change).\n"
            f"{OUTPUT_RULE}\n"
            f"Expected: all hidden unit tests pass AND no global-state "
            f"anti-patterns remain."
        )
        variant = _task_row(
            name, "refactor", "medium", prompt,
            "file_code_exec", "ugly.py\n" + spec["tests"], spec["banned"],
        )
        variant["fixtures"] = [("ugly.py", spec["ugly"])]
        variant["reference"] = {"file": "ugly.py", "content": spec["good"]}
        variant["negative"] = {"file": "ugly.py", "content": spec["ugly"]}
        out.append(variant)
    return out


_REFACTOR_INVOICE = {
    "slug": "invoice",
    "blurb": "invoice formatter with global rate and duplicated block",
    "banned": ["global "],
    "ugly": '''global _rate
_rate = 0.075


def process(rows):
    total = 0.0
    lines = []
    for r in rows:
        p = r.split(",")
        q = int(p[2])
        price = float(p[3])
        total += q * price
        lines.append(p[1] + " x" + str(q) + " @ " + str(price))
    tax = round(total * _rate, 2)
    lines.append("TAX " + str(tax))
    lines.append("TOTAL " + str(round(total + tax, 2)))
    dup = []
    for l in lines:
        dup.append(l.upper() if l.startswith("T") else l)
    return dup
''',
    "good": '''TAX_RATE = 0.075


def _parse_row(row: str) -> tuple[str, int, float]:
    parts = row.split(",")
    return parts[1], int(parts[2]), float(parts[3])


def _line_for(name: str, qty: int, price: float) -> str:
    return f"{name} x{qty} @ {price}"


def _tax_for(total: float) -> float:
    return round(total * TAX_RATE, 2)


def _upper_summary(lines: list[str]) -> list[str]:
    return [l.upper() if l.startswith("T") else l for l in lines]


def process(rows):
    """Format invoice rows: item lines, tax, grand total."""
    lines = []
    total = 0.0
    for row in rows:
        name, qty, price = _parse_row(row)
        total += qty * price
        lines.append(_line_for(name, qty, price))
    tax = _tax_for(total)
    lines.append(f"TAX {tax}")
    lines.append(f"TOTAL {round(total + tax, 2)}")
    return _upper_summary(lines)
''',
    "tests": '''rows = ["s1,Widget,2,1.50", "s2,Gadget,1,3.00"]
out = mod.process(rows)
check("item lines", out[0] == "Widget x2 @ 1.5" and out[1] == "Gadget x1 @ 3.0")
check("tax", out[2] == "TAX 0.45")
check("total", out[3] == "TOTAL 6.45")
check("empty", mod.process([]) == ["TAX 0.0", "TOTAL 0.0"])
check("single row", mod.process(["s1,Widget,4,1.25"])[1] == "TAX 0.38")
''',
}

_REFACTOR_CONFIG = {
    "slug": "config",
    "blurb": "config validator with global error buffer and duplicated checks",
    "banned": ["global ", "_errs"],
    "ugly": '''global _errs
_errs = []


def validate(cfg):
    _errs[:] = []
    if "name" not in cfg:
        _errs.append("missing name")
    if not isinstance(cfg.get("port"), int):
        _errs.append("port must be int")
    if "hosts" in cfg and len(cfg["hosts"]) == 0:
        _errs.append("hosts empty")
    if "name" not in cfg:
        _errs.append("missing name")
    if not isinstance(cfg.get("port"), int):
        _errs.append("port must be int")
    if "hosts" in cfg and len(cfg["hosts"]) == 0:
        _errs.append("hosts empty")
    return list(_errs)
''',
    "good": '''def _missing_name(cfg: dict) -> list[str]:
    return ["missing name"] if "name" not in cfg else []


def _bad_port(cfg: dict) -> list[str]:
    return ["port must be int"] if not isinstance(cfg.get("port"), int) else []


def _empty_hosts(cfg: dict) -> list[str]:
    return ["hosts empty"] if "hosts" in cfg and len(cfg["hosts"]) == 0 else []


def validate(cfg: dict) -> list[str]:
    """Return the list of configuration problems (may be empty)."""
    problems = []
    for check in (_missing_name, _bad_port, _empty_hosts):
        problems.extend(check(cfg))
    return problems
''',
    "tests": '''check("valid cfg",
      mod.validate({"name": "api", "port": 8080, "hosts": ["a"]}) == [])
check("missing name once", mod.validate({"port": 8080}).count("missing name") == 1)
check("port type", mod.validate({"name": "x", "port": "8080"})
      == ["port must be int"])
check("empty hosts once",
      mod.validate({"name": "x", "port": 1, "hosts": []}).count("hosts empty") == 1)
check("all problems", sorted(mod.validate({}))
      == sorted(["missing name", "port must be int"]))
check("no globals leak", mod.validate({"name": "a", "port": 1}) == [])
''',
}

_REFACTOR_LOGS = {
    "slug": "logs",
    "blurb": "log summarizer with global counters and duplicated counting",
    "banned": ["global ", "_counts"],
    "ugly": '''global _counts
_counts = {}


def summarize(lines):
    _counts.clear()
    for line in lines:
        lvl = line.split(" ")[1]
        _counts[lvl] = _counts.get(lvl, 0) + 1
    top = []
    for k in sorted(_counts):
        top.append(k + ":" + str(_counts[k]))
    return top
''',
    "good": '''def _level_of(line: str) -> str:
    return line.split(" ")[1]


def _count_levels(lines: list[str]) -> dict:
    counts = {}
    for line in lines:
        level = _level_of(line)
        counts[level] = counts.get(level, 0) + 1
    return counts


def summarize(lines: list[str]) -> list[str]:
    """Return sorted 'LEVEL:count' strings for each level present."""
    counts = _count_levels(lines)
    return [f"{k}:{counts[k]}" for k in sorted(counts)]
''',
    "tests": '''logs = ["2024-01-01 ERROR boot", "2024-01-01 WARN slow",
         "2024-01-01 ERROR retry", "2024-01-01 INFO ok"]
check("counts levels", mod.summarize(logs) == ["ERROR:2", "INFO:1", "WARN:1"])
check("empty", mod.summarize([]) == [])
check("single", mod.summarize(["2024-01-01 ERROR x"]) == ["ERROR:1"])
''',
}

# ------------------------------------------------------------ fastapi_setup
def _fastapi_variants() -> list[dict]:
    specs = [_FASTAPI_TODOS, _FASTAPI_CATALOG, _FASTAPI_ORDERS]
    out = []
    for spec in specs:
        name = f"fastapi_{spec['slug']}"
        files = ", ".join(rel for rel, _ in spec["fixtures"])
        prompt = (
            f"{ROLE}\n\n"
            f"{CONTEXT_RULE.format(files=files)}\n\n"
            f"TASK: Build a small FastAPI application from the spec in "
            f"`README.md` ({spec['blurb']}). Create `app.py` (and "
            f"`requirements.txt` if needed) in the workdir. Follow the "
            f"spec exactly: endpoints, status codes, error handling "
            f"(404 for missing resources), and request/response shapes.\n"
            f"Difficulty: medium (multi-endpoint API with error handling).\n"
            f"{OUTPUT_RULE}\n"
            f"Expected: every endpoint from the spec exists with the "
            f"documented behavior."
        )
        expected = "\n".join(
            f"{rel}|{needle}" for rel, needle in spec["needles"]
        )
        variant = _task_row(
            name, "fastapi_setup", "medium", prompt,
            "file_contains", expected, [],
        )
        variant["fixtures"] = list(spec["fixtures"])
        variant["reference"] = [
            {"file": "app.py", "content": spec["reference_app"]},
            {"file": "requirements.txt",
             "content": spec.get("reference_requirements", "fastapi\nuvicorn\n")},
        ]
        variant["negative"] = [
            {"file": "app.py", "content": "# placeholder\npass\n"},
        ]
        out.append(variant)
    return out


_FASTAPI_TODOS = {
    "slug": "todos",
    "blurb": "todo list API",
    "fixtures": [
        ("README.md", """# Todo API

Build a FastAPI app in `app.py` for a small todo list. Data is stored
in-memory (a Python list); the id counter starts at 1.

Endpoints:
- GET /todos          -> list of all todos
- GET /todos/{id}     -> one todo; 404 JSON {"detail": "not found"} if missing
- POST /todos         -> body {"task": "..."}; creates todo with {"id": 2, "task": "...", "done": false}, returns 201
- DELETE /todos/{id}  -> deletes the todo; 204 on success, 404 if missing
"""),
        ("data.json", '[{"id": 1, "task": "buy milk", "done": false}]'),
    ],
    "needles": [
        ("app.py", "from fastapi import FastAPI, HTTPException"),
        ("app.py", "app = FastAPI("),
        ("app.py", '@app.get("/todos"'),
        ("app.py", '@app.get("/todos/{todo_id}"'),
        ("app.py", '@app.post("/todos"'),
        ("app.py", '@app.delete("/todos/{todo_id}"'),
        ("app.py", "raise HTTPException(status_code=404"),
        ("requirements.txt", "fastapi"),
    ],
    "reference_app": '''from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

todos = [{"id": 1, "task": "buy milk", "done": False}]
next_id = 2


class TodoIn(BaseModel):
    task: str


@app.get("/todos")
def list_todos():
    return todos


@app.get("/todos/{todo_id}")
def get_todo(todo_id: int):
    for t in todos:
        if t["id"] == todo_id:
            return t
    raise HTTPException(status_code=404, detail="not found")


@app.post("/todos", status_code=201)
def create_todo(body: TodoIn):
    global next_id
    todo = {"id": next_id, "task": body.task, "done": False}
    next_id += 1
    todos.append(todo)
    return todo


@app.delete("/todos/{todo_id}", status_code=204)
def delete_todo(todo_id: int):
    for t in todos:
        if t["id"] == todo_id:
            todos.remove(t)
            return
    raise HTTPException(status_code=404, detail="not found")
''',
}

_FASTAPI_CATALOG = {
    "slug": "catalog",
    "blurb": "item catalog API with search",
    "fixtures": [
        ("README.md", """# Catalog API

Build a FastAPI app in `app.py` for a small item catalog. Load `data.json`
at startup into an in-memory list.

Endpoints:
- GET /items           -> all items
- GET /items/{id}      -> one item; 404 if missing
- GET /items/search    -> query param `q` (str, required): case-insensitive
                          substring match on item name; returns matching items
"""),
        ("data.json", '[{"id": 1, "name": "Laptop", "price": 1200}, {"id": 2, "name": "Mouse", "price": 25}]'),
    ],
    "needles": [
        ("app.py", "from fastapi import FastAPI, HTTPException"),
        ("app.py", "app = FastAPI("),
        ("app.py", '@app.get("/items"'),
        ("app.py", '@app.get("/items/{item_id}"'),
        ("app.py", '@app.get("/items/search"'),
        ("app.py", "raise HTTPException(status_code=404"),
        ("app.py", "data.json"),
        ("requirements.txt", "fastapi"),
    ],
    "reference_app": '''import json
from fastapi import FastAPI, HTTPException

app = FastAPI()

with open("data.json", encoding="utf-8") as fh:
    items = json.load(fh)


@app.get("/items")
def list_items():
    return items


@app.get("/items/{item_id}")
def get_item(item_id: int):
    for it in items:
        if it["id"] == item_id:
            return it
    raise HTTPException(status_code=404, detail="not found")


@app.get("/items/search")
def search_items(q: str):
    needle = q.lower()
    return [it for it in items if needle in it["name"].lower()]
''',
}

_FASTAPI_ORDERS = {
    "slug": "orders",
    "blurb": "order API that computes totals",
    "fixtures": [
        ("README.md", """# Orders API

Build a FastAPI app in `app.py` for a small ordering system. Load `data.json`
(products with `price`) at startup.

Endpoints:
- GET /orders                 -> all orders
- GET /orders/{id}            -> one order; 404 if missing
- POST /orders                -> body {"items": [{"product_id": 1, "qty": 2}]};
                                 returns 201 with the order including
                                 "total" (sum of price * qty, rounded to 2),
                                 and a generated "id" (max id + 1)
"""),
        ("data.json", '[{"id": 1, "name": "Widget", "price": 5.0}, {"id": 2, "name": "Gadget", "price": 3.0}]'),
    ],
    "needles": [
        ("app.py", "from fastapi import FastAPI, HTTPException"),
        ("app.py", "app = FastAPI("),
        ("app.py", '@app.get("/orders"'),
        ("app.py", '@app.get("/orders/{order_id}"'),
        ("app.py", '@app.post("/orders"'),
        ("app.py", "raise HTTPException(status_code=404"),
        ("app.py", '"total"'),
        ("requirements.txt", "fastapi"),
    ],
    "reference_app": '''import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

with open("data.json", encoding="utf-8") as fh:
    products = json.load(fh)

orders = []


class OrderItem(BaseModel):
    product_id: int
    qty: int


class OrderIn(BaseModel):
    items: list[OrderItem]


@app.get("/orders")
def list_orders():
    return orders


@app.get("/orders/{order_id}")
def get_order(order_id: int):
    for o in orders:
        if o["id"] == order_id:
            return o
    raise HTTPException(status_code=404, detail="not found")


@app.post("/orders", status_code=201)
def create_order(body: OrderIn):
    prices = {p["id"]: p["price"] for p in products}
    total = 0.0
    for item in body.items:
        total += prices.get(item.product_id, 0.0) * item.qty
    order = {
        "id": max([o["id"] for o in orders], default=0) + 1,
        "items": [i.model_dump() for i in body.items],
        "total": round(total, 2),
    }
    orders.append(order)
    return order
''',
}

# --------------------------------------------------------- docker_configure
def _docker_variants() -> list[dict]:
    specs = [_DOCKER_FLASK, _DOCKER_STREAMLIT, _DOCKER_WORKER]
    out = []
    for spec in specs:
        name = f"docker_{spec['slug']}"
        files = ", ".join(rel for rel, _ in spec["fixtures"])
        prompt = (
            f"{ROLE}\n\n"
            f"{CONTEXT_RULE.format(files=files)}\n\n"
            f"TASK: Containerize the project in the workdir "
            f"({spec['blurb']}). Create a `Dockerfile` and a "
            f"`docker-compose.yml` that follow current best practices "
            f"(slim base image pinned to a major version, workdir set, "
            f"dependencies installed from `requirements.txt`, non-default "
            f"exposed port, healthcheck where reasonable). The compose "
            f"service must build from the local Dockerfile, publish the "
            f"app port, and mount the app as a volume.\n"
            f"Difficulty: medium (containerization conventions).\n"
            f"{OUTPUT_RULE}\n"
            f"Expected: a valid Dockerfile and compose file that would "
            f"build and run the app."
        )
        expected = "\n".join(
            f"{rel}|{needle}" for rel, needle in spec["needles"]
        )
        variant = _task_row(
            name, "docker_configure", "medium", prompt,
            "file_contains", expected, [],
        )
        variant["fixtures"] = list(spec["fixtures"])
        variant["reference"] = [
            {"file": "Dockerfile", "content": spec["reference_dockerfile"]},
            {"file": "docker-compose.yml",
             "content": spec["reference_compose"]},
        ]
        variant["negative"] = [
            {"file": "Dockerfile", "content": "# TODO\n"},
            {"file": "docker-compose.yml", "content": "# TODO\n"},
        ]
        out.append(variant)
    return out


_DOCKER_FLASK = {
    "slug": "flask_api",
    "blurb": "a Flask REST API",
    "fixtures": [
        ("app.py", '''from flask import Flask, jsonify

app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})
'''),
        ("requirements.txt", "flask==3.0.3\n"),
        ("README.md", "Flask REST API. Runs on port 5000.\n"),
    ],
    "needles": [
        ("Dockerfile", "FROM python:3.11-slim"),
        ("Dockerfile", "WORKDIR /app"),
        ("Dockerfile", "COPY"),
        ("Dockerfile", "RUN pip install"),
        ("Dockerfile", "CMD"),
        ("Dockerfile", "EXPOSE 5000"),
        ("docker-compose.yml", "services:"),
        ("docker-compose.yml", "build:"),
        ("docker-compose.yml", "ports:"),
        ("docker-compose.yml", "5000"),
    ],
    "reference_dockerfile": '''FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "app.py"]
''',
    "reference_compose": '''services:
  api:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - .:/app
''',
}

_DOCKER_STREAMLIT = {
    "slug": "streamlit_dashboard",
    "blurb": "a Streamlit dashboard",
    "fixtures": [
        ("app.py", '''import streamlit as st

st.title("Dashboard")
'''),
        ("requirements.txt", "streamlit==1.36.0\n"),
        ("README.md", "Streamlit dashboard. Runs on port 8501.\n"),
    ],
    "needles": [
        ("Dockerfile", "FROM python:3.11-slim"),
        ("Dockerfile", "WORKDIR /app"),
        ("Dockerfile", "COPY"),
        ("Dockerfile", "RUN pip install"),
        ("Dockerfile", "CMD"),
        ("Dockerfile", "EXPOSE 8501"),
        ("docker-compose.yml", "services:"),
        ("docker-compose.yml", "build:"),
        ("docker-compose.yml", "ports:"),
        ("docker-compose.yml", "8501"),
    ],
    "reference_dockerfile": '''FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
''',
    "reference_compose": '''services:
  dashboard:
    build: .
    ports:
      - "8501:8501"
    volumes:
      - .:/app
''',
}

_DOCKER_WORKER = {
    "slug": "cron_worker",
    "blurb": "a scheduled worker script",
    "fixtures": [
        ("worker.py", '''import time


def run():
    print("worker tick")


if __name__ == "__main__":
    while True:
        run()
        time.sleep(60)
'''),
        ("requirements.txt", "requests==2.32.3\n"),
        ("README.md", "Background worker. No HTTP port needed.\n"),
    ],
    "needles": [
        ("Dockerfile", "FROM python:3.11-slim"),
        ("Dockerfile", "WORKDIR /app"),
        ("Dockerfile", "COPY"),
        ("Dockerfile", "RUN pip install"),
        ("Dockerfile", "CMD"),
        ("docker-compose.yml", "services:"),
        ("docker-compose.yml", "build:"),
        ("docker-compose.yml", "restart:"),
    ],
    "reference_dockerfile": '''FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "worker.py"]
''',
    "reference_compose": '''services:
  worker:
    build: .
    restart: unless-stopped
    volumes:
      - .:/app
''',
}

# -------------------------------------------------------------- write_tests
def _write_tests_variants() -> list[dict]:
    specs = [
        _TESTS_BANKING, _TESTS_CART, _TESTS_URLPARSER,
        _TESTS_STATS, _TESTS_TEMPERATURE,
    ]
    out = []
    for spec in specs:
        name = f"write_tests_{spec['slug']}"
        prompt = (
            f"{ROLE}\n\n"
            f"{CONTEXT_RULE.format(files='good.py, buggy.py')}\n\n"
            f"TASK: The project contains two versions of the same module: "
            f"`good.py` (correct) and `buggy.py` (one deliberately seeded "
            f"defect). Your job is to write a unit test suite that would "
            f"catch the defect ({spec['blurb']}). Requirements:\n"
            f"1. Every test must pass against the correct module.\n"
            f"2. At least one test must FAIL against the buggy module.\n"
            f"3. Use `import mod` to reach the module under test and write "
            f"plain functions named `test_*` containing `assert` statements "
            f"(no test framework needed). Cover edge cases, not just happy "
            f"paths.\n"
            f"Difficulty: hard (test design; the bug is subtle).\n"
            f"{OUTPUT_RULE}\n"
            f"Your test code must be the ONLY code block in your reply."
        )
        variant = _task_row(
            name, "write_tests", "hard", prompt,
            "test_suite", f"GOOD_MODULE=good.py\nBUGGY_MODULE=buggy.py", [],
        )
        variant["fixtures"] = [("good.py", spec["good"]),
                               ("buggy.py", spec["buggy"])]
        reference_tests = f"```python\n{spec['author_tests']}\n```"
        variant["reference"] = {"response": reference_tests}
        variant["negative"] = {
            "response": "```python\ndef test_nothing():\n    pass\n```",
        }
        out.append(variant)
    return out


_TESTS_BANKING = {
    "slug": "banking",
    "blurb": "transfer does not debit the sender",
    "good": '''class Account:
    def __init__(self, owner: str, balance: float = 0.0):
        self.owner = owner
        self.balance = balance

    def deposit(self, amount: float) -> float:
        if amount <= 0:
            raise ValueError("amount must be positive")
        self.balance += amount
        return self.balance

    def withdraw(self, amount: float) -> float:
        if amount <= 0:
            raise ValueError("amount must be positive")
        if amount > self.balance:
            raise ValueError("insufficient funds")
        self.balance -= amount
        return self.balance

    def transfer(self, other: "Account", amount: float) -> float:
        self.withdraw(amount)
        other.balance += amount
        return self.balance
''',
    "buggy": '''class Account:
    def __init__(self, owner: str, balance: float = 0.0):
        self.owner = owner
        self.balance = balance

    def deposit(self, amount: float) -> float:
        if amount <= 0:
            raise ValueError("amount must be positive")
        self.balance += amount
        return self.balance

    def withdraw(self, amount: float) -> float:
        if amount <= 0:
            raise ValueError("amount must be positive")
        if amount > self.balance:
            raise ValueError("insufficient funds")
        self.balance -= amount
        return self.balance

    def transfer(self, other: "Account", amount: float) -> float:
        other.balance += amount
        return self.balance
''',
    "author_tests": '''def test_deposit():
    a = mod.Account("alice")
    assert a.deposit(100) == 100.0


def test_withdraw():
    a = mod.Account("alice", 50)
    assert a.withdraw(20) == 30.0


def test_withdraw_insufficient():
    a = mod.Account("alice", 10)
    try:
        a.withdraw(20)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_deposit_negative():
    a = mod.Account("alice")
    try:
        a.deposit(-5)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_transfer_deducts_sender():
    a = mod.Account("alice", 100)
    b = mod.Account("bob", 0)
    a.transfer(b, 40)
    assert a.balance == 60.0


def test_transfer_credits_receiver():
    a = mod.Account("alice", 100)
    b = mod.Account("bob", 0)
    a.transfer(b, 40)
    assert b.balance == 40.0
''',
}

_TESTS_CART = {
    "slug": "cart",
    "blurb": "promo codes apply a fixed amount instead of a percentage",
    "good": '''class Cart:
    def __init__(self):
        self.items = []

    def add(self, sku: str, price: float, qty: int = 1) -> None:
        self.items.append((sku, price, qty))

    def total(self) -> float:
        raw = sum(p * q for _, p, q in self.items)
        return round(raw, 2)

    def apply_promo(self, code: str) -> float:
        base = self.total()
        if code == "SAVE10":
            return round(base * 0.9, 2)
        if code == "SAVE50":
            return round(base * 0.5, 2)
        return base
''',
    "buggy": '''class Cart:
    def __init__(self):
        self.items = []

    def add(self, sku: str, price: float, qty: int = 1) -> None:
        self.items.append((sku, price, qty))

    def total(self) -> float:
        raw = sum(p * q for _, p, q in self.items)
        return round(raw, 2)

    def apply_promo(self, code: str) -> float:
        base = self.total()
        if code == "SAVE10":
            return round(base - 10.0, 2)
        if code == "SAVE50":
            return round(base - 50.0, 2)
        return base
''',
    "author_tests": '''def test_total():
    c = mod.Cart()
    c.add("a", 1.50, 2)
    c.add("b", 2.00, 1)
    assert c.total() == 5.0


def test_total_rounding():
    c = mod.Cart()
    c.add("a", 0.1, 3)
    assert c.total() == 0.3


def test_promo_save10_percent():
    c = mod.Cart()
    c.add("x", 100.0, 1)
    assert c.apply_promo("SAVE10") == 90.0


def test_promo_save10_small_order():
    c = mod.Cart()
    c.add("x", 50.0, 1)
    assert c.apply_promo("SAVE10") == 45.0


def test_promo_save50_percent():
    c = mod.Cart()
    c.add("x", 200.0, 1)
    assert c.apply_promo("SAVE50") == 100.0


def test_promo_unknown():
    c = mod.Cart()
    c.add("x", 10.0, 1)
    assert c.apply_promo("NOPE") == 10.0


def test_empty_cart():
    assert mod.Cart().total() == 0.0
''',
}

_TESTS_URLPARSER = {
    "slug": "urlparser",
    "blurb": "query values are returned as single strings instead of lists",
    "good": '''from urllib.parse import parse_qs


def parse_query(url: str) -> dict:
    """Return decoded query parameters; values may repeat (as lists)."""
    if "?" not in url:
        return {}
    _, _, qs = url.partition("?")
    return {k: v for k, v in parse_qs(qs).items()}


def path_of(url: str) -> str:
    path = url.partition("?")[0]
    return path.split("://", 1)[-1].partition("/")[2].rstrip("/") or "/"
''',
    "buggy": '''from urllib.parse import parse_qs


def parse_query(url: str) -> dict:
    """Return decoded query parameters; values may repeat (as lists)."""
    if "?" not in url:
        return {}
    _, _, qs = url.partition("?")
    return {k: v[0] for k, v in parse_qs(qs).items()}


def path_of(url: str) -> str:
    path = url.partition("?")[0]
    return path.split("://", 1)[-1].partition("/")[2].rstrip("/") or "/"
''',
    "author_tests": '''def test_basic_params():
    assert mod.parse_query("https://x.io/a?q=cat&page=2") == {
        "q": ["cat"], "page": ["2"]}


def test_repeated_key():
    assert mod.parse_query("?tag=a&tag=b") == {"tag": ["a", "b"]}


def test_no_query():
    assert mod.parse_query("https://x.io/a") == {}


def test_url_decode():
    assert mod.parse_query("?q=hello%20world") == {"q": ["hello world"]}


def test_path():
    assert mod.path_of("https://x.io/a/b/") == "a/b"


def test_root_path():
    assert mod.path_of("https://x.io?q=1") == "/"
''',
}

_TESTS_STATS = {
    "slug": "stats",
    "blurb": "median mutates its input list",
    "good": '''def median(values):
    """Median without mutating the input list."""
    if not values:
        raise ValueError("empty list")
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def mean(values):
    if not values:
        raise ValueError("empty list")
    return sum(values) / len(values)
''',
    "buggy": '''def median(values):
    """Median without mutating the input list."""
    if not values:
        raise ValueError("empty list")
    values.sort()
    n = len(values)
    mid = n // 2
    if n % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2


def mean(values):
    if not values:
        raise ValueError("empty list")
    return sum(values) / len(values)
''',
    "author_tests": '''def test_median_odd():
    assert mod.median([3, 1, 2]) == 2.0


def test_median_even():
    assert mod.median([4, 1, 2, 3]) == 2.5


def test_median_does_not_mutate():
    data = [5, 3, 1, 4, 2]
    mod.median(data)
    assert data == [5, 3, 1, 4, 2]


def test_median_empty():
    try:
        mod.median([])
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_mean():
    assert mod.mean([1, 2, 3, 4]) == 2.5


def test_mean_empty():
    try:
        mod.mean([])
    except ValueError:
        return
    raise AssertionError("expected ValueError")
''',
}

_TESTS_TEMPERATURE = {
    "slug": "temperature",
    "blurb": "average truncates instead of rounding",
    "good": '''class Thermometer:
    def __init__(self):
        self.readings = []

    def record(self, celsius: float) -> None:
        self.readings.append(celsius)

    def min_max(self):
        if not self.readings:
            raise ValueError("no readings")
        return min(self.readings), max(self.readings)

    def average(self):
        if not self.readings:
            raise ValueError("no readings")
        return round(sum(self.readings) / len(self.readings), 2)
''',
    "buggy": '''class Thermometer:
    def __init__(self):
        self.readings = []

    def record(self, celsius: float) -> None:
        self.readings.append(celsius)

    def min_max(self):
        if not self.readings:
            raise ValueError("no readings")
        return min(self.readings), max(self.readings)

    def average(self):
        if not self.readings:
            raise ValueError("no readings")
        return int(sum(self.readings) / len(self.readings))
''',
    "author_tests": '''def test_record():
    t = mod.Thermometer()
    t.record(20.0)
    assert t.readings == [20.0]


def test_min_max():
    t = mod.Thermometer()
    for v in [3.5, -2.0, 9.0]:
        t.record(v)
    assert t.min_max() == (-2.0, 9.0)


def test_average_rounds():
    t = mod.Thermometer()
    t.record(19.5)
    t.record(20.5)
    assert t.average() == 20.0


def test_average_fraction():
    t = mod.Thermometer()
    t.record(1.0)
    t.record(2.0)
    assert t.average() == 1.5


def test_empty():
    try:
        mod.Thermometer().min_max()
    except ValueError:
        return
    raise AssertionError("expected ValueError")
''',
}

# ---------------------------------------------------------------- cli_tool
def _cli_variants() -> list[dict]:
    specs = [
        _CLI_SALES, _CLI_FILTER, _CLI_JSON_PRETTY, _CLI_WORD_FREQ,
    ]
    out = []
    for spec in specs:
        name = f"cli_{spec['slug']}"
        files = ", ".join(rel for rel, _ in spec["fixtures"])
        prompt = (
            f"{ROLE}\n\n"
            f"{CONTEXT_RULE.format(files=files)}\n\n"
            f"TASK: Build a small command-line tool from the spec in "
            f"`README.md` ({spec['blurb']}). Create `cli.py` in the workdir "
            f"using argparse (flags exactly as documented in the spec). "
            f"The tool must read the data file from the current directory "
            f"and print output to stdout in the exact format shown in the "
            f"spec.\n"
            f"Difficulty: complex (CLI contract must match exactly).\n"
            f"{OUTPUT_RULE}\n"
            f"Expected: the grader runs your `cli.py` with documented "
            f"arguments and compares stdout line-by-line."
        )
        variant = _task_row(
            name, "cli_tool", "complex", prompt,
            "command_check", "", [],
        )
        variant["fixtures"] = list(spec["fixtures"])
        variant["reference"] = {"file": "cli.py", "content": spec["reference"]}
        variant["cmd"] = spec["cmd"]
        variant["negative"] = {
            "file": "cli.py", "content": 'import sys\nprint("TODO")\n',
        }
        out.append(variant)
    return out


_CLI_SALES = {
    "slug": "sales",
    "blurb": "sales summary CLI",
    "cmd": "python cli.py --input orders.csv --top 2",
    "fixtures": [
        ("README.md", """# Sales summary CLI

`cli.py --input FILE [--city CITY] [--top N]`

- `--input` (required): path to a CSV with columns date,item,price,qty,city
- `--city` (optional): restrict to rows with that city
- `--top N` (optional, default 5): print the N items with the highest total
  revenue (price * qty), one per line: `ITEM:REVENUE` (revenue rounded to 2
  decimals), sorted descending by revenue, ties broken by item name.

Example output for a small file with top 2:
Widget:10.50
Gadget:4.00
"""),
        ("orders.csv", "date,item,price,qty,city\n2024-01-01,Widget,1.50,2,Berlin\n2024-01-02,Gadget,2.00,2,Berlin\n2024-01-02,Widget,1.50,5,Munich\n2024-01-03,Doohickey,0.50,1,Berlin\n"),
    ],
    "reference": '''import argparse
import csv


def revenue(rows):
    by_item = {}
    for row in rows:
        item = row["item"]
        rev = float(row["price"]) * int(row["qty"])
        by_item[item] = by_item.get(item, 0.0) + rev
    return by_item


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--city", default=None)
    parser.add_argument("--top", type=int, default=5)
    args = parser.parse_args()

    with open(args.input, encoding="utf-8", newline="") as fh:
        rows = [r for r in csv.DictReader(fh)]

    if args.city:
        rows = [r for r in rows if r["city"] == args.city]

    by_item = revenue(rows)
    ranked = sorted(by_item.items(), key=lambda kv: (-kv[1], kv[0]))
    for item, rev in ranked[: args.top]:
        print(f"{item}:{rev:.2f}")


if __name__ == "__main__":
    main()
''',
}

_CLI_FILTER = {
    "slug": "filter",
    "blurb": "CSV filter CLI",
    "cmd": "python cli.py --input people.csv --min-age 30 --job engineer",
    "fixtures": [
        ("README.md", """# CSV filter CLI

`cli.py --input FILE [--min-age N] [--job JOB]`

- `--input` (required): path to a CSV with columns name,age,city,job
- `--min-age N` (optional): only people with age >= N
- `--job JOB` (optional): only people whose job equals JOB (case-insensitive)

Print matching names sorted alphabetically, one per line.
"""),
        ("people.csv", "name,age,city,job\nAlice,34,Berlin,engineer\nBob,29,Hamburg,engineer\nCarol,41,Munich,designer\nDave,30,Berlin,engineer\n"),
    ],
    "reference": '''import argparse
import csv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--min-age", type=int, default=0)
    parser.add_argument("--job", default=None)
    args = parser.parse_args()

    with open(args.input, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    matches = []
    for row in rows:
        if int(row["age"]) < args.min_age:
            continue
        if args.job and row["job"].lower() != args.job.lower():
            continue
        matches.append(row["name"])

    for name in sorted(matches):
        print(name)


if __name__ == "__main__":
    main()
''',
}

_CLI_JSON_PRETTY = {
    "slug": "json_pretty",
    "blurb": "pretty-printing JSON CLI",
    "cmd": "python cli.py --input config.json --sort",
    "fixtures": [
        ("README.md", """# JSON pretty-printer CLI

`cli.py --input FILE [--sort]`

- `--input` (required): path to a JSON file
- `--sort` (optional): sort keys alphabetically at every nesting level

Print the JSON indented with 2 spaces to stdout. Without `--sort` the
original key order is preserved.
"""),
        ("config.json", '{"z": {"b": 2, "a": 1}, "y": [1, 2], "a": true}'),
    ],
    "reference": '''import argparse
import json


def sort_keys(value):
    if isinstance(value, dict):
        return {k: sort_keys(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [sort_keys(v) for v in value]
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--sort", action="store_true")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as fh:
        data = json.load(fh)

    if args.sort:
        data = sort_keys(data)

    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
''',
}

_CLI_WORD_FREQ = {
    "slug": "word_freq",
    "blurb": "word frequency CLI",
    "cmd": "python cli.py --input text.txt --top 3",
    "fixtures": [
        ("README.md", """# Word frequency CLI

`cli.py --input FILE [--top N]`

- `--input` (required): path to a plain-text file
- `--top N` (optional, default 10): print the N most frequent words

Words are lowercased and stripped of surrounding punctuation
(.,!?;:"'()). Print `word:count` per line, most frequent first, ties
broken alphabetically.
"""),
        ("text.txt", "The cat and the dog. The cat ran, the dog ran!\n"),
    ],
    "reference": '''import argparse
import re


def tokens(text):
    return [t.strip(".,!?;:\\"'()").lower()
            for t in text.split() if t.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as fh:
        words = tokens(fh.read())

    counts = {}
    for w in words:
        counts[w] = counts.get(w, 0) + 1

    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    for word, count in ranked[: args.top]:
        print(f"{word}:{count}")


if __name__ == "__main__":
    main()
''',
}

# ---------------------------------------------------------------- registry
FAMILIES = {
    "bug_fix": _bug_fix_variants,
    "implement_function": _implement_variants,
    "refactor": _refactor_variants,
    "fastapi_setup": _fastapi_variants,
    "docker_configure": _docker_variants,
    "write_tests": _write_tests_variants,
    "cli_tool": _cli_variants,
}

DIFFICULTY_BY_FAMILY = {
    "bug_fix": "medium",
    "implement_function": "hard",
    "refactor": "medium",
    "fastapi_setup": "medium",
    "docker_configure": "medium",
    "write_tests": "hard",
    "cli_tool": "complex",
}


# ---------------------------------------------------------------- validation
def _build_expected_for_cli(variant: dict) -> tuple[str, bool]:
    """Run the reference cli.py and capture stdout lines.

    Returns (expected text, ok). The expected text has the form:
        CMD:python cli.py --input orders.csv --top 2
        <line1>
        <line2>
    """
    cmd = variant["cmd"]
    parts = cmd.split()
    if parts and parts[0].lower() == "python":
        import sys
        parts[0] = sys.executable
    with tempfile.TemporaryDirectory(prefix="hermesbench_gen_") as tmp:
        workdir = Path(tmp)
        for rel, content in variant["fixtures"]:
            target = workdir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        (workdir / "cli.py").write_text(
            variant["reference"]["content"], encoding="utf-8")
        try:
            proc = subprocess.run(
                parts, cwd=str(workdir), capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=60,
            )
        except (subprocess.TimeoutExpired, OSError):
            return "", False
        lines = [l.strip() for l in proc.stdout.splitlines() if l.strip()]
        if proc.returncode != 0 or not lines:
            return "", False
        expected = "CMD:" + variant["cmd"] + "\n" + "\n".join(lines)
        return expected, True


def _grade_variant(variant: dict, workdir: Path, response: str) -> float | None:
    task = Task(
        task_id=variant["name"],
        category=f"se_{DIFFICULTY_BY_FAMILY[variant['family']]}",
        prompt=variant["prompt"],
        check_type=variant["check_type"],
        expected=variant["expected"],
        threshold=variant["threshold"],
        rubric=variant["rubric"],
        workdir=workdir,
        banned=variant["banned"],
    )
    score, _ = grade(task, response, judge=None)
    return score


def _validate_variant(variant: dict) -> tuple[bool, str]:
    """Score the reference (must be >= 1.0) and the negative (must be < 1.0)
    using the real graders, in a throwaway workdir."""
    if (variant["check_type"] == "command_check"
            and not variant["expected"].startswith("CMD:")):
        expected, ok = _build_expected_for_cli(variant)
        if not ok:
            return False, "reference CLI produced no usable output"
        variant["expected"] = expected
    with tempfile.TemporaryDirectory(prefix="hermesbench_gen_") as tmp:
        workdir = Path(tmp)
        for rel, content in variant["fixtures"]:
            target = workdir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        def apply(artifact) -> str:
            if artifact is None:
                return ""
            if isinstance(artifact, list):
                response = ""
                for item in artifact:
                    response += apply(item)
                return response
            if "file" in artifact:
                target = workdir / artifact["file"]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(artifact["content"], encoding="utf-8")
                return ""
            return artifact.get("response", "")

        ref_score = _grade_variant(variant, workdir, apply(variant["reference"]))
        if ref_score is None or ref_score < 1.0:
            return False, f"reference scored {ref_score} (want 1.0)"

        if variant.get("negative"):
            neg_score = _grade_variant(variant, workdir, apply(variant["negative"]))
            if neg_score is None or neg_score >= 1.0:
                return False, f"negative scored {neg_score} (want < 1.0)"

        return True, "ok"


# ---------------------------------------------------------------- generation
def _all_variants(families: list[str]) -> list[dict]:
    out = []
    for family in families:
        if family not in FAMILIES:
            raise SystemExit(f"unknown family: {family} (use --list)")
        for variant in FAMILIES[family]():
            variant.setdefault("family", family)
            out.append(variant)
    return out


def generate(rounds: int, per_family: int, seed: int, families: list[str],
             out_dir: Path) -> None:
    variants = _all_variants(families)
    by_family: dict[str, list[dict]] = {}
    for v in variants:
        by_family.setdefault(v["family"], []).append(v)

    rng = random.Random(seed)
    seen: set[str] = set()
    manifest = {
        "generator_version": GEN_VERSION,
        "seed": seed,
        "families": families,
        "per_family_per_round": per_family,
        "rounds": int(rounds),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "task_sets": {},
        "rejected": [],
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    for round_no in range(1, rounds + 1):
        selected: list[dict] = []
        for family, pool in by_family.items():
            fresh = [v for v in pool if v["name"] not in seen]
            rng.shuffle(fresh)
            pick = fresh[:per_family]
            reused = []
            if len(pick) < per_family:
                rest = [v for v in pool if v not in pick]
                rng.shuffle(rest)
                extra = rest[: per_family - len(pick)]
                pick.extend(extra)
                reused = [v["name"] for v in extra]
            for v in pick:
                seen.add(v["name"])
                v["_reused"] = v["name"] in reused
            selected.extend(pick)

        rows, entries = [], []
        for variant in selected:
            ok, msg = _validate_variant(variant)
            if not ok:
                manifest["rejected"].append({
                    "variant": variant["name"], "round": round_no,
                    "reason": msg,
                })
                print(f"  REJECTED {variant['name']}: {msg}")
                continue
            entries.append({
                "task_id": variant["name"],
                "family": variant["family"],
                "reused": variant["_reused"],
                "validated": True,
                "check_type": variant["check_type"],
                "difficulty": DIFFICULTY_BY_FAMILY[variant["family"]],
            })
            rows.append({
                "task_id": variant["name"],
                "family": variant["family"],
                "category": f"se_{DIFFICULTY_BY_FAMILY[variant['family']]}",
                "prompt": variant["prompt"],
                "check_type": variant["check_type"],
                "expected": variant["expected"],
                "threshold": variant["threshold"],
                "rubric": variant["rubric"],
                "banned": ";".join(variant["banned"]),
            })

        csv_path = out_dir / f"round_{round_no}_se.csv"
        csv_path.write_text(
            _csv_dump(rows), encoding="utf-8")
        for variant in selected:
            if variant["name"] not in [e["task_id"] for e in entries]:
                continue
            task_dir = out_dir / "tasks" / variant["name"] / "work"
            task_dir.mkdir(parents=True, exist_ok=True)
            for rel, content in variant["fixtures"]:
                target = task_dir / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            pristine_dir = task_dir.parent / "pristine"
            if pristine_dir.exists():
                shutil.rmtree(pristine_dir)
            shutil.copytree(task_dir, pristine_dir)

        manifest["task_sets"][f"round_{round_no}"] = entries
        print(f"round {round_no}: {len(entries)} tasks -> {csv_path.name}")

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"manifest -> {manifest_path}")


def _csv_dump(rows: list[dict]) -> str:
    if not rows:
        return ""
    header = ["task_id", "family", "category", "prompt", "check_type",
              "expected", "threshold", "rubric", "banned"]
    lines = [",".join(header)]
    for row in rows:
        cells = []
        for key in header:
            val = row[key]
            if isinstance(val, float):
                val = f"{val:.2f}"
            val = str(val).replace("\r", " ")
            if any(c in val for c in (",", '"', "\n")):
                val = '"' + val.replace('"', '""') + '"'
            cells.append(val)
        lines.append(",".join(cells))
    return "\n".join(lines) + "\n"


# -------------------------------------------------------------------- CLI
def main() -> int:
    parser = argparse.ArgumentParser(
        description="HermesBench SE task-variant generator")
    parser.add_argument("--list", action="store_true",
                        help="list families and variant counts")
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--per-family", type=int, default=2,
                        help="variants per family per round")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--families", default=None,
                        help="comma-separated family names (default: all)")
    parser.add_argument("--out", default=str(Path(__file__).parent / "variants"))
    args = parser.parse_args()

    if args.list:
        for family, builder in FAMILIES.items():
            n = len(builder())
            print(f"  {family:<20} {n:>2} variants  "
                  f"(difficulty: {DIFFICULTY_BY_FAMILY[family]})")
        return 0

    families = [f.strip() for f in (args.families or "").split(",") if f.strip()]
    families = families or sorted(FAMILIES)
    generate(args.rounds, args.per_family, args.seed, families,
             Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
