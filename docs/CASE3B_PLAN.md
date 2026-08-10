# HermesBench — Case 3B: Hardened Learning Loop (Plan & Implementation Notes)

Status: **implementation complete, offline validation passed, waiting for
rounds to be run by the operator**

Reference: `G:\Here is the complete.md` (the Case-3 A-to-Z spec, v3.0);
`docs\CASE3_PLAN.md` (Case 3A baseline); `case3 fix.docx` (post-mortem fix
proposals that Case 3B implements).

---

## 1. Why a Case 3B

Case 3A ran to completion (5 rounds, 100 rows, `runs\case3_run`). Its final
**verdict was NO** (R5 ΔPass −10%, Fisher p = 1.0). The post-mortem
(`case3 fix.docx`) and the run audit surfaced five harness weaknesses that
cannot be patched into a finished run without biasing it, so they are
implemented as a **new variant** with its own config and run-id:

| # | Weakness | Case 3B change |
|---|---|---|
| 1 | Post-task hook shares the 900 s task timeout; 1/100 hooks hit it | `case3.hook_timeout_s = 120` — hook sessions are hard-capped; `TimeoutExpired` degrades to a recorded non-fatal `error` row |
| 2 | Only score == 1.0 passes ever wrote lessons; near-miss lessons were discarded | `case3.hook_tiered = true` with `hook_memory_min_score = 0.7`: score ≥ 1.0 → adversarial **skill** hook; 0.7–0.99 → **memory-only** hook (new `MEMORY_ONLY_HOOK_PROMPT`); < 0.7 → skip |
| 3 | Test-family tasks keep dying with `runner-failed` (bare asserts / top-level code) | `skills/benchmark_coding_contract.md` gains §4 "Standardized Test-Writing Template" (import mod, all checks in `def test_*`, stdlib only, no top-level side effects) |
| 4 | No per-invocation context cap exists in `hermes -z`; long runaway conversations | `config3b.yaml` lowers task cap to **300 s** (wall-clock; the only cap the CLI supports) |
| 5 | `pruned_skill_files` was always 0 — nothing injected skill knowledge | `case3.inject_skills = {enabled: true, top_k: 3, max_chars_per_skill: 600}` — `run_task()` pre-pends a `RELEVANT SKILLS (consult these before answering): …` preamble, keyword-matched against the arm home skill library |

Deviations from spec §4.2/§5.1 (tiered gates, injection, shorter cap) are
**intentional and documented here** — they are the experiment, not a repair
of Case 3A.

## 2. What changed vs Case 3A

### 2.0 Post-review fixes (advisory review round)

Reviewer audit found 2 significant + 3 minor issues; all fixed and covered by
new regression tests:

1. **Critical — control-arm hook leak (fix #1).** `_run_one` ran the hook
   whenever `hook_status is None`, which is exactly what non-eligible
   (control, dry-run, hook-disabled) rows have — the original `elif
   hook_eligible:` guard was lost in the gate refactor. Now the hook runs
   only at `if hook_eligible and hook_status is None:`; gate is consulted
   for hook-eligible rows only; control rows keep `hook_status = None` /
   NaN exactly as in Case 3A. Regression tests assert the gate contract.
2. **Config key mismatch (fix).** `HermesInterface` read
   `config["benchmark"]["learning_hook"]` while the runner and
   `config3b.yaml` define `learning_hook:` **top-level**; disabling it at the
   root would have been ignored by the interface. Both now read
   `config.get("learning_hook", {}).get("enabled", True)`.
3. **Missing hook columns (fix).** The restore-failed / harness-error
   fallback rows omit the five `hook_*` metrics; now explicitly `None` for
   schema consistency.
4. **Dead code (fix).** Removed unused `cur`/`prev` locals in
   `BenchmarkRunner.__init__`.
5. **Cross-task pruner leakage (fix).** `prune_failing_skills` was fed the
   cumulative `agent.log`, so a failing task could prune skills viewed by
   earlier passing tasks in the same round. New `_slice_task_log(log,
   start, end)` slices agent.log to `[task_start, task_end]` and the pruner
   now receives only the current task's slice (falls back to the full log
   only when no slice can be built). Regression: `prune slice` tests.
6. **Truncated test file.** Reviewer received a clipped `selftest.py`
   excerpt; the full `tests_selftest.py` (not `selftest.py`) is self-consistent.
7. **hook_eligible truthiness (2nd review).** `self.learning_hook` is
   `bool(...)`, so the old `self.learning_hook is not None` was always
   True — a config with `learning_hook.enabled: false` would still mark
   treatment rows eligible. Now `bool(self.learning_hook) and arm ==
   self.hook_arm and not self.dry_run`. Regressions: `3b reviewer2`
   tests instantiate the runner with the hook disabled and assert
   ineligibility.

### 2.1 `config/config3b.yaml` (new)

```yaml
hermes:
  timeout_s: 300              # fix #4 (was 900)
learning_hook:
  exclude_tiers: []           # fix part of #2 (tier exclusions removed)
case3:
  contract_template: true     # fix #3 (contract §4 template)
  hook_timeout_s: 120         # fix #1
  hook_tiered: true           # fix #2
  hook_min_score: 1.0         # adversarial threshold (unchanged)
  hook_memory_min_score: 0.7  # fix #2 memory tier floor
  adversarial_hook: true
  inject_skills:              # fix #5
    enabled: true
    top_k: 3
    max_chars_per_skill: 600
```

### 2.2 `benchmark/benchmark_runner.py`

- Pure `hook_gate(...)` policy replaces the inline chain in `_run_one` and is
  called only for hook-eligible rows (Treatment arm, hook on, not dry-run) so
  the **control arm keeps `hook_status = None` exactly like Case 3A**.
- Gate order preserved from 3A: tier-excluded → `skipped(tier=New)` (even on
  not-ok rows) → `skipped(not-ok)` → `skipped(no-diff)` → tiered scoring.
- Tiered returns `(None, adversarial=True, memory_only=False)` for score ≥
  1.0, `(None, adversarial=False, memory_only=True)` for 0.7–0.99, and
  `skipped(score<1.0)` below.

### 2.3 `benchmark/hermes_interface.py`

- `MEMORY_ONLY_HOOK_PROMPT`: post-task prompt that directs the agent to write
  a **memory entry only**, never a skill; default answer
  `NO_MEMORY_PERSISTED: no durable lesson qualifies.`; still must end in
  `DONE`.
- `run_learning_hook(..., memory_only=False)` — selects the memory template;
  hook subprocess runs with `timeout_s=hook_timeout_s`; on
  `subprocess.TimeoutExpired` returns a non-fatal `LearningHook` with the
  error recorded (never aborts the round). `adversarial` wins over
  `memory_only=False` only in the strict/normal tier.
- `_invocation(..., timeout_s=None)` — optional per-call timeout override.
- `HermesInterface` stores `self.config` and reads `case3.hook_timeout_s`.
- **Fix #5 injection**: `run_task()` calls `_skill_injection_context(task)`
  which tokenizes the task prompt (`_keyword_tokens`, stop-word filtered),
  scores `home_dir/skills/**/SKILL.md` heads (first 4000 chars) by keyword
  overlap, and pre-pends the top 3 as a `RELEVANT SKILLS (consult these
  before answering):` preamble. Returns `""` when disabled / no skills / no
  match, so the control-class prompt is unchanged.

### 3d `skills/benchmark_coding_contract.md` — §4 (fix #3)

New mandatory section in the contract skill (seeded into **both** arms like
the rest of §1–§4):

```markdown
## §4 Standardized Test-Writing Template (testing family)

For tasks that ask you to write tests:
1. `import mod` the module under test (dynamic handle, never the filename).
2. All checks live inside `def test_*()` functions — no bare asserts, no
   stray top-level code, no side effects at import time.
3. Use stdlib only (`unittest` / `assert`); no pytest, no third-party
   imports that may be absent.
4. Nothing may print or raise before the real test runner starts.
```

Fix is preventive: `runner-failed` (0.0) happened exactly when a test payload
crashed before producing `SUMMARY n/n`. Full compliance in the write_tests
family should convert those 0.0 rows into runnable (still graded strictly)
suites.

## 3. Consistency rules kept from Case 3A

- Hooks run **treatment only**; control arm rows keep `hook_status = None`.
- Control `reset_home()` wipes `control` between rounds; contract skill is
  re-seeded on both arms (`seed_home()` / `reset_home()`).
- Single runner instance per round; `--resume` after each round; identical
  5-round × 10-task × 2-arm curriculum (`datasets/variants/tier_round_1..5.csv`).
- Verdict remains §8.2: `YES` iff ΔPass ≥ +5% AND Fisher p < 0.05 on R5.

## 4. Execution protocol (operator runs — rounds NOT started)

LM Studio must be running with `qwen/qwen3.5-9b` loaded (`127.0.0.1:1234`).

```
# Round 1
.venv\Scripts\python.exe benchmark\run_benchmark.py --config config\config3b.yaml --dataset datasets\variants\tier_round_1.csv --round 1 --arm both --run-id case3b_run --limit 10
# Rounds 2–5 (identical, with --resume) 
.venv\Scripts\python.exe benchmark\run_benchmark.py --config config\config3b.yaml --dataset datasets\variants\tier_round_2.csv --round 2 --arm both --run-id case3b_run --limit 10 --resume
… (rounds 3, 4, 5 identically)
```

Expected per round ≈ 20–30 hermes invocations; 300 s task cap (was 900) and
120 s hook cap (was 900) bound worst-case round length ≈ 2 h.

## 5. Verification completed (offline)

- `python -m py_compile` on edited modules: clean.
- Full `tests_selftest.py` — **ALL OFFLINE SELF-TESTS PASSED**, with new
  regressions:
  - `hook_gate` strict vs tiered outcomes; tier (New) label precedence even
    on not-ok; no-diff skip; memory-only vs adversarial tier selection.
  - `HermesInterface` hook cap 120 s propagation; memory-only hook prompt
    selection; `_invocation(timeout_s)` fallback; hook `TimeoutExpired`
    non-fatal path.
  - Skill injection: no skills → empty preamble; keyword match → `RELEVANT
    SKILLS …` preamble.
- Dry run `run_benchmark.py --config config3b.yaml --dry-run` loads config,
  seeds both homes with 542 skills + contract.

## 6. Known caveats

- `hook_min_score`/`hook_memory_min_score` gate **records** only; the 0.7–0.99
  tier writes memory (not skills), reflected as `hook_mem_delta` rows, while
  `hook_skill_files_delta` stays 0 — the SKILL file row delta remains the
  SUR foundation.
- Injection only reads skills present in the treatment home; skipped-when-empty
  keeps the baseline prompt byte-identical, so the *marginal* change is
  measured, not the global effect.
- Fix #1's 120 s cap: a hook routinely truncates >120 s tasks, marked
  `error` (hook timeout) — distinguish from host failure via `hook_duration`.
- Store charts/`results.xlsx` go under `runs\case3b_run` (own version) so
  Case 3A data remains untouched.