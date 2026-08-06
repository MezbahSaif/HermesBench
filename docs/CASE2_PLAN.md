# HermesBench — Case 2: Measurable Learning Loop (Plan & Execution Notes)

Status: **setup complete, waiting for rounds to be run by the operator**

---

## 1. The claim being tested

Hermes Agent claims to be a *self-improving* agent: across rounds of use it should
persist knowledge (memory + skills) and measurably get better at similar tasks.

This benchmark answers: **does accumulated memory/skill state causally improve
round-over-round performance?**

## 2. Why the first experiment (other_run) was a null result — the diagnosis

The original 5-round run (`runs/other_run`, 80 rows) found **no improvement** —
claim "not supported". An external review diagnosed *why*: the measurement
harness silently defeated the mechanism it was measuring.

| Symptom | Root cause |
|---|---|
| `memories/` and `skills/` stayed at 0 files | `hermes -z` (one-shot) is engineered to be *stateless*: it loads memory but **never fires a write trigger** (no user confirmation, no auto-memorize, no post-turn persist). |
| `state.db` grew 5.8 → 64.5 MB | That is raw session/transcript storage (writes automatically) — **exhaust, not fuel**. |
| Bench homes had 0 skills | `seed_home()` copied only `config.yaml`/`.env`/`SOUL.md`; the real home's **542 bundled skills** were invisible to the benchmark agents. |
| Round 5 could not beat round 1 | Every improvement pathway (skill writes, memory writes, pre-existing knowledge) was closed before the experiment ran. |

**Conclusion:** the first run is still a valid Case 1 result — "in stateless
one-shot mode, Hermes does not self-improve". But it does **not** test the actual
claim. Case 2 fixes the harness so the learning loop can genuinely engage.

## 3. What was done (harness fixes)

All changes are in the working tree (uncommitted, untouched by the runs below).

### 3.1 `benchmark/hermes_interface.py`
- **`seed_home()` now seeds skills**: copies the real home's `skills/` tree
  (542 files, 6.8 MB) into every bench home (`hermes.seed_skills: true` in
  `config/config.yaml`). Both arms start with Hermes's real knowledge base;
  only the treatment arm can *add* to it during the experiment.
- **New native learning hook** (`run_learning_hook`): after each treatment-arm
  task, runs one more short `hermes -z` session whose prompt instructs the agent
  to distill lessons and persist them with its **native** tools:
  - `memory(action="add", target="memory", content=...)` → `memories/MEMORY.md`
  - `skill_manage` → skills/ folder when the lesson is a reusable procedure
  This is the explicit "memorize trigger" that one-shot mode never auto-fires.
- **Hook excludes the New tier** (`learning_hook.exclude_tiers: [New]`, reviewer
  fix): the hook only runs on Repeat/Variant tasks. New uses cli_tool /
  docker_configure only, but all four cli instances are spread across rounds —
  if the hook practiced them, cli_tool would get ~4 deliberate practice
  sessions and New would stop being a "no deliberate learning" baseline.
  New-tier tasks record `hook_status = "skipped(tier=New)"` so the exclusion
  is auditable in metrics.csv. Any New drift is then noise or state.db/session
  growth, never hook-driven skill accumulation.
- Refactored the subprocess driver into `_invocation()` shared by tasks and hooks.

### 3.2 `benchmark/benchmark_runner.py`
- New metric columns: `hook_status`, `hook_duration_s`, `hook_memory_files_delta`,
  `hook_skill_files_delta`, `hook_memory_bytes_delta` — so the professor can see
  the persistence actually happening (or not), per task.
- New `tier` column in `METRIC_COLUMNS` / `_STRING_COLUMNS` (see §4).
- Hook runs only on the treatment arm (`learning_hook.arm: treatment`); control
  arm stays hook-free (it exists to show what happens with *no* persistence path).
- **Failures never persist lessons** (reviewer fix): the hook only runs when the
  task finished with `status == "ok"`. A failed/timed-out/crashed task sets
  `hook_status = "skipped(not-ok)"` (auditable in the CSV) so wrong lessons
  cannot seed later rounds.

### 3.3 `benchmark/task_loader.py`
- `Task` gains a `tier` field; parsed from the optional `tier` CSV column.

### 3.4 `config/config.yaml`
- `hermes.seed_skills: true`
- `learning_hook: {enabled: true, arm: treatment, exclude_tiers: [New]}`

### 3.5 Live verification (probe, done against the real model)
- Seeded a throwaway home → 542 skills present.
- Ran the hook on a real task → `memories/MEMORY.md` created with 2 native memory
  entries; `memory_files` delta = 2.
- Ran a **fresh** `-z` session in the same home → it quoted the stored memory
  back verbatim. **Write path and read path both confirmed working.**

### 3.6 Windows access-denied auto-recovery (added after the pilot)

The round-1 pilot exposed a class of hard failure: task workdirs could not be
deleted (`PermissionError 13 / "Access is denied"`), which made control-arm
Repeat tasks fail permanently. Two distinct root causes, both now auto-fixed:

| Symptom | Root cause | Fix |
|---|---|---|
| `rmtree` fails forever on a workdir | the agent wrote a file literally named `nul` (misread shell `> nul` redirects). Windows treats `nul`/`con`/`prn`/`aux`/`com1-9`/`lpt1-9` as device names, so normal deletion always fails | `_remove_windows_reserved_files()` strips them before every restore using the `\\?\` extended path prefix |
| `rmtree` fails, retry still fails | a server the agent started (e.g. `uvicorn`) was still alive and holding file handles on the workdir | 1) `_run_kill_on_close()` puts every `hermes` invocation in a Windows Job Object with `KILL_ON_JOB_CLOSE`, so the whole agent process tree dies when the invocation ends (no more orphaned servers); 2) `kill_agent_orphans()` — a startup sweep that force-kills leftover agent processes from crashed/aborted runs (matches `uvicorn`/`fastapi`/`flask`/`streamlit`/`hermes.exe` markers only; never touches LM Studio, the runner, or unrelated python); 3) `restore_workspace()` retries with backoff, then escalates once to orphan-kill + final retry before giving up |

Net effect: the benchmark no longer dies on file locks. Any leftover from a
previous aborted run is cleaned automatically at the start of the next
invocation; any `nul`-style file the agent creates is stripped before the next
restore. All verified by the offline self-tests (reserved-name restore +
orphan sweep, see §7).

## 4. How the dataset was created (three tiers)

`datasets/build_tiered_datasets.py` recombines the 34 existing task instances
(7 families, each with a pristine workdir snapshot) into 5 per-round CSVs:

```
datasets/variants/tier_round_1.csv … tier_round_5.csv
```

Each round = 6 tasks: **2 Repeat + 3 Variant + 1 New** (in that CSV order).

| Tier | Definition | What it proves |
|---|---|---|
| **Repeat** | Same task_id, verbatim, every round (`fastapi_catalog`, `refactor_config`) | Memory pipeline works at all → "did it memorize" (caching sanity) |
| **Variant** | Same family, **different instance** every round, held to **strict same-family lanes** across all 5 rounds (bug_fix, implement_function, write_tests) | **The transfer test** — skill applies to unseen inputs, not memorized answers |
| **New** | One-off instances, never seen before/after, drawn **only from families never practiced** (`cli_tool`, `docker_configure`) | Specificity control — improvement must be specific to practiced families, not noise |

Per-tier counts per round:

```
tier_round_1: fastapi_catalog[Repeat] refactor_config[Repeat]
              bug_fix_text_wrong_regex[Variant] implement_knapsack[Variant]
              write_tests_temperature[Variant] cli_filter[New]
tier_round_2: fastapi_catalog[Repeat] refactor_config[Repeat]
              bug_fix_text_offbyone[Variant] implement_lru_cache[Variant]
              write_tests_stats[Variant] docker_streamlit_dashboard[New]
tier_round_3: fastapi_catalog[Repeat] refactor_config[Repeat]
              bug_fix_scheduling_offbyone[Variant] implement_merge_intervals[Variant]
              write_tests_cart[Variant] cli_json_pretty[New]
tier_round_4: fastapi_catalog[Repeat] refactor_config[Repeat]
              bug_fix_text_wrong_compare[Variant] implement_edit_distance[Variant]
              write_tests_banking[Variant] cli_word_freq[New]
tier_round_5: fastapi_catalog[Repeat] refactor_config[Repeat]
              bug_fix_scheduling_wrong_compare[Variant] implement_max_profit[Variant]
              write_tests_urlparser[Variant] cli_sales[New]
```

Invariant checks the generator enforces: every task_id exists in
`datasets/variants/tasks/<id>` with a `pristine/` snapshot; no instance is
reused across rounds except the two intentional Repeat tasks; **no instance
sits in two different tiers** (New ∩ (Repeat ∪ Variant) = ∅); Variant lanes
have the **same family every round** (no cross-round family drift); no
duplicates inside a single round. The generator refuses to write a CSV that
violates any of these.

## 5. How we will execute (operator runs, same PC, LM Studio on)

LM Studio must be running with `qwen/qwen3.5-9b` loaded (start via
`C:\Users\pc\.lmstudio\bin\lms.exe server start` if needed).

Round 1 (no `--resume` — fresh run). **Pilot first**: this round doubles as the
pilot — after it completes, verify the checklist in §6a before running rounds
2–5.

```
.venv\Scripts\python benchmark\run_benchmark.py --dataset datasets\variants\tier_round_1.csv --round 1 --arm both --run-id tier_run --limit 6
```

Rounds 2–5 (add `--resume` so completed rows are kept):

```
.venv\Scripts\python benchmark\run_benchmark.py --dataset datasets\variants\tier_round_2.csv --round 2 --arm both --run-id tier_run --limit 6 --resume
.venv\Scripts\python benchmark\run_benchmark.py --dataset datasets\variants\tier_round_3.csv --round 3 --arm both --run-id tier_run --limit 6 --resume
.venv\Scripts\python benchmark\run_benchmark.py --dataset datasets\variants\tier_round_4.csv --round 4 --arm both --run-id tier_run --limit 6 --resume
.venv\Scripts\python benchmark\run_benchmark.py --dataset datasets\variants\tier_round_5.csv --round 5 --arm both --run-id tier_run --limit 6 --resume
```

Per round this is 6 tasks × 2 arms + 6 treatment hooks ≈ 18 hermes invocations;
expect roughly 1.5–3 h per round on this hardware.

Treatment home (`runs/tier_run/homes/treatment_home`) persists across rounds and
receives the post-task memory hook; control home is wiped + re-seeded (skills
included) every round. Watch progress anytime:

```
Get-Content G:\HermesBench\runs\tier_run\progress.json
```

## 6. What comes after the run

1. Verify `metrics.csv` (60 rows = 6 tasks × 2 arms × 5 rounds; 0 blanks in
   `passed`/`timed_out`/`session_id`), re-sort to canonical (round, arm) order,
   regenerate `results.xlsx` + plots.
2. Verdicts (automatically emitted by `metrics_engine.py`, both console and
   `results.xlsx`):
   - **Whole-dataset verdict** (unchanged format): "CLAIM SUPPORTED for:
     <metrics>" or "CLAIM NOT SUPPORTED" — the same style as `other_run`.
   - **Tier-sliced verdicts** (new): one verdict per tier — Repeat
     (memorization), Variant (transfer), New (specificity control — should
     stay flat if learning is specific). The `tier_verdict` sheet in the xlsx
     has tier × metric rows with `treatment_improving`/`control_improving`/
     `supported` flags; the runner log also prints `TIER VERDICT [...]` lines
     at the end of the run.
3. Professor-ready tables, sliced by **tier** and arm per round:
   - Repeat: score trend round 1→5 (does memory injection help the same task?)
   - Variant: transfer trend (the real self-improvement test)
   - New: flatness control
4. Mechanism evidence: `hook_*` columns (including `skipped(tier=New)` rows
   proving the New control was never hooked), `memories/MEMORY.md` growth,
   skills deltas, `state.db` growth — "the loop wrote and the next session
   read".
5. Dual-case summary: Case 1 (`other_run`, stateless → no learning) vs
   Case 2 (`tier_run`, hooked → does it learn?).
6. Honest framing for the professor: Hermes's loop is *context-augmentation*
   (cached procedures in `SKILL.md`/`MEMORY.md` injected into the prompt), not
   weight updates — "self-augmenting with cached procedures" is the defensible
   term; whether "self-improving" is accurate is a discussion point.
7. Known limitations to state up front (in a one-line caveat, not to fix):
   - **New tier is thin (n=1/round, n=5 total)**: a single bad/lucky round on
     `docker_streamlit_dashboard` swings the whole "flatness control." Present
     the raw per-round New scores alongside any trend line so an outlier round
     is visible, not hidden by smoothing.
   - **New tier mixes families** (`cli_tool` ×4, `docker_configure` ×1). That's
     fine as "unpracticed-family" noise control, but never caption it as a
     "cli_tool trend" — it's an *unpracticed-family, mixed* control.

## 6a. Pilot round 1 (before committing to rounds 2–5)

Run round 1 only (`--arm both`, no `--resume`), then confirm in
`runs/tier_run/metrics.csv`:
- all 6 rows present, `tier` populated (`Repeat,Repeat,Variant,Variant,Variant,New`);
- treatment `hook_status` correct: 1 × `skipped(tier=New)` for `cli_filter`,
  plus real hook execution (`ok`/`error`) on the 5 Repeat/Variant rows;
- control arm rows have empty `hook_*` (never hooked);
- `results.xlsx` generates with the `tier_verdict` sheet and no errors.

If clean, run rounds 2–5 with `--resume` per §5.

**Hook error policy (decided now, not at 2am):**
- `hook_status = "error"` on any Repeat/Variant row (hook session crashed or
  exited non-zero) → **log it and continue**, but note it in the write-up.
  The hook is a *bonus* write channel; a lost lesson on one task weakens
  treatment slightly, it does not invalidate the run. Stopping the run for it
  would cost hours for no correctness gain.
- `hook_status = "error"` on *all* 5 Repeat/Variant rows (or `skipped(tier=New)`
  missing on `cli_filter`) → **stop and fix** before rounds 2–5: the write
  path itself is broken, and every subsequent treatment round would silently
  run without learning, reproducing Case 1.
- `hook_status = "error"` on 2–4 of 5 rows → **pause and investigate** before
  rounds 2–5 (do not auto-stop the run, do not auto-continue): decide whether
  the errors share a cause (flaky write path, bad prompt, LM Studio
  instability) vs. isolated task-specific failures. Resume only once the cause
  is named; log the decision.
- Control arm showing any non-empty `hook_*` value → **stop and fix** (control
  must never be hooked; that would break the comparison).

Rough decision ladder (1 = continue, 5 = stop, middle = investigate):
`1 failing → log & continue · 2–4 failing → pause + root-cause · 5 failing /
control contaminated → stop and fix before rounds 2–5`.

## 7. Files touched (Case 2 work)

- `benchmark/hermes_interface.py` — skills seeding, learning hook, `_invocation()`;
  `_run_kill_on_close()` job-object process-tree kill (Windows access-denied fix)
- `benchmark/benchmark_runner.py` — `tier` + `hook_*` metric columns; hook
  gated to ok-status tasks and to non-New tiers (`skipped(not-ok)`,
  `skipped(tier=New)`); end-of-run `TIER VERDICT [...]` log lines;
  `_remove_windows_reserved_files()` + `kill_agent_orphans()` +
  `_process_table()`/`_ancestor_pids()` + restore escalation (Windows
  access-denied fixes)
- `benchmark/task_loader.py` — `tier` field
- `analysis/metrics_engine.py` — tier-sliced verdicts (`verdict_by_tier`,
  `tier_verdict` xlsx sheet, `print_tier_verdicts`); whole verdict unchanged
- `config/config.yaml` — `seed_skills`, `learning_hook`
- `datasets/build_tiered_datasets.py` — tiered dataset generator (with
  confound checks: no cross-tier reuse, no Variant family drift)
- `datasets/variants/tier_round_1.csv … tier_round_5.csv` — generated datasets
- `tests_selftest.py` — extended for the `tier_verdict` sheet + xlsx sheet count
  + access-denied auto-recovery regression tests
- `runs/other_run/` — **untouched** (Case 1 evidence, 80 rows)
