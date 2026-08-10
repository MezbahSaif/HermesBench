# HermesBench — Faculty Presentation Notes (explained for a beginner)

> How to explain the whole project to faculty: every run, the methodology,
> the results, the limitations, the problems — in plain words, with the
> summary table and the answers to the questions faculty WILL ask.

---

## 1. The whole project in ONE sentence

> **"We made Hermes — an AI coding agent — work on the same coding tasks over
> 5 rounds. Half the time it was allowed to carry a notebook full of its own
> lessons; the other half it started fresh every time. We measured whether the
> notebook made it better."**

That's it. Everything else is details of the notebook.

## 2. The question we are answering

Hermes advertises itself as "self-improving." Faculty will ask: *what does
that even mean?* Our answer: **does letting the agent keep its own
memory/skills between attempts actually make it score higher?**

Key point to say up front: we do **NOT** touch its brain (weights) — we only
let it write notes and read them back. The honest name for that is
**context-augmentation**, not true learning. Say that word first; it saves you
from being cornered later.

## 3. The method — like explaining to a friend

- **Rounds**: 5 rounds = 5 "weeks." Each round = ~6–10 coding tasks: fix a
  bug, write tests, build a FastAPI app, a CLI tool, a Dockerfile, etc.
- **Two groups (arms)**:
  - **Treatment**: keeps its home folder. It can write lessons into it, and
    next round it sees them.
  - **Control**: home folder **wiped and re-seeded every round**. Same agent,
    same tasks, but zero memory — the "would it have improved anyway?" group.
- **Same task board in both arms** — so any difference is caused only by the
  memory.
- **Grading**: automatic — does the code pass hidden checks? Score 0–1. No
  human grading.
- **The verdict rule (pre-decided, so we cannot cheat)**: treatment wins ONLY
  if on the final round it has ≥ 5% more **perfect (1.0)** scores than control
  **AND** the stats test says p < 0.05 (not luck). Otherwise → "NO, claim not
  supported."
- **The hook**: our agent runs in "one-shot" mode (`hermes -z`), which *never
  saves anything on its own* (the discovery of run 1). So after each good
  task, we run one extra short AI session whose only job is: "distill lessons
  and save them into the notebook" (a memory file or a skill file). That is
  the ONLY channel where learning could happen.

## 4. The three completed runs — what to say about each

### Run 1 — `other_run` (the "oops" run) — 80 rows

- **What we did**: plain loop. Tasks → grade. **No notebook at all.**
  Dataset: 8 tasks/round (bug_fix / fastapi / cli_tool / docker_configure
  families), same board every season, no tiers.
- **Result**: treatment 65.3% vs control 66.1% — flat. Verdict: NO.
- **Why (the diagnosis — the best story)**: learning was **physically
  impossible**. `hermes -z` is stateless — it never writes memory. The DB grew
  5.8 → 64.5 MB, but that is transcript exhaust, not fuel. And the 542 bundled
  skills were invisible to the bench homes — the agents started with nothing.
- **Lesson**: "a null result proved the harness was broken, not the agent —
  so we fixed the harness." That is honest science.

### Run 2 — `tier_run` (the notebook appears) — 60 rows

- **What we did**: added the hook (run 1's fix) + seeded 542 real skills into
  both homes + tiered curriculum
  (`datasets/variants/tier_round_1..5.csv`, 6 tasks/round):
  - **Repeat** ×2 — same tasks every round (memorization test);
  - **Variant** ×3 — same family, different instance (transfer test);
  - **New** ×1 — never-practiced families (should stay flat control).
- **Result**: still flat — 65.3% vs 66.1%, all 40 tier verdicts NO. The hook
  demonstrably worked (notebook files grew!), but performance did not move.
- **Why**: the notebook was **unfiltered** — it saved junk (hacks,
  "temporary script worked!" notes) and, worse, saved lessons that did not
  target the actual repeated failures (e.g., test-writing tasks failed on a
  wrong import idiom, and the notes never addressed it).

### Run 3 — `case3_run` (the strict notebook) — 100 rows

- **What we did**: quality gates — save a lesson only if the task **scored
  1.0 AND files were really edited**; the reflection prompt was told to
  **discard hacks**; a **contract skill** was seeded into both arms (write to
  the file, use code fences, `import mod`); and a **pruner** deletes skills
  used in failed tasks. Dataset: `tier_round_1..5.csv` regenerated to 10
  tasks/round (3 Repeat / 5 Variant / 2 New).
- **Result**: treatment got *worse* — final round ΔPass **−10%** (3/10 vs
  4/10), p = 1.0, OR 0.6429, VTR 0.60 vs 0.48, SUR 0 → verdict NO.
- **Why** (5 weaknesses, all fixed in Case 3B — say them, then pivot):
  1. Near-miss lessons (score 0.7–0.99) — often the most instructive — were
     **thrown away**; a 0.99 task taught nothing.
  2. **Nothing was ever injected back** — `pruned_skill_files` was always 0 →
     the agent never read its own lessons during a task. A notebook that is
     never opened.
  3. No time cap → runaway 900-second conversations.
  4. Test-writing tasks kept dying with `runner-failed` (bad formatting).
  5. The hook shared the same 900 s timeout as tasks.

### Case 3B — `case3b_run` (next, 5 fixes): hook capped at 120 s; tiered hook
(score ≥ 1.0 → skill, 0.7–0.99 → memory-only); contract §4 test template;
task cap 300 s; **active injection** — top-3 relevant skills are pre-inserted
into every task prompt (`RELEVANT SKILLS (consult these before answering):`).

## 5. The summary table (put this on a slide)

| Run | What was tested | Notebook? | Result | Why it failed / what it proved |
|---|---|---|---|---|
| 1 `other_run` | baseline, no memory | no | 65.3% vs 66.1% — NO | no memory channel existed at all (harness bug) |
| 2 `tier_run` | open notebook, no filter | writes | 65.3% vs 66.1% — NO | wrote junk + lessons that missed the failures |
| 3 `case3_run` | filtered notebook | writes, never read | ΔPass −10%, p=1.0 — NO | near-misses discarded; nothing injected back; no caps |
| 3B `case3b_run` | filtered + injected + capped | writes AND reads | pending | fixes all five 3A weaknesses |

**The through-line (closing line)**:
> *"Run 1 proved the channel was missing. Run 2 proved an open channel
> pollutes. Run 3A proved a write-only channel is useless. Case 3B finally
> closes the loop — lessons are filtered, near-misses count, and the lessons
> are actually injected back into the task."*

## 6. Limitations — say these BEFORE faculty finds them

- Small scale: 5 rounds, 6–10 tasks/round, **one model** (qwen3.5-9b), one PC.
  Not generalizable — say it yourself.
- Task pool had 34 instances; some had to be **reused** in round 5 (flagged in
  `REUSE_NOTES`); the New tier had n=1 per round, so one lucky/unlucky round
  moves it.
- SUR metric is a **proxy**, not a real skill-retrieval measure.
- "Self-improvement" = context-augmentation, **not** fine-tuning. We never
  touch weights.
- LLM-judge tasks (summaries/essays) carry grader subjectivity.
- Statistics: the verdict uses only round 5; report p-values but also the raw
  percentages.

## 7. Cheat sheet — the 6 questions faculty WILL ask

1. **"Why did control also improve?"** — Control also *practices* the tasks
   every round and has the 542 seeded skills; only the persistent personal
   notes are removed. That is exactly the contrast we want — and in 3A control
   did not even improve.
2. **"Is this just fine-tuning?"** — No. No weight update anywhere; the
   "learning" is notes injected into the prompt.
3. **"How do you know the notebook was really written?"** — Per-task evidence
   columns: `hook_status`, memory-file deltas; the `skipped(tier=New)` rows
   prove the mechanism worked as designed.
4. **"Why only 5 rounds?"** — ~100 agent calls per case, hours per round, one
   local machine; this is a probe, not a training run.
5. **"Why that stats test?"** — Fisher's exact test is built for small counts;
   we report raw rates alongside so nothing hides behind the numbers.
6. **"What would make you say YES?"** — Pre-registered rule: ΔPass ≥ +5%
   **and** p < 0.05 on round 5 — decided before running, so the verdict cannot
   be moved.

## 8. Reference

- `docs/RUNS_SUMMARY.md` — full run-by-run dossier (implementation, metrics,
  differentiation).
- `docs/CASE2_PLAN.md` — Case 1 diagnosis + Case 2 plan/fix brief.
- `docs/CASE3_PLAN.md` — Case 3A implementation.
- `docs/CASE3B_PLAN.md` — Case 3B implementation + reviewer-fix log.