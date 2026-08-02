import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark.task_loader import load_tasks

rounds = {}
for r in range(1, 6):
    tasks = load_tasks(Path(f"datasets/variants/round_{r}_se.csv"))
    rounds[r] = tasks

unique = {}
for tasks in rounds.values():
    for t in tasks:
        if t.task_id not in unique:
            unique[t.task_id] = t

family_desc = {
    "bug_fix": "Find and fix a seeded bug in a working module (`main.py`). Graded by hidden `check()` assertions running against the fixed module.",
    "implement_function": "Implement a well-known algorithm from a stub (`solution.py` with `raise NotImplementedError`). Graded by hidden `check()` assertions.",
    "refactor": "Clean up working but ugly code (`ugly.py`): remove `global`, deduplicate, keep the same API. Graded by hidden `check()` assertions (behavior must be unchanged).",
    "write_tests": "Write unit tests that pass on `good.py` AND catch the seeded bug in `buggy.py`. Graded by running the tests against both modules in a subprocess.",
    "fastapi_setup": "Build a FastAPI app (`app.py`) from a README spec. Graded by required elements present in the files.",
    "docker_configure": "Write `Dockerfile` + `docker-compose.yml` for a given project. Graded by required directives present in the files.",
    "cli_tool": "Build a CLI tool (`cli.py`) matching a README spec exactly. Graded by RUNNING the CLI and comparing stdout line-by-line.",
}
fams = ["bug_fix", "implement_function", "refactor", "write_tests", "fastapi_setup", "docker_configure", "cli_tool"]

out = []
out.append("# HermesBench \u2014 Software Engineering Task Overview (Rounds 1\u20135)\n")
out.append("The benchmark runs 5 rounds \u00d7 14 tasks \u00d7 2 arms = **140 agent executions**. Each round runs the same 14-task battery again; the **only** difference between rounds is what the agent remembers (treatment arm) vs. forgets (control arm).\n")
out.append("## The 7 task families\n")
out.append("| Family | What the agent must do |")
out.append("|---|---|")
for fam in fams:
    out.append(f"| `{fam}` | {family_desc[fam]} |")
out.append("")
out.append("Each task is fully self-contained: the prompt the agent receives **is** the whole task description shown in the second section of this file.\n")
out.append("## Rounds at a glance (task_ids per round)\n")
for r in range(1, 6):
    out.append(f"### Round {r}")
    out.append("| # | Task ID | Family |")
    out.append("|---|---|---|")
    for i, t in enumerate(rounds[r], 1):
        out.append(f"| {i} | `{t.task_id}` | {t.family} |")
    out.append("")
out.append("## Full task prompts (verbatim, one per unique task)\n")
out.append("Repeated task_ids in later rounds reuse the **exact same prompt** \u2014 the full text is shown once here.\n")
for fam in fams:
    items = sorted((t for t in unique.values() if t.family == fam), key=lambda t: t.task_id)
    if not items:
        continue
    out.append(f"### {fam} ({len(items)} unique tasks)\n")
    for t in items:
        out.append(f"#### `{t.task_id}` \u2014 {t.category}")
        out.append("````text")
        out.append(t.prompt)
        out.append("````")
        out.append("")
out.append("---\n")
out.append("## Who decides right or wrong? \u2014 the deterministic grader (no AI)\n")
out.append("**A plain Python program decides \u2014 never the model, never you.** Each task has a hidden test set (the `expected` column in the CSV, which the agent never sees), and the grader executes it:\n")
out.append("- **bug_fix / implement / refactor** \u2014 the grader loads the agent's edited file as a module and runs 5\u20138 hidden assertions, e.g. `knapsack(10, [5,4,6,3], [10,40,30,50]) == 90`. Score = passed \u00f7 total.\n")
out.append("- **write_tests** \u2014 runs the agent's tests in a subprocess against the *correct* module (must pass) and the *buggy* one (must catch the bug).\n")
out.append("- **cli_tool** \u2014 actually executes `python cli.py --input ...` and compares stdout lines to the expected output.\n")
out.append("- **fastapi / docker** \u2014 reads the produced files and checks the required elements are present.\n")
out.append("")
out.append("Score \u2265 0.7 \u2192 **task passed**. The SE dataset contains zero `llm_judge` tasks, so no LLM is involved in grading: the same input always produces the same score.\n")
Path("TASKS_OVERVIEW.md").write_text("\n".join(out), encoding="utf-8")
print(f"written: {len(out)} lines, {len(unique)} unique tasks")
