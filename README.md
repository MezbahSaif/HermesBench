# HermesBench

Benchmark framework for a university research project: does **Hermes Agent**
(Nous Research) measurably **self-improve** over repeated benchmark execution?

Design: **5 rounds × 14 tasks × 2 arms**. Each task is a fresh one-shot
`hermes -z` session on a frozen model (LM Studio). The treatment arm's Hermes
home persists across rounds (skills/memory accumulate); the control arm's home
is wiped and re-seeded every round. Trend analysis (Mann-Kendall, Welch)
decides whether the learning loop causes the improvement.

## Commands (PowerShell, from the project root)

```powershell
# environment check (creates venv + installs requirements on first run)
powershell -ExecutionPolicy Bypass -File .\verify_setup.ps1

# environment-only check, no agent executions
.\.venv\Scripts\python benchmark\run_benchmark.py --dataset datasets\variants\round_1_se.csv --dry-run

# the experiment, one round at a time (~2 h each)
.\.venv\Scripts\python benchmark\run_benchmark.py --dataset datasets\variants\round_1_se.csv --round 1 --arm both --run-id thesis_run
.\.venv\Scripts\python benchmark\run_benchmark.py --dataset datasets\variants\round_1_se.csv --round 2 --arm both --run-id thesis_run --resume
# ... rounds 3-5 identical except --round N, always with --resume

# crash recovery: rerun the same round's command with --resume
# stray agents after a crash:
taskkill /F /IM hermes.exe

# results + full report package (xlsx + plots) after round 5
.\.venv\Scripts\python analysis\metrics_engine.py --csv runs\thesis_run\metrics.csv
# dashboard
.\.venv\Scripts\streamlit run ui\app.py

# offline self-tests (validates loaders, graders, stats — no model needed)
.\.venv\Scripts\python tests_selftest.py

# regenerate dataset variants (only when changing the generator)
.\.venv\Scripts\python datasets\generate_tasks.py --rounds 5 --per-family 2 --seed 42
# regenerate the task-overview doc
.\.venv\Scripts\python make_tasks_overview.py
```

## Rules — never break

- Always the **same** `--dataset datasets\variants\round_1_se.csv` and
  `--run-id thesis_run`; add `--resume` after the first chunk.
- Never delete `runs\thesis_run\` between rounds.
- The v1 default dataset (`datasets/benchmark.csv`) is **not** the experiment —
  always pass `--dataset`. It's the original 16-task smoke dataset; most of its
  workdirs hold no fixtures (only `.gitkeep`), so results are meaningless, not
  thesis data.
- LM Studio must be running (model loaded, server on port 1234) before any real
  run. One model, one machine for the whole run (thesis validity).
- Never commit `runs/`, `logs/`, `.venv/`, `metrics/` (gitignored). `homes/`
  under a run dir contains machine-specific config/API keys — never share.

## Known gotchas

- `*_log_events` metrics (tool calls, errors, retries, reflections) are
  **always 0**: Hermes calls `logging.disable(logging.CRITICAL)` during `-z`
  one-shot runs, so its agent.log has no activity lines. Treat as unavailable;
  `api_calls` (from the usage JSON) is the reliable signal.
- Grading is fully deterministic (Python checkers, no LLM judge in the SE
  dataset). Score ≥ 0.7 → passed.
- Task workdirs are restored from `pristine/` snapshots before every
  execution — edits never leak between arms or rounds.
- `human_interventions` = tasks that needed manual attention (timeout/crash),
  not human clicks.

## Layout

```
benchmark/       runner, hermes interface, graders, task loader, CLI, config loader
analysis/        statistics (Mann-Kendall, Welch, bootstrap), graphs, metrics engine (xlsx/plots/verdict)
ui/app.py        Streamlit dashboard (viewer + launcher)
datasets/        benchmark.csv (v1, unused for the experiment),
                 variants/round_N_se.csv (the 5 experiment rounds),
                 variants/tasks/<id>/{work,pristine}/ (fixtures)
config/config.yaml   hermes paths (${LOCALAPPDATA} portable), LM Studio, thresholds
tests_selftest.py    offline regression suite (all fix behaviors)
make_tasks_overview.py  regenerates TASKS_OVERVIEW.md from the round CSVs
runs/<run_id>/    metrics.csv (canonical), results.xlsx, plots/, artifacts/, homes/
```

## Read first

- `README.md` — full design, pipeline, metrics, limitations
- `TASKS_OVERVIEW.md` — every task prompt the agent receives (rounds 1-5)
- `config/config.yaml` — paths and thresholds
