"""Load benchmark tasks from datasets/*.csv.

Dataset schema (CSV, utf-8):

    task_id,family,category,prompt,check_type,expected,threshold,rubric,banned

`family` (optional, defaults to task_id) groups variant tasks across rounds
so recovery-rate analysis can match them. `banned` (optional) is a
semicolon-separated list of substrings that must NOT appear in the model's
code (checked for code_exec / file_code_exec / test_suite).

check_type:
    contains        expected = substring that must appear in the response
    regex           expected = regex, searched against the response
    file_exists     expected = glob pattern relative to the task workdir
    file_contains   expected = "glob|substring" lines (partial credit; for a
                    single check: "glob|substring" exactly like before)
    code_exec       expected = test code using check(name, cond); model code is
                    extracted from the response and run with the tests
    file_code_exec  expected = two lines: "FILE" then test code; FILE is loaded
                    as a module (mod.*) before tests run, cwd = workdir
    test_suite      expected = two lines "GOOD_MODULE=..."/"BUGGY_MODULE=...";
                    the model's written tests (code fences) must pass on the
                    good module and fail on the buggy one
    command_check   expected = "CMD:<shell command>" then expected stdout lines
                    (run in workdir; partial credit per matching line)
    llm_judge       expected unused; rubric = grading rubric for the judge

Multiple check types may be combined with "+" (score = mean), e.g.
"file_contains+file_code_exec".
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

VALID_CHECK_TYPES = {
    "contains",
    "regex",
    "file_exists",
    "file_contains",
    "code_exec",
    "file_code_exec",
    "test_suite",
    "command_check",
    "llm_judge",
}


@dataclass
class Task:
    task_id: str
    category: str
    prompt: str
    check_type: str
    expected: str
    threshold: float
    rubric: str
    workdir: Path
    family: str = ""
    banned: list[str] = field(default_factory=list)
    tier: str = ""


def _validate_check_type(task_id: str, check_type: str) -> str:
    parts = [p for p in check_type.split("+") if p.strip()]
    if not parts:
        raise ValueError(f"task {task_id}: empty check_type")
    for part in parts:
        if part not in VALID_CHECK_TYPES:
            raise ValueError(
                f"task {task_id}: unknown check_type {part!r}"
            )
    return "+".join(parts)


def _unescape(text: str) -> str:
    """Decode literal escape sequences written by the task generator's CSV
    dumper (older dumps escaped real newlines as the two characters '\\n'),
    and normalize CRLF line endings (Windows write translation)."""
    return text.replace("\r\n", "\n").replace("\\n", "\n")


def load_tasks(csv_path: Path, limit: int | None = None,
               task_ids: list[str] | None = None,
               categories: list[str] | None = None,
               tasks_dir: Path | None = None) -> list[Task]:
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Dataset not found: {csv_path}")
    tasks: list[Task] = []
    with open(csv_path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            task_id = (row.get("task_id") or "").strip()
            if not task_id:
                continue
            if task_ids and task_id not in task_ids:
                continue
            category = (row.get("category") or "").strip()
            if categories and category not in categories:
                continue
            check_type = _validate_check_type(
                task_id, (row.get("check_type") or "").strip().lower()
            )
            try:
                threshold = float(row.get("threshold") or 0.7)
            except ValueError:
                print(f"[task_loader] WARNING: task {task_id}: unparsable "
                      f"threshold {row.get('threshold')!r}; using 0.7")
                threshold = 0.7
            tasks_base = Path(tasks_dir) if tasks_dir \
                else csv_path.parent / "tasks"
            workdir = tasks_base / task_id / "work"
            banned_raw = (row.get("banned") or "").strip()
            banned = [b.strip() for b in banned_raw.split(";") if b.strip()]
            tasks.append(
                Task(
                    task_id=task_id,
                    category=category,
                    prompt=_unescape((row.get("prompt") or "").strip()),
                    check_type=check_type,
                    expected=_unescape((row.get("expected") or "").strip()),
                    threshold=threshold,
                    rubric=_unescape((row.get("rubric") or "").strip()),
                    workdir=workdir,
                    family=(row.get("family") or "").strip() or task_id,
                    banned=banned,
                    tier=(row.get("tier") or "").strip(),
                )
            )
    if not tasks:
        raise ValueError(f"No tasks loaded from {csv_path}")
    if limit:
        tasks = tasks[:limit]
    return tasks


def load_dataset_from_config(config: dict) -> list[Task]:
    dataset = Path(config["project"].get("dataset", "datasets/benchmark.csv"))
    if not dataset.is_absolute():
        dataset = Path(__file__).resolve().parent.parent / dataset
    tasks_dir = config.get("project", {}).get("tasks_dir")
    if tasks_dir:
        td = Path(tasks_dir)
        if not td.is_absolute():
            td = Path(__file__).resolve().parent.parent / td
        tasks_dir = td
    return load_tasks(dataset, tasks_dir=tasks_dir)
