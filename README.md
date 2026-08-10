# HermesBench — repository layout

Three independent, runnable experiment cases, each in its own folder.
Everything a case needs that differs from the others lives INSIDE its folder.
Anything all cases use identically lives HERE at the root, once.

## The three cases

| Folder | Case | Original run | Harness era (commit) | Rounds |
|---|---|---|---|---|
| `Case1_Qwen/` | 1 — naive baseline (no loop) | `other_run` (80 rows) | `9760ca1` | 8 tasks × 5 |
| `Case2_Qwen/` | 2 — unfiltered learning hook | `tier_run` (60 rows) | `3a34e64` | 6 tasks × 5 |
| `Case3_Qwen/` | 3A — quality-gated loop | `case3_run` (100 rows) | `736ce15` | 10 tasks × 5 |

Each folder has its own `README.md` with exact run commands
(`run_rounds.ps1`), its own config, datasets, tests, and plan docs. Running
one case never touches the others.

## Shared (ONE copy, used by all cases — do not duplicate)

- `datasets/variants/tasks/` — the 34 task instances (pristine + work). The
  case harnesses resolve this via `project.tasks_dir` in each case's config.
- `.venv/` — the Python environment.
- `runs/` — all historical results (untouched; new runs land inside each
  case folder at `CaseN_Qwen/runs/<run-id>/`).
- `docs/RUNS_SUMMARY.md`, `docs/FACULTY_PRESENTATION.md` — shared write-ups.
- `datasets/benchmark.csv`, `datasets/tasks/`, `datasets/generate_tasks.py` —
  legacy base assets/tools.

## Notes

- Case 1 and Case 2 harnesses are faithful reproductions of their era code
  (the originals were overwritten during development; recovered from git).
- The shared-tasks-dir patch is the single, identical change added to all
  three harnesses.
- Version history of everything is preserved in git (checkpoint commit
  `1cb01e5` and earlier era commits).