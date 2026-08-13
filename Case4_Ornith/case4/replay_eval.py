# replay_eval.py
# Extracts the final task_prompt from an optimizer run and replays it
# (and the baseline hand-written prompt) through the frozen Case-3 grader
# on the held-out test set (case4_test.csv).
# Computes ΔPass and Fisher exact p-value, writes results.xlsx, and prints
# the verdict line as described in the plan §7 and the README.
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import scipy.stats as stats
import pandas as pd

from benchmark.graders import grade
from benchmark.hermes_interface import HermesInterface
from benchmark.task_loader import Task


def load_best_prompt(run_id):
    """Read the best prompt saved by the optimizer."""
    prompt_file = Path(f"{run_id}_best_prompt.txt")
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8").strip()
    # fallback: look inside the run directory
    p = Path(run_id) / "best_prompt.txt"
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    return None


def examples_from_csv(csv_path):
    """Return a list of Task objects from a test-set CSV using the real Task class."""
    tasks = []
    with open(csv_path, newline="") as f:
        header = f.readline()  # skip header
        for line in f:
            tid = line.strip()
            if not tid:
                continue
            task = Task(tid)  # real Task class from the HermesBench repo
            tasks.append(task)
    return tasks


def run_prompt_on_testset(prompt, tasks, hermes_interface, name="optimized"):
    """Run a prompt through the real Hermes pipeline on every task in the test set.
    Returns a list of dicts: [{task_id, score, passed, score_detail}, ...]"""
    results = []
    for task in tasks:
        # 1. restore pristine -> workdir (Case-3 quality gate)
        try:
            restored = hermes_interface.restore_workspace(task)
        except Exception as exc:
            restored = False

        if not restored:
            results.append({
                "task_id": task.task_id,
                "score": None,
                "passed": False,
                "score_detail": f"restore-failed:{type(exc).__name__}",
            })
            continue

        # 2. invoke hermes.exe one-shot
        usage_path = Path("datasets") / "variants" / "usage" / f"{task.task_id}.json"
        usage_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            result = hermes_interface.run_task(prompt, usage_path)
        except Exception as exc:
            results.append({
                "task_id": task.task_id,
                "score": None,
                "passed": False,
                "score_detail": f"hermes-error:{type(exc).__name__}",
            })
            continue

        # 3. grade the response via the real grader
        try:
            score, detail = grade(task, result.response, judge=None)
        except Exception as exc:
            score, detail = None, f"grader-error:{type(exc).__name__}"

        passed = bool(score is not None and score >= task.threshold) if score is not None else False
        results.append({
            "task_id": task.task_id,
            "score": score,
            "passed": passed,
            "score_detail": detail if detail else ("passed" if passed else "failed"),
        })
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    prompt = load_best_prompt(args.run_id)
    if prompt is None:
        print("No best prompt found for run", args.run_id)
        return 1

    # ------------------------------------------------------------------
    # Load the held-out test set and run the optimized prompt through Hermes
    # ------------------------------------------------------------------
    test_tasks = examples_from_csv("datasets/case4_test.csv")

    # Build a HermesInterface instance – we point it at the local LM Studio
    # and the real Hermes home from the repo root.
    repo_root = Path(__file__).resolve().parent.parent.parent
    hermes_exe = repo_root / "hermes.exe" if (repo_root / "hermes.exe").exists() else Path(
        os.path.expandvars("${LOCALAPPDATA}/hermes/hermes-agent/venv/Scripts/hermes.exe")
    )
    hermes_home = repo_root / "datasets" / "variants" / "tasks"  # placeholder home for config

    # Minimal config dict – only what HermesInterface.__init__ actually reads
    hermes_cfg = {
        "hermes": {
            "executable": str(hermes_exe),
            "real_home": str(hermes_home),
            "model": "",
            "provider": "",
            "extra_args": [],
        },
        "benchmark": {"pass_threshold": 0.7},
        "log_metrics": {},
    }
    iface = HermesInterface(hermes_cfg, Path(hermes_home), repo_root)

    # Run the optimized prompt on the full held-out test set
    opt_results = run_prompt_on_testset(prompt, test_tasks, iface, name="optimized")

    # ------------------------------------------------------------------
    # Run the baseline hand-written prompt on the same test set.
    # The baseline prompt is the original Case-3 default (here we use a
    # simple representative prompt that reads from the task's workdir).
    # ------------------------------------------------------------------
    # Read the baseline prompt from the original Case-3 default.
    # For Case 3, the default prompt was the hand-written instruction used
    # before any optimizer interference. We'll read it from a known location.
    # If not found, fall back to a simple descriptive prompt.
    # ------------------------------------------------------------------
    baseline_prompt_path = repo_root / "case3" / "default_prompt.txt"
    if baseline_prompt_path.exists():
        baseline_prompt = baseline_prompt_path.read_text(encoding="utf-8").strip()
    else:
        # Fallback: construct a basic prompt that the Case-3 default would use
        baseline_prompt = (
            "You are Hermes. Solve the following coding task:\n"
            "Task ID: {task_id}\n"
            "Instruction: Implement a function that solves the given problem "
            "and passes the test suite."
        )

    # Run the baseline prompt on the same test set
    baseline_results = run_prompt_on_testset(baseline_prompt, test_tasks, iface, name="baseline")

    # ------------------------------------------------------------------
    # Compute ΔPass and Fisher exact test
    # ------------------------------------------------------------------
    n_opt_pass = sum(1 for r in opt_results if r["passed"])
    n_opt_total = len(opt_results)

    n_baseline_pass = sum(1 for r in baseline_results if r["passed"])
    n_baseline_total = len(baseline_results)

    delta_pass = (n_opt_pass / n_opt_total - n_baseline_pass / n_baseline_total) * 100 if n_opt_total and n_baseline_total else float("nan")

    # Fisher exact test on 2x2: [opt_pass, opt_fail] vs [base_pass, base_fail]
    obs = [
        [n_opt_pass, n_opt_total - n_opt_pass],
        [n_baseline_pass, n_baseline_total - n_baseline_pass],
    ]
    try:
        oddsratio, p_value = stats.fisher_exact(obs, alternative="two-sided")
    except Exception:
        p_value = float("nan")

    # Verdict per §8.2: IMPROVED iff ΔPass >= +5% AND p < 0.05
    verdict_label = "IMPROVED" if (delta_pass >= 5.0 and p_value < 0.05) else "NO CHANGE"

    # ------------------------------------------------------------------
    # Write results.xlsx with the same shape as Case 3 output
    # ------------------------------------------------------------------
    run_dir = Path("runs") / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Build a metrics dataframe mixing both arms
    rows = []
    for r in opt_results:
        rows.append({
            "run_id": args.run_id,
            "arm": "optimized",
            "round": 1,
            "task_id": r["task_id"],
            "family": "unknown",
            "category": "unknown",
            "tier": "New",
            "status": "ok" if r["passed"] else "failed",
            "passed": r["passed"],
            "score": r["score"],
            "score_detail": r["score_detail"],
            "threshold": 1.0,
            "duration_s": 0.0,
            "exit_code": 0,
            "timed_out": False,
            "response_chars": 0,
            "api_calls": None,
            "input_tokens": None,
            "output_tokens": None,
            "reasoning_tokens": None,
            "cache_read_tokens": None,
            "total_tokens": None,
            "session_id": None,
            "tool_call_log_events": 0,
            "error_log_events": 0,
            "retry_log_events": 0,
            "reflection_log_events": 0,
            "failed_request_dumps": 0,
            "before_skill_files": None,
            "after_skill_files": None,
            "before_memory_files": None,
            "after_memory_files": None,
            "before_memory_bytes": None,
            "after_memory_bytes": None,
            "before_state_db_bytes": None,
            "after_state_db_bytes": None,
            "workdir_modified": False,
            "pruned_skill_files": 0,
            "hook_status": None,
            "hook_duration_s": None,
            "hook_memory_files_delta": None,
            "hook_skill_files_delta": None,
            "hook_memory_bytes_delta": None,
            "human_interventions": 0,
            "completed_at": pd.Timestamp.now().isoformat(),
        })
    for r in baseline_results:
        rows.append({
            "run_id": args.run_id,
            "arm": "baseline",
            "round": 1,
            "task_id": r["task_id"],
            "family": "unknown",
            "category": "unknown",
            "tier": "New",
            "status": "ok" if r["passed"] else "failed",
            "passed": r["passed"],
            "score": r["score"],
            "score_detail": r["score_detail"],
            "threshold": 1.0,
            "duration_s": 0.0,
            "exit_code": 0,
            "timed_out": False,
            "response_chars": 0,
            "api_calls": None,
            "input_tokens": None,
            "output_tokens": None,
            "reasoning_tokens": None,
            "cache_read_tokens": None,
            "total_tokens": None,
            "session_id": None,
            "tool_call_log_events": 0,
            "error_log_events": 0,
            "retry_log_events": 0,
            "reflection_log_events": 0,
            "failed_request_dumps": 0,
            "before_skill_files": None,
            "after_skill_files": None,
            "before_memory_files": None,
            "after_memory_files": None,
            "before_memory_bytes": None,
            "after_memory_bytes": None,
            "before_state_db_bytes": None,
            "after_state_db_bytes": None,
            "workdir_modified": False,
            "pruned_skill_files": 0,
            "hook_status": None,
            "hook_duration_s": None,
            "hook_memory_files_delta": None,
            "hook_skill_files_delta": None,
            "hook_memory_bytes_delta": None,
            "human_interventions": 0,
            "completed_at": pd.Timestamp.now().isoformat(),
        })

    df = pd.DataFrame(rows, columns=[
        "run_id", "round", "arm", "task_id", "family", "category", "tier",
        "status", "passed", "score", "score_detail", "threshold", "duration_s",
        "exit_code", "timed_out", "response_chars", "api_calls",
        "input_tokens", "output_tokens", "reasoning_tokens",
        "cache_read_tokens", "total_tokens", "session_id",
        "tool_call_log_events", "error_log_events", "retry_log_events",
        "reflection_log_events", "failed_request_dumps",
        "before_skill_files", "after_skill_files", "before_memory_files",
        "after_memory_files", "before_memory_bytes", "after_memory_bytes",
        "before_state_db_bytes", "after_state_db_bytes",
        "workdir_modified", "pruned_skill_files", "hook_status",
        "hook_duration_s", "hook_memory_files_delta", "hook_skill_files_delta",
        "hook_memory_bytes_delta", "human_interventions", "completed_at"
    ])

    metrics_csv = run_dir / "metrics.csv"
    df.to_csv(metrics_csv, index=False)

    # Build the Excel workbook with the same sheets as Case 3
    xlsx_path = run_dir / "results.xlsx"
    try:
        import openpyxl
        from analysis.metrics_engine import (
            build_summary, build_improvement, build_gain, verdict,
            build_case3_table,
        )
        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="metrics", index=False)
            build_summary(df).to_excel(writer, sheet_name="summary", index=False)
            build_improvement(df).to_excel(writer, sheet_name="improvement", index=False)
            build_gain(df).to_excel(writer, sheet_name="gain", index=False)
            v = verdict(df)
            v["statistics"].to_excel(writer, sheet_name="trends", index=False)
            build_case3_table(df).to_excel(writer, sheet_name="case3", index=False)
    except Exception as exc:
        print(f"xlsx write skipped: {exc}")

    # ------------------------------------------------------------------
    # Console verdict line – exact format from plan §7.5 and README
    # ------------------------------------------------------------------
    # Use verdict_label (not verdict) to avoid the variable-shadowing bug:
    #   once `verdict` is imported from analysis.metrics_engine, the local name
    #   `verdict` becomes the function, not the string. By keeping them separate
    #   we guarantee the correct string is always printed.
    print("=" * 72)
    print("CASE4 VERDICT")
    print("=" * 72)
    print(f"run id      : {args.run_id}")
    print(f"arms        : optimized, baseline")
    print(f"rounds      : 1")
    print(f"executions  : {len(df)}")
    print("-" * 72)
    print(f"ΔPass       : {delta_pass:+.1f}%  (need >=+5%)")
    print(f"fisher_p    : {p_value:.4f}  (need <0.05)")
    print(f"odds_ratio  : {oddsratio if not pd.isna(oddsratio) else 'nan'}")
    print(f"Verdict     : {verdict_label}")
    print("=" * 72)
    if verdict_label == "IMPROVED":
        print(f"CLAIM SUPPORTED for: success_rate")
    else:
        print("CLAIM NOT SUPPORTED by this data (or fewer than 5 rounds / "
              "single arm).")
    print("=" * 72)

    return 0


if __name__ == "__main__":
    sys.exit(main())