# HermesBench — Prior Experiments Dossier (other_run / tier_run / case3_run)

This file is the full write-up of the three completed experiments, their
methodology, per-run implementation details, abstract, and how they
differentiate. It is the baseline Case 3B (SQLite memory medium) was designed
against.

---

## 1. Shared methodology fabric (all runs)

- **Engine**: `benchmark/benchmark_runner.py` + `benchmark/hermes_interface.py`
  + `analysis/metrics_engine.py`. Agent = real `hermes.exe` (home `G:\Hermes`),
  LM Studio `qwen/qwen3.5-9b` @ `http://127.0.0.1:1234/v1`, no token cap
  (wall-clock cap only, `hermes.timeout_s`).
- **5 rounds, 2 arms**: the treatment arm's home directory persists across
  rounds; the control arm is **wiped + re-seeded every round** (skills
  included), so control can never learn.
- **Both arms get the identical task order per round**; rows stored in canonical
  `round -> arm` order; `--resume` re-runs only retryable rows
  (`timeout` / `skipped` / `harness-error`) and **replaces them in place** —
  never appended, never duplicated (lock-step).
- **Grading**: per-family graders driven by the task-dir config —
  `code_exec`, `file_contains`, `file_code_exec`, `regex`, `llm_judge`.
- **Verdict gates**: §8.2 rules — Case 1/2 style = whole-dataset pass-rate
  comparison; Case 3 style = R5-only **ΔPass ≥ +5% AND Fisher p < 0.05**.
- **Output**: `results.xlsx` sheet set (metrics / summary / improvement / gain /
  families / regression / trends / tier_verdict / recovery) + console verdicts;
  `progress.json` for live tracking.
- All runs used `hermes -z` (zero-shot, stateless session). The "learning" is
  the **context loop**: a post-task hook writes lessons into the persisted home
  between rounds, and the next session reads them back. The medium differs per
  case: no channel (Case 1) -> open memo/skills channel (Case 2) -> quality-
  gated memo/skills channel (Case 3A) -> SQLite state.db medium (Case 3B).

---

## 2. `other_run` — Case 1: the naive baseline (the null result)

**Scope**: 80 rows = 5 rounds × 2 arms × 8 tasks. Run dir `runs/other_run/`.

### Implementation
- **No loop at all.** Plain task loop: restore `pristine/` → agent runs task →
  graded.
- **No post-task hook, no skills seeding, no tiering.**
- Default 8-task dataset (`datasets/benchmark.csv`) — the same 8 tasks every
  round.

### Result
- Final per-arm means: **65.3% (treatment) vs 66.1% (control)** → **CLAIM NOT
  SUPPORTED** (verdict NO). No trend in either arm.

### Post-hoc diagnosis (CASE2_PLAN.md §2) — *why* it was null
- `hermes -z` is **stateless** — the write trigger never fires; `state.db`
  grew 5.8 → 64.5 MB = *exhaust*, not fuel.
- The 542 bundled Hermes skills were **invisible** to bench homes.
- `seed_home()` copied only `config.yaml` / `.env` / `SOUL.md`.

### Abstract
*A stateless agent with no memory channel shows no self-improvement
(T 65.3% vs C 66.1%) — the learning loop was structurally absent.*

### Role
Diagnosis, not conclusion — it motivated everything that followed.

---

## 3. `tier_run` — Case 2: the unfiltered hook (first real loop)

**Scope**: 60 rows = 5 rounds × 2 arms × 6 tasks. Run dir `runs/tier_run/`.

### Implementation
- **Tiered dataset generator** (`datasets/build_tiered_datasets.py`) with hard
  invariants: no cross-tier reuse, no Variant family drift round-over-round,
  no intra-round duplicates; it refuses to write a violating CSV.
  Per round: 
  - **Repeat ×2** — `fastapi_catalog`, `refactor_config`, *identical* every
    round (memorization sanity test).
  - **Variant ×3** — bug_fix lane, algorithm lane (implement_*), write_tests
    lane: same family, *different instance* each round (the transfer test).
  - **New ×1** — `cli_filter` / `docker_streamlit_dashboard`: held-out
    families, never practiced (specificity control).
- **Hook** (`learning_hook` in `config/config.yaml`), **unfiltered**: fires
  after *every* `status == ok` task (`MEMORY_ONLY_HOOK_PROMPT`, memory
  pipeline writes into the treatment home). Gating only: `skipped(not-ok)`,
  `skipped(tier=New)`. **No quality gate, no pruning, no contract skill.**
- **Seeding**: `seed_skills: true` — 542 bundled Hermes skills seeded into
  both arm homes.
- **Metrics**: PassRate@round (score ≥ 0.7), tier-sliced verdicts per tier
  (Repeat / Variant / New) → `tier_verdict` xlsx sheet + `TIER VERDICT`
  console lines; `hook_status` / `session_id` columns.

### Result
- 60/60 `ok`; `tier_verdict` **40/40 `supported=False`** → **CLAIM NOT
  SUPPORTED**.
- Round means: treatment 0.667 / 0.500 / 0.701 / 0.667 / 0.729 (ALL **0.653**)
  vs control 0.722 / 0.646 / 0.500 / 0.625 / 0.812 (ALL **0.661**).

### Post-hoc fix brief (no re-runs except one infra row)
- `write_tests_*` zeros (9 of 10 rows 0.0) = **genuine agent failures**:
  wrong-import differential idiom (`from good import Cart` instead of the
  `mod` contract) → `runner-failed`; prose answers with no code fence →
  `runner-failed`/`no-tests`. Not a harness bug; a re-run would not change
  scores.
- r4 control `fastapi_catalog` = **infra crash** (client-side abort, no real
  result, zero-byte `nul` litter) → re-run in place → **0.75** (`file_contains
  6/8`).
- `refactor_config` `file_code_exec:banned` rows = **task-side failure**: the
  agent verifies via a temp script and never overwrites `work/ugly.py`; the
  r1-persisted skill taught *verification*, not *persisting edits* → reframed,
  not fixed.

### Abstract
*An unfiltered context loop demonstrably writes (hooks fire, MEMORY.md /
skills / state.db grow) yet moves no metric (T 65.3% vs C 66.1%) — persisted
lessons do not target the failures that repeat, and terminal-only hacks
pollute memory.*

---

## 4. `case3_run` — Case 3A: the quality-gated loop

**Scope**: 100 rows = 5 rounds × 2 arms × 10 tasks. Run dir `runs/case3_run/`.

### Implementation — four harness upgrades over Case 2
1. **Target-diff quality gate** (`verify_workdir_modified` in
   `hermes_interface.py`): the hook fires only if `git status --porcelain`
   inside the workdir is non-empty (mtime fallback). Terminal-only hacks
   never enter memory. New hook statuses: `skipped(no-diff)`,
   `skipped(score<1.0)`.
2. **Contract meta-skill** (`skills/benchmark_coding_contract.md`): seeded into
   **both** arms, survives the control's per-round wipe — File Modification
   Rule, Code Block Formatting, `import mod` module contract.
3. **Adversarial reflection hook** (`ADVERSARIAL_HOOK_PROMPT`): a quality
   filter that instructs the agent to **discard temporary-script / hardcoded-
   hack lessons** and reply `NO_SKILL_PERSISTED` when nothing generalizable
   exists.
4. **Active skill pruner** (`prune_failing_skills`): after any `score < 1.0`,
   deletes every skill file the agent actually used during that task; never
   prunes the contract. Counted in the `pruned_skill_files` column.

Plus:
- `benchmark/infrastructure_recovery.py` module (Windows recovery routines,
  re-exported by the runner for back-compat; 3× backoff
  `safe_restore_workspace`).
- `case3:` block in `config/config.yaml`
  (`enabled`, `seed_contract_skill`, `require_workdir_diff`, `hook_min_score:
  1.0`, `adversarial_hook`, `prune_failing_skills`, `delta_pass_threshold:
  0.05`, `alpha: 0.05`).
- **Strict passing = score == 1.0**.
- **Curriculum** (spec §6): 3 Repeat / 5 Variant / 2 New per round, recombined
  from the 34-instance pool. Repeat = `fastapi_catalog`, `refactor_config`,
  `write_tests_temperature`. Variant = bug_fix ×2 lanes, algorithms ×2 lanes,
  testing ×1 lane. New = held-out `cli_tool` / `docker_configure` only. The
  generator enforces 10 rows/round, no intra-round dupes, task stays in one
  tier, and flags intentional 5th-round reuses in `REUSE_NOTES` (the 34-
  instance pool cannot fully supply the board).
- **Metrics** (`case3` xlsx sheet + independent console verdict emitted in
  `_finalize`, so a plotting hiccup can never swallow the verdict):
  - **PassRate@1** = #tasks with score == 1.0 / total, per arm per round.
  - **ΔPass** = PassRate(treatment, R5) − PassRate(control, R5).
  - **VTR** = pass rate on `tier == "Variant"` rows per arm.
  - **Fisher exact** = 2×2 [treatment pass/fail] vs [control pass/fail],
    final round, two-sided.
  - **SUR** = Σ skills written on passed tasks / peak skills persisted,
    clamped [0, 100] (proxy — no per-skill retrieval column in metrics.csv).
  - **Verdict** = `YES` iff ΔPass ≥ **+5%** AND p < **0.05**; else `NO`
    ("CASE3 VERDICT: ..." console line per spec §8.2).

### Result
- Strict-pass (score == 1.0) per round:
  R1 T7/C7, R2 6/5, R3 4/3, R4 4/2, R5 3/4.
- **ΔPass = 0.3 − 0.4 = −10%** (treatment got *worse*), p = 1.0,
  OR 0.6429, VTR 0.60 vs 0.48, SUR 0 → **CASE3 VERDICT: NO**.

### Abstract
*Even under strict quality gates (diff-gated, pruned, contract-seeded memory),
the treatment arm does not reach perfect scores more often than control — it
declines (ΔPass −10%; Fisher p = 1.0). The learning channel is faithful; the
persisted skill becomes irrelevant to the failures that repeat.*

---

## 5. Differentiation at a glance

| | `other_run` | `tier_run` | `case3_run` |
|---|---|---|---|
| Role | Case 1 baseline | Case 2 unfiltered loop | Case 3A gated loop |
| Loop | **none** | hook, unfiltered | hook + diff gate + adversarial + pruner + contract |
| Gating | — | `ok` status only | `ok` + workdir diff + score == 1.0 |
| Curriculum | same 8 tasks / round | Repeat 2 / Variant 3 / New 1 | Repeat 3 / Variant 5 / New 2 |
| Pass definition | ≥ 0.7 | ≥ 0.7 | **== 1.0** |
| Rows | 80 | 60 | 100 |
| Key metric | whole-run means | tier verdicts | ΔPass + Fisher |
| Seeding | none | 542 skills (both arms) | 542 skills + contract (both arms) |
| Verdict | NO | NO (40/40 unsupported) | NO (ΔPass −10%, p = 1.0) |
| Section | CASE2_PLAN.md §2 (diagnosis) | CASE2_PLAN.md | CASE3_PLAN.md |

## 6. The through-line to Case 3B

- Case 1: no channel → null.
- Case 2: open, unfiltered channel → null (pollution).
- Case 3A: filtered channel → still null, now negative.
- **Case 3B (next)**: asks "is the *medium* the problem?" — swaps the memo
  file / opaque bundled skills for a **SQLite `state.db` memory medium**
  (schema + reader, stuck-tool fix, long-context concat fix, memory file
  growth cap), keeps the same strict gates, and tests whether a readable,
  queryable memory store changes anything.
  Plan + full fix log: `docs/CASE3B_PLAN.md`.