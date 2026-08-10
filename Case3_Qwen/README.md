# Case3_Qwen — Case 3A: The quality-gated loop (replica of `case3_run`)

**What this case is**: the strict-notebook experiment. Same hook, but it now
fires ONLY when the task scored 1.0 AND the target files were really edited
(diff gate); the reflection prompt is adversarial (discards hacks); failing
skills are pruned; and a mandatory coding contract is seeded into BOTH arms.
Case 3B was scrapped — this folder is 3A only. Original result: NO
(R5 ΔPass −10%, p = 1.0). See `docs/CASE3_PLAN.md`.

**Harness provenance**: exact code state of commit `736ce15` (2026-08-08,
HEAD of the Case-3A era), the last committed 3A state. All Case-3B code was
never committed and is excluded. Plus the shared-tasks-dir loader patch.

**Dataset**: `datasets/variants/tier_round_1.csv .. 5.csv` — the **10-task** boards
(3 Repeat + 5 Variant + 2 New), extracted from that same commit.

## Files
- `benchmark/`, `analysis/` — the 3A harness (incl. `infrastructure_recovery.py`)
- `config/config.yaml` — era config with the `case3:` block
- `datasets/tier_round_*.csv` — 10-task boards
- `skills/benchmark_coding_contract.md` — the contract skill (sections §1–3)
- `tests_selftest.py` — era offline self-tests
- `docs/CASE3_PLAN.md` — plan, gates, pruner, metrics, verdict rule
- `run_rounds.ps1` — run all 5 rounds

## How to run
1. Start LM Studio, load `qwen/qwen3.5-9b`, server on 127.0.0.1:1234.
2. From this folder: `powershell -File run_rounds.ps1`
3. Results: `runs\case3_run\metrics.csv` (expect 100 rows) + `results.xlsx`.

After the run: `analysis\metrics_engine.py --csv runs\case3_run\metrics.csv`
→ look for the `CASE3 VERDICT: YES/NO` console line (§8.2: ΔPass ≥ +5% AND
Fisher p < 0.05 on round 5).

## Shared files (do NOT copy into this folder)
- Task workspaces: `..\..\datasets\variants\tasks\` (shared pool via
  `project.tasks_dir`)
- `.venv` at the repo root; historical results stay in `..\..\runs\`.

## Caveats
- Pilot check after round 1: treatment hook `ok/error` on perfect-score rows,
  `skipped(no-diff)` / `skipped(score<1.0)` elsewhere; control `hook_*` empty.
- Never run two rounds/concurrent instances at once.