# HermesBench

Benchmark framework for a university research project evaluating the claim that
**Hermes Agent** (Nous Research) is a **self-improving AI agent**.

> Research question: *"Does Hermes Agent demonstrate measurable
> self-improvement over repeated benchmark execution?"*

The model weights never change (LM Studio serves a frozen GGUF). The claim is
tested at the *system* level: Hermes' learning loop (skills, memory, session
recall). The benchmark isolates that loop with a treatment/control design.

## Experimental design

| | Treatment arm | Control arm |
|---|---|---|
| Hermes home | persists across rounds | wiped + re-seeded every round |
| Skills / memory | accumulate | erased |
| Model | same LM Studio GGUF | same |
| Tasks | same battery, same order | same |

* Fresh **one-shot session per task** (`hermes -z`), so improvement must come
  from persistent learning artifacts, not conversational context.
* Each arm gets an **isolated `HERMES_HOME`** (seeded once from your real
  `config.yaml` + `.env`); your real Hermes install is never modified.
* Metrics are collected per task execution; round-level trends are tested with
  **Mann-Kendall** and **OLS slope** tests; treatment vs control at the final
  round with a **Welch t-test**.

**Interpretation rule:** the claim is supported for a metric if the treatment
arm shows a significant improving trend (p < 0.05) that the control arm does
not also show. If both arms improve equally, the improvement is task
repetition/context noise, not the learning loop.

## Quick start

1. **Start LM Studio**, load the model (e.g. `google/gemma-3-4b` GGUF), and
   start the local server (`http://127.0.0.1:1234/v1`).
2. Create the environment (once):

   ```powershell
   py -3.13 -m venv .venv
   .\.venv\Scripts\pip install -r requirements.txt
   ```

3. Validate the environment (no agent runs, no server needed):

   ```powershell
   .\.venv\Scripts\python benchmark\run_benchmark.py --dry-run
   ```

## Sharing with a teammate

The config is **portable**: `config/config.yaml` uses `${LOCALAPPDATA}` (or
just `hermes` under the user's local app-data folder), and the config
loader (`benchmark/config_loader.py`) auto-detects the Hermes install on
any machine — no usernames are hardcoded anywhere. Requirements on the
teammate's machine:

* Hermes Agent installed (`hermes.exe` under `%LOCALAPPDATA%\hermes\...`)
  and configured (its real `config.yaml` + `.env` define the model).
* LM Studio running with the same GGUF model on `http://127.0.0.1:1234/v1`
  (important for thesis validity: one model, one machine for the whole run).
* If the auto-detection ever fails, just set `hermes.executable` and
  `hermes.real_home` in `config/config.yaml` to the teammate's paths.

**Do not share** `runs/` and `logs/` — they contain machine-specific
seeded homes and old metrics. Everything else (config, datasets, benchmark/,
analysis/, ui/) can be zipped as-is.

4. Run the benchmark (full: both arms × rounds; `--limit 3` for a quick test):

   ```powershell
   .\.venv\Scripts\python benchmark\run_benchmark.py --rounds 3 --arm both --limit 3
   .\.venv\Scripts\python benchmark\run_benchmark.py --rounds 3 --arm both
   ```

5. Explore results:

   ```powershell
   .\.venv\Scripts\streamlit run ui\app.py
   ```

## Pipeline

```
Task Dataset ──▶ Hermes Agent ──▶ LM Studio ──▶ Deterministic Grader
                                                     │
                                                     ▼
                                               Metrics Engine
                                                     │
                        ┌──────────────┬────────────┴───────────┐
                        ▼              ▼                       ▼
                   metrics.csv    results.xlsx             plots/
                   (raw rows)     metrics · summary     PNGs per metric
                                  trends · recovery    + verdict console
```

After the graders score every (round, arm, task) execution, the **metrics
engine** (`analysis/metrics_engine.py`) derives everything else from the
same `metrics.csv` — the stage is idempotent, so it can be re-run on any
existing run:

```powershell
python analysis/metrics_engine.py --csv runs/<run_id>/metrics.csv
```

Artifacts (all under `runs/<run_id>/`):

* **metrics.csv** — one row per execution (score, duration, tokens, events,
  learning-loop deltas; see Metrics below).
* **results.xlsx** — four sheets: `metrics` (raw), `summary` (round × arm
  aggregates), `trends` (Mann-Kendall tau/p + OLS slope per arm/metric, and
  the final-round treatment-vs-control Welch t-test), `recovery` (failure→
  success recovery rate per round per arm).
* **plots/** — success rate with bootstrap CI bands, every metric's
  per-round series per arm, learning-loop artifact accumulation, score
  distributions, recovery rate, human interventions (12 PNGs).
* Console verdict: the claim verdict (`CLAIM SUPPORTED for: ...`) is
  printed at the end of every run and logged to `logs/<run_id>.log`.
* **Dashboard** — `streamlit run ui\app.py` (viewer only; reads the same
  on-disk artifacts, can also launch runs).

Outputs land in `runs/<run_id>/` (metrics.csv, results.xlsx, plots/,
artifacts/ with per-task responses) and `logs/<run_id>.log`.

## CLI reference

```
python benchmark/run_benchmark.py [--config config/config.yaml]
                                   [--run-id ID] [--rounds N]
                                   [--arm treatment|control|both]
                                   [--tasks id1,id2] [--category prog,term]
                                   [--limit N] [--resume] [--dry-run]
                                   [--no-judge]
```

`--resume` continues a run in the same `runs/<run_id>/` directory (use
`--run-id` to pick it). `--dry-run` checks the environment and task
workspaces without executing anything. `--refresh-pristine` snapshots the
current workdir of every task into `tasks/<task_id>/pristine/` (one-time
setup for hand-made datasets).

### Manual round-by-round mode

Instead of one long overnight run, the benchmark can be executed one round
at a time. The treatment home persists between invocations (learning
accumulates) and the control home is reset per round, so the chunked
schedule is statistically identical to a single run:

```powershell
# round 1 (first time, creates the run folder)
python benchmark\run_benchmark.py --dataset datasets\variants\round_1_se.csv --round 1 --arm both --run-id thesis_run

# any later day / after a crash — same run-id + --resume
python benchmark\run_benchmark.py --dataset datasets\variants\round_1_se.csv --round 2 --arm both --run-id thesis_run --resume
python benchmark\run_benchmark.py --dataset datasets\variants\round_1_se.csv --round 5 --arm both --run-id thesis_run --resume
```

Rules: always the same `--dataset` and `--run-id`; add `--resume` after the
first chunk; never delete `runs/thesis_run/` in between. A crash loses at
most the task that was running when it happened — every completed task is
written to `metrics.csv` immediately, and `--resume` skips what's already
done. (Crash recovery without `--round`: rerun the same command with
`--rounds N --resume`.)

### Workspace isolation

Every task execution starts from an identical, untouched fixture: before
each (round, arm, task) run the runner restores the task workdir from its
`pristine/` snapshot (`restore_workspace`). The agent's edits therefore
never leak into later rounds or across arms — a hard requirement for the
treatment/control comparison. The task generator writes `pristine/`
automatically; generated datasets and the v1 dataset both ship with one
for every task (verified by the self-tests).

## Known limitations

* **Log-signal metrics** (`tool_call_log_events`, `error_log_events`,
  `retry_log_events`, `reflection_log_events`): Hermes calls
  `logging.disable(logging.CRITICAL)` during one-shot (`-z`) runs, so its
  `agent.log` receives no per-turn activity lines — these metrics stay `0`
  for the whole run. The harness warns about this at the first task; treat
  them as *unavailable*, not as zero activity. `api_calls` (from the usage
  JSON) remains reliable.
* `human_interventions` counts tasks that needed manual attention
  (timeout / crash / failed exit), not literal human clicks.
* Recovery rate only becomes meaningful from round 2 onward.

## Metrics

Per task execution (metrics.csv row): duration, status (ok/timeout/failed/
crashed), exit code, score (0–1, continuous → trend-friendly), passed
(score ≥ threshold), API calls and token usage (from `--usage-file` JSON),
session id, heuristic log events (tool calls / errors / retries /
reflections — counted in the agent log within the task's time window),
failed request dumps, human interventions (tasks needing manual attention:
timeout/crash/failed exit), and learning-loop state deltas (skill files,
memory files/bytes, state.db size) before/after the task.

Derived round-level metrics (analysis):
* **success rate** — passed / tasks per round
* **error rate** — mean error events per round
* **recovery rate** — % of previously-failed tasks that pass in a later
  round, per arm. A rising recovery rate is the strongest direct evidence
  of the learning loop fixing its own past failures.
* **human interventions** — count per round per arm

## Dataset

### Static dataset: `datasets/benchmark.csv`

16 tasks across programming, research, terminal, and reasoning. Grading is
deterministic where possible:

| check_type | meaning |
|---|---|
| `contains` / `regex` | response content check |
| `file_exists` / `file_contains` | artifact in the task workspace |
| `code_exec` | model code is executed against `check(name, cond)` tests |
| `file_code_exec` | model edits a file; tests import and exercise it |
| `llm_judge` | LLM-as-judge via LM Studio (rubric → score 0–1) |

`code_exec` executes model-generated code in a temp dir with a 60 s timeout
(your machine, local tasks — keep the dataset trusted).

### Dynamic SE dataset: `datasets/generate_tasks.py` → `datasets/variants/`

Task-variant generator for the **Software Engineering** domain (same
combination-seed + strict self-validation pattern you used for the saif
project, but fully deterministic — no LLM involved, so there is no
dataset-generation leakage and every task's correctness is machine-checked).

```
python datasets/generate_tasks.py --list                      # families
python datasets/generate_tasks.py --rounds 5 --per-family 2   # 14 tasks/round
python datasets/generate_tasks.py --families bug_fix,cli_tool --rounds 2
```

7 families (36 hand-authored parameter combinations), all validated before
emission: the *reference* solution must score 1.0 against the real graders
and a *buggy counterpart* must score < 1.0, otherwise the variant is rejected
(recorded in `manifest.json`):

| family | difficulty | grading |
|---|---|---|
| `bug_fix` | medium | seeded logic bug in a ~50-line module; tests run on the fixed file |
| `implement_function` | hard | spec + stub file; hidden unit tests |
| `refactor` | medium | split a god function; behavior tests **and** banned anti-patterns |
| `fastapi_setup` | medium | static checks: endpoints, error handling, requirements |
| `docker_configure` | medium | static checks: Dockerfile + compose conventions |
| `write_tests` | hard | written tests must pass on the good module and fail on the buggy one |
| `cli_tool` | complex | exact stdout comparison via `command_check` |

Each round emits `datasets/variants/round_<n>_se.csv` with *fresh parameter
combinations*, so rounds differ (no memorization) while the `family` column
stays constant — recovery-rate analysis matches variants across rounds by
family. Fixtures live under `datasets/variants/tasks/<task_id>/work/`.

Run a variant round like any dataset:

```
python benchmark/run_benchmark.py --dataset datasets/variants/round_1_se.csv --rounds 5 --arm both
```

New grader features used by the SE dataset (all in `benchmark/graders.py`):

| feature | meaning |
|---|---|
| `a+b` check types | mean of sub-scores, e.g. `file_contains+file_code_exec` |
| multi-line `file_contains` | one `glob\|needle` per line → partial credit |
| `banned` column | semicolon-separated anti-patterns; if found in the code → 0 |
| `test_suite` | `GOOD_MODULE=`/`BUGGY_MODULE=` lines; model's `test_*` functions must pass on good and fail on buggy (mutation-testing style) |
| `command_check` | `CMD:<command>` + expected stdout lines; runs in the workdir |

`task_loader` also reads the optional `family` column (defaults to task_id);
`metrics.csv` carries `family` per row, and `recovery_rate` groups by family
(rounds with different task variants of the same family still count as
"the same task").

## Caveats / limitations (write these into your thesis)

* **Same-model judge** — the judge is the same GGUF by default. Configure a
  stronger `judge_model` in `config.yaml` if available.
* **Heuristic log counts** — tool-call/error/retry/reflection counts come
  from regex patterns in the agent log; treat them as relative signals, and
  verify against `api_calls` and `failed_request_dumps`.
* **Task length** — Hermes nudges skill/memory creation after ~15/6 turns.
  Single-step chat tasks may never trigger the loop; the dataset therefore
  favors multi-step agentic tasks. Check `learning_artifacts.png` to see
  whether skills actually accumulated.
* **Small models and tool use** — a 4B model (e.g. gemma-3-4b) frequently
  *narrates* a tool call in text instead of executing it (visible as
  `api_calls == 1` with a `[tool_code]`-style response and a missing output
  file). This makes file/terminal tasks fail honestly. If your research
  question requires tool execution, use a stronger tool-calling model
  (e.g. Hermes 4 14B/70B, Qwen3) — switch in LM Studio and in the hermes
  config; no framework changes needed.
* **Sampling noise** — temperature sampling produces run-to-run variance
  (you may see the same task pass in one arm and fail in the other).
  This is exactly what the design measures: run enough rounds/tasks that
  variance is visible as CI bands, and use the control arm to separate
  noise from learning.
* **Speed** — a 4B model on a 3050 Ti takes roughly 1–5 min per agentic task;
  plan for ~1 h per arm-round of 16 tasks.

## Project layout

```
HermesBench/
├── benchmark/      runner, hermes interface, graders, task loader, CLI
├── analysis/       statistics.py (Mann-Kendall, Welch, bootstrap),
│                   graphs.py (matplotlib report plots)
├── ui/app.py       Streamlit dashboard (launch + live metrics + reports)
├── datasets/       benchmark.csv + tasks/<task_id>/work/ fixtures,
│                   generate_tasks.py (SE variants), variants/ (per-round CSVs)
├── config/         config.yaml (hermes path, LM Studio, arms, thresholds)
├── runs/<run_id>/  metrics.csv, results.xlsx, plots/, artifacts/, homes/
├── logs/           per-run logs
└── metrics/        (convenience copy location; canonical data lives in runs/)
```
