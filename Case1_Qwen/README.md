# Case1_Qwen — Case 1: The naive baseline (replica of `other_run`)

**What this case is**: the ORIGINAL experiment. A plain task loop with NO
learning channel: no post-task hook, no skills seeding, no tiers. Hermes runs
in one-shot (`-z`) mode, so nothing ever persisted — that is why it was a
null result (65.3% vs 66.1%). See `docs/CASE2_PLAN.md` §2 for the diagnosis.

**Harness provenance**: exact code state of commit `9760ca1` (2026-08-05),
the era `other_run` was executed in. Only one change was added on top: the
shared-tasks-dir loader patch (below).

**Dataset**: 8 coding tasks per round, 5 rounds (bug_fix / fastapi / cli_tool /
docker_configure families), rebuilt 1:1 from `runs/other_run/metrics.csv`
(the per-round boards and order the run actually used). Task prompts come from
the era `round_*_se.csv` sources (kept in `datasets/variants/`).

## Files
- `benchmark/`, `analysis/` — the Case-1-era harness
- `config/config.yaml` — era config (`task_limit: 8`, no hook, no seeding)
- `datasets/variants/round_1.csv .. round_5.csv` — the 8-task boards
- `datasets/variants/round_1_se.csv .. round_5_se.csv` — era source files (14 tasks each)
- `tests_selftest.py` — era offline self-tests
- `run_rounds.ps1` — run all 5 rounds

## How to run
1. Start LM Studio, load `qwen/qwen3.5-9b`, server on 127.0.0.1:1234.
2. From this folder: `powershell -File run_rounds.ps1`
   (or run the commands inside manually — Round 1 no `--resume`, 2–5 with it)
3. Results: `runs\case1_run\metrics.csv` (expect 80 rows) + `results.xlsx`.

After the run: `.venv` metrics: `analysis\metrics_engine.py --csv runs\case1_run\metrics.csv`

## Shared files (do NOT copy into this folder)
- Task workspaces: `..\..\datasets\variants\tasks\` (single shared pool; the
  loader resolves it via `project.tasks_dir`)
- `.venv` at the repo root
- Historical results stay in `..\..\runs\` untouched.

## Caveats
- Faithful to the era: no auto orphan-process sweep existed then. If a rerun
  hits Windows "Access denied" restore errors, close stray agent processes
  (LM Studio's server is fine — only `uvicorn`/`hermes.exe`-style leftovers).
- Never run two rounds/concurrent instances at once.