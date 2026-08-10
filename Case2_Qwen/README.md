# Case2_Qwen — Case 2: The unfiltered learning loop (replica of `tier_run`)

**What this case is**: the first real learning loop. After every successfully
finished treatment task, a "learning hook" session distills lessons and
persists them via Hermes's native tools (`memories/MEMORY.md`, `skills/`).
Both arms get the 542 bundled skills seeded; only the treatment arm can add
to them. 3-tier curriculum: Repeat (memorization), Variant (transfer), New
(specificity control). Result of the original run: flat (65.3% vs 66.1%),
40/40 tier verdicts unsupported. See `docs/CASE2_PLAN.md`.

**Harness provenance**: exact code state of commit `3a34e64` (2026-08-07,
last commit before the Case-3 changes), including the Windows access-denied
auto-recovery fixes (`kill_agent_orphans`, reserved-name cleanup). Plus the
shared-tasks-dir loader patch.

**Dataset**: `datasets/variants/tier_round_1.csv .. 5.csv` — the **6-task** boards
(2 Repeat + 3 Variant + 1 New), extracted from that same commit (the boards
CASE2_PLAN.md §4 describes). Case 3 later overwrote these filenames at the
repo root with 10-task boards — this folder keeps the original Case-2
content, so the two cases can no longer collide.

## Files
- `benchmark/`, `analysis/` — the Case-2-era harness
- `config/config.yaml` — era config (`learning_hook` + `seed_skills`, limit 6)
- `datasets/tier_round_*.csv` — 6-task boards
- `tests_selftest.py` — era offline self-tests
- `docs/CASE2_PLAN.md` — plan, boards, hook policy, fix brief, verdicts
- `run_rounds.ps1` — run all 5 rounds

## How to run
1. Start LM Studio, load `qwen/qwen3.5-9b`, server on 127.0.0.1:1234.
2. From this folder: `powershell -File run_rounds.ps1`
3. Results: `runs\case2_run\metrics.csv` (expect 60 rows) + `results.xlsx`.

After the run: `analysis\metrics_engine.py --csv runs\case2_run\metrics.csv`

## Shared files (do NOT copy into this folder)
- Task workspaces: `..\..\datasets\variants\tasks\` (shared pool via
  `project.tasks_dir`)
- `.venv` at the repo root; historical results stay in `..\..\runs\`.

## Caveats
- Pilot check after round 1: hook rows must exist on treatment (Repeat/Variant)
  and be `skipped(tier=New)` on New; control `hook_*` must stay empty.
- Never run two rounds/concurrent instances at once.