# HermesBench — Case 3: Quality-Gated Learning Loop (Plan & Implementation Notes)

Status: **implementation complete, offline validation passed, waiting for
rounds to be run by the operator**

Reference: `G:\Here is the complete.md` (the Case-3 A-to-Z spec, v3.0).

---

## 1. The claim being tested

Case 2 left the loop open but **unfiltered**: the post-task hook persisted
notes from *every* `status == ok` task (even terminal-only hacks that never
touched the target files), bad skills were never removed, and >90% of test
tasks failed on prompt-contract formatting — measured Treatment vs Control
ended flat (65.3% vs 66.1%).

Case 3 tests the claim under **strict quality gates**:

> **A quality-gated, pruned, contract-seeded learning loop makes Hermes
> natively self-improve: the treatment arm reaches 100%-score tasks
> significantly more often than the control arm by the final round.**

Four harness changes enforce this (spec §1.2): target-diff quality gate,
seed meta-skill contract, active skill pruning, coupled curriculum.

## 2. What was built

### 2.1 `skills/benchmark_coding_contract.md` (new — spec §3)

Mandatory baseline seed skill, preloaded into **both** arms before round 1:

- **File Modification Rule** — the FINAL solution MUST be written directly to
  the target source file in `work/`; terminal-only solutions get ZERO.
- **Code Block Formatting** — executable Python must be wrapped in standard
  markdown fences (` ```python `), no conversational summaries in place of code.
- **Module Import Contract** — test suites must use the dynamic handle
  `import mod` (never `from good import Cart` type hardcodes).

Seeded at `skills/benchmark/coding-contract/SKILL.md` inside each arm home by
`HermesInterface._seed_contract_skill()` during `seed_home()` — this runs on
both `seed_home()` and `reset_home()`, so the contract survives the control
arm's per-round wipe.

### 2.2 `benchmark/infrastructure_recovery.py` (new — spec §2/§5)

All Windows recovery routines moved out of `benchmark_runner.py` into this
module and **re-exported by the runner** for back-compat:

| Function | Role |
|---|---|
| `_remove_windows_reserved_files` | deletes `con/nul/aux/…` paths via `\\?\` prefix + `cmd /c del` |
| `_process_table` / `_ancestor_pids` / `_agent_orphans` | locate leftover agent processes (`uvicorn`/`fastapi`/`flask`/`streamlit`/`hermes.exe`) |
| `kill_agent_orphans` | terminate orphaned agent processes |
| `restore_workspace` | restore `pristine/` → `work/` (with retry + orphan sweep) |
| `safe_restore_workspace` | **spec §5.3**: retries the restore up to 3 times with `2**attempt` backoff, owns the restore-abort → skip-task path |
| `snapshot_pristine` | create/precheck `pristine/` snapshot |

The runner uses `safe_restore_workspace` when `case3.enabled`,
`restore_workspace` otherwise.

### 2.3 Target-Diff Quality Gate (spec §4.1)

`verify_workdir_modified(workdir, since=None)` in `hermes_interface.py`:
1. `git status --porcelain` inside the workdir → non-empty = modified = True.
2. Fallback when git is unavailable/empty: file mtime ≥ `since` (runner passes
   the task start time; default window = 1 h). Any file touched after the task
   started counts as evidence.

This is what makes the hook fire *only* on solutions that verifiably edited
target files.

### 2.4 Adversarial (quality-filtered) reflection hook (spec §4.2)

`run_learning_hook(..., adversarial=True)` switches the post-task prompt to
`ADVERSARIAL_HOOK_PROMPT`. The hook now only runs when **all** gates pass:

```
hook_status = skipped(not-ok)      task status != ok
            | skipped(tier=New)    New is the specificity control (§-review)
            | skipped(no-diff)     target files unmodified (gate §4.1)
            | skipped(score<1.0)   score below hook_min_score (default 1.0)
            | ok / error           hook actually ran (quality-filtered prompt)
```

The adversarial prompt's quality filter explicitly instructs the agent to
**DISCARD temporary-script / hardcoded-hack lessons** and reply
`NO_SKILL_PERSISTED` when no generalizable lesson exists — closing the Case 2
"context pollution" leak.

### 2.5 `benchmark/benchmark_runner.py` — wiring

- METRIC_COLUMNS += `workdir_modified`, `pruned_skill_files`; `_STRING_COLUMNS`
  += `workdir_modified`.
- `__init__` reads the new `case3:` block (`case3_enabled`,
  `require_workdir_diff`, `hook_min_score`, `prune_failing_skills`).
- `_run_one` wires the gates above, records `workdir_modified`/hook status per
  row, and fires the active skill pruner (see below).
- `_finalize` emits an **independent** CASE3 verdict log line (spec §8.2)
  computed separately from the xlsx/plots stage, so a plotting hiccup can never
  swallow the faculty verdict.

### 2.6 Active Skill Pruning Engine (spec §4.3)

`prune_failing_skills(home_dir, session_logs)` in `hermes_interface.py`:
after a task with `score < 1.0`, scans the arm's agent log + usage json for
`skill_view`/`skill_manage` invocations, and **deletes every skill file that was
used during the failing task** (`.md` under `home_dir/skills/`), so harmful
procedures cannot accumulate. Never prunes the seeded
`benchmark_coding_contract`. Logs `[PRUNER] …` and records the count in
`pruned_skill_files`.

### 2.7 `config/config.yaml` — new `case3:` block

```yaml
case3:
  enabled: true
  seed_contract_skill: "skills/benchmark_coding_contract.md"
  require_workdir_diff: true
  hook_min_score: 1.0
  adversarial_hook: true
  prune_failing_skills: true
  delta_pass_threshold: 0.05        # spec §8.2
  alpha: 0.05                       # fisher-exact alpha
```

## 3. Dataset curriculum (spec §6)

`datasets/build_case3_dataset.py` recombines the 34 existing task instances
into the Case-3 curriculum — **10 tasks per round, 5 rounds** (not 6):

| Tier | Per round | Instances | What it proves |
|---|---|---|---|
| **Repeat** | 3 | `fastapi_catalog`, `refactor_config`, `write_tests_temperature` — identical every round | Memory write/read works (caching sanity) |
| **Variant** | 5 | bug_fix ×2 lanes, algorithms ×2 lanes, testing ×1 lane; instance changes each round, family stable per lane | Transfer test — skills generalize to unseen instances |
| **New** | 2 | held-out `cli_tool` / `docker_configure` only | Specificity control — must stay flat when learning is specific |

Per-round boards (task[i] = round i):

```
tier_round_1: fastapi_catalog[Repeat] refactor_config[Repeat] write_tests_temperature[Repeat]
              bug_fix_text_wrong_regex bug_fix_finance_offbyone
              implement_knapsack implement_flatten_json write_tests_stats   [Variant]
              cli_filter docker_streamlit_dashboard                          [New]
tier_round_2: fastapi_catalog[Repeat] refactor_config[Repeat] write_tests_temperature[Repeat]
              bug_fix_text_offbyone bug_fix_scheduling_wrong_key
              implement_lru_cache implement_knapsack write_tests_cart        [Variant]
              cli_json_pretty docker_cron_worker                             [New]
tier_round_3: fastapi_catalog[Repeat] refactor_config[Repeat] write_tests_temperature[Repeat]
              bug_fix_scheduling_offbyone bug_fix_text_wrong_compare
              implement_merge_intervals implement_lru_cache write_tests_banking [Variant]
              cli_word_freq docker_flask_api                                 [New]
tier_round_4: fastapi_catalog[Repeat] refactor_config[Repeat] write_tests_temperature[Repeat]
              bug_fix_finance_wrong_compare bug_fix_scheduling_wrong_compare
              implement_edit_distance implement_merge_intervals write_tests_urlparser [Variant]
              cli_sales cli_filter[New]
tier_round_5: fastapi_catalog[Repeat] refactor_config[Repeat] write_tests_temperature[Repeat]
              bug_fix_finance_bad_default bug_fix_finance_wrong_accum
              implement_max_profit implement_edit_distance write_tests_stats  [Variant]
              docker_streamlit_dashboard cli_json_pretty                      [New]
```

**Capacity audit (documented in the generator):** the 34-instance pool cannot
fully supply "5 variant lanes × 5 distinct + 2 new × 5 distinct". Available
distinct counts: bug_fix = 10 (covers 2 lanes), algorithms = 6 (1 full lane),
testing = 4 after `write_tests_temperature` is consumed by Repeat (so its 5th
round reuses round 1), and cli+docker hold only 7 held-out instances (rounds
4–5 reuse two earlier new instances). The generator enforces the hard
invariants (10 rows/round, no intra-round dup, task stays in one tier) and
flags the intentional reuse rows in `REUSE_NOTES` so the numbers are auditable.

## 4. Metrics engine (spec §8)

`analysis/metrics_engine.py` gains the Case-3 functions + a `case3` xlsx sheet:

| Metric | Formula | Function |
|---|---|---|
| **PassRate@1** | `#tasks with score==1.0 / total tasks in round r` (per arm) | `pass_rate_per_round` |
| **ΔPass** | PassRate(treatment,R5) − PassRate(control,R5) | `delta_pass` |
| **VTR** | Pass rate on `tier=="Variant"` rows per arm | `variant_transfer_rate` |
| **Fisher exact** | 2×2 [treatment pass/fail] vs [control pass/fail] final round, two-sided |`fisher_exact_final` |
| **SUR** | Σ skills written on passed tasks / peak skills persisted (clamped [0,100]) | `skill_utility_ratio` |
| **Verdict** | `YES` iff ΔPass ≥ **+5%** AND p < **0.05**; else `NO` | `case3_verdict` |

All outputs go to `runs/case3_run/results.xlsx` in the `case3` sheet (and an
independent console line via `_finalize`), printed exactly per spec §8.2:
`"CASE3 VERDICT: YES (Hermes Agent natively self-improves under quality gates)"`
The existing whole-dataset / tier-verdict / sheet layout is unchanged.

## 5. Execution protocol (operator runs — no live run performed)

LM Studio must be running with `qwen/qwen3.5-9b` loaded. Round 1 establishes
the baseline; rounds 2–5 use `--resume` (keeps Treatment state).

```
# Round 1
.venv\Scripts\python.exe benchmark\run_benchmark.py --dataset datasets\variants\tier_round_1.csv --round 1 --arm both --run-id case3_run --limit 10
# Rounds 2–5
.venv\Scripts\python.exe benchmark\run_benchmark.py --dataset datasets\variants\tier_round_2.csv --round 2 --arm both --run-id case3_run --limit 10 --resume
… (rounds 3, 4, 5 identically)
```

Round = 10 tasks × 2 arms + up to 10 treatment hooks ≈ 30 hermes invocations ;
expect several hours per round on this hardware. `--limit 10` = the full round.

## 6. Verification completed (offline)

- `python -m py_compile` on all edited modules; `benchmark/infrastructure_recovery.py`
  imports cleanly.
- Full `tests_selftest.py` passes (**ALL OFFLINE SELF-TESTS PASSED**), including:
  - resume flow (rows replaced in canonical order, no tail-append);
  - orphan sweep (fake `uvicorn` detected, unrelated processes spared);
  - xlsx sheet set (now **10 sheets**, incl. `case3`);
  - metrics engine writes the `case3` sheet.
- Dry run `run_benchmark.py --dry-run --limit 3` shows both arms seeding the
  contract AND 542 bundled skills, correct dataset load, `workdir=ok`.
- Synthetic 5-round × 10-task × 2-arm metrics (treatment rises to 100%,
  control flat):
  - PassRate R5 1.0 vs 0.0 → ΔPass +100% (gate +5% ✓)
  - Fisher p = 1.1e-05 (< 0.05 ✓)
  - VTR 0.24 vs 0.0; SUR clamped; verdict printed `YES …` ✓
  - `results.xlsx` = metrics/summary/…/recovery/**case3** sheets

## 7. Reminder — how to validate

- **Tests**: `tests_selftest.py` (fast, offline).
- **Dry run**: `benchmark/run_benchmark.py --dry-run --limit 10` with a tier CSV.
- **Live run**: the 5 commands in §5 above, then
  `.venv\Scripts\python.exe analysis\metrics_engine.py --csv runs\case3_run\metrics.csv`.

## 8. Known caveats
- SUR proxy: metrics.csv has no per-skill retrieval column, so SUR uses
  (after_skill_files − before_skill_files) on passed tasks, clamped to [0,100]
  (documented in the function).
- Concurrent sweep also flags harmless app servers on shared machines.
- `Infra` move keeps back-compat exports; `run_benchmark.py` and
  `tests/…` import through `benchmark_runner`.