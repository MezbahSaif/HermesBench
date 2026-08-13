# replay_eval.py
import argparse
import sys
from pathlib import Path
import scipy.stats as stats
import pandas as pd

def get_repo_root():
    current = Path(__file__).resolve()
    for p in [current] + list(current.parents):
        if (p / "benchmark").is_dir() and (p / "datasets").is_dir():
            return p
    return current.parent.parent

repo_root = get_repo_root()
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from benchmark.graders import grade
from benchmark.hermes_interface import HermesInterface
from benchmark.infrastructure_recovery import restore_workspace
from benchmark.task_loader import Task


def load_best_prompt(run_id):
    prompt_file = Path(f"{run_id}_best_prompt.txt")
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8").strip()
    p = Path(run_id) / "best_prompt.txt"
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    return None


def examples_from_csv(csv_path):
    tasks = []
    with open(csv_path, newline="") as f:
        f.readline()
        for line in f:
            tid = line.strip()
            if tid:
                workdir = repo_root / "datasets" / "variants" / "tasks" / tid / "work"
                try:
                    task = Task(tid)
                    if hasattr(task, 'threshold'):
                        task.threshold = 0.7
                except TypeError:
                    task = Task(task_id=tid, category="unknown", prompt="", check_type="pass", 
                                expected="", threshold=0.7, rubric="", workdir=workdir)
                tasks.append(task)
    return tasks


def run_prompt_on_testset(prompt_template, tasks, hermes_interface):
    results = []
    for task in tasks:
        try:
            restored = restore_workspace(task)
        except Exception as exc:
            restored = False

        if not restored:
            results.append({"task_id": task.task_id, "score": None, "passed": False, "score_detail": "restore-failed"})
            continue

        workdir = repo_root / "datasets" / "variants" / "tasks" / task.task_id / "work"
        prompt_text = ""
        for possible in ["problem.json", "task.json", "prompt.json",
                         "problem.txt", "task.txt", "prompt.txt",
                         "problem.md", "task.md", "prompt.md"]:
            p = workdir / possible
            if p.is_file():
                try:
                    prompt_text = p.read_text(encoding="utf-8")[:500]
                    break
                except Exception:
                    continue
        if not prompt_text.strip():
            prompt_text = "Implement a solution for the given coding task."

        rendered_prompt = prompt_template.replace("{task_id}", task.task_id).replace("{prompt}", prompt_text)

        usage_path = repo_root / "datasets" / "variants" / "usage" / f"{task.task_id}.json"
        usage_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            result = hermes_interface.run_task(rendered_prompt, usage_path)
        except Exception as exc:
            results.append({"task_id": task.task_id, "score": None, "passed": False, "score_detail": "hermes-error"})
            continue

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
    parser.add_argument("--prompt-source", required=True, choices=["gepa", "mipro"])
    args = parser.parse_args()

    prompt = load_best_prompt(args.run_id)
    if prompt is None:
        print("No best prompt found for run", args.run_id)
        return 1

    test_tasks = examples_from_csv(repo_root / "datasets" / "case4_test.csv")
    
    hermes_exe = repo_root / "hermes.exe" if (repo_root / "hermes.exe").exists() else Path(sys.executable).parent / "hermes.exe"
    hermes_home = repo_root / "datasets" / "variants" / "tasks"

    hermes_cfg = {
        "hermes": {"executable": str(hermes_exe), "real_home": str(hermes_home), "model": "", "provider": "", "extra_args": []},
        "benchmark": {"pass_threshold": 0.7},
        "log_metrics": {},
    }
    iface = HermesInterface(hermes_cfg, Path(hermes_home), repo_root)

    opt_results = run_prompt_on_testset(prompt, test_tasks, iface)

    baseline_prompt_path = repo_root / "case3" / "default_prompt.txt"
    if baseline_prompt_path.exists():
        baseline_prompt = baseline_prompt_path.read_text(encoding="utf-8").strip()
    else:
        baseline_prompt = "You are Hermes. Solve the following coding task:\nTask ID: {task_id}\nInstruction: {prompt}"
    
    baseline_results = run_prompt_on_testset(baseline_prompt, test_tasks, iface)

    n_opt_pass = sum(1 for r in opt_results if r["passed"])
    n_opt_total = len(opt_results)
    n_baseline_pass = sum(1 for r in baseline_results if r["passed"])
    n_baseline_total = len(baseline_results)

    delta_pass = (n_opt_pass / n_opt_total - n_baseline_pass / n_baseline_total) * 100 if n_opt_total and n_baseline_total else float("nan")

    obs = [[n_opt_pass, n_opt_total - n_opt_pass], [n_baseline_pass, n_baseline_total - n_baseline_pass]]
    try:
        result = stats.fisher_exact(obs, alternative="two-sided")
        if isinstance(result, tuple):
            oddsratio, p_value = result[0], result[1]
        else:
            oddsratio, p_value = result.oddsratio, result.pvalue
    except Exception:
        p_value = float("nan")
        oddsratio = float("nan")

    verdict_label = "IMPROVED" if (delta_pass >= 5.0 and (isinstance(p_value, float) and not pd.isna(p_value) and p_value < 0.05)) else "NO CHANGE" 

    run_dir = Path("runs") / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for arms_list, arm_label in [(opt_results, "optimized"), (baseline_results, "baseline")]:
        for r in arms_list:
            rows.append({
                "run_id": args.run_id, "arm": arm_label, "round": 1, "task_id": r["task_id"],
                "family": "unknown", "category": "unknown", "tier": "New",
                "status": "ok" if r["passed"] else "failed", "passed": r["passed"],
                "score": r["score"], "score_detail": r["score_detail"], "threshold": 1.0,
                "duration_s": 0.0, "exit_code": 0, "timed_out": False, "response_chars": 0,
                "api_calls": None, "input_tokens": None, "output_tokens": None,
                "reasoning_tokens": None, "cache_read_tokens": None, "total_tokens": None,
                "session_id": None, "tool_call_log_events": 0, "error_log_events": 0,
                "retry_log_events": 0, "reflection_log_events": 0, "failed_request_dumps": 0,
                "before_skill_files": None, "after_skill_files": None, "before_memory_files": None,
                "after_memory_files": None, "before_memory_bytes": None, "after_memory_bytes": None,
                "before_state_db_bytes": None, "after_state_db_bytes": None, "workdir_modified": False,
                "pruned_skill_files": 0, "hook_status": None, "hook_duration_s": None,
                "hook_memory_files_delta": None, "hook_skill_files_delta": None,
                "hook_memory_bytes_delta": None, "human_interventions": 0,
                "completed_at": pd.Timestamp.now().isoformat(),
            })

    df = pd.DataFrame(rows)
    df.to_csv(run_dir / "metrics.csv", index=False)

    try:
        try:
            from analysis.metrics_engine import build_summary, build_improvement, build_gain, verdict, build_case3_table  # type: ignore
        except (ImportError, ModuleNotFoundError) as e:
            print("analysis.metrics_engine not available, skipping xlsx generation")
            return 0
        
        with pd.ExcelWriter(run_dir / "results.xlsx", engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="metrics", index=False)
            build_summary(df).to_excel(writer, sheet_name="summary", index=False)
            build_improvement(df).to_excel(writer, sheet_name="improvement", index=False)
            build_gain(df).to_excel(writer, sheet_name="gain", index=False)
            verdict(df)["statistics"].to_excel(writer, sheet_name="trends", index=False)
            build_case3_table(df).to_excel(writer, sheet_name="case3", index=False)
    except Exception as exc:
        print(f"xlsx write skipped: {exc}")

    print("=" * 72)
    print("CASE4 VERDICT")
    print("=" * 72)
    print(f"run id      : {args.run_id}")
    print(f"prompt src  : {args.prompt_source}")
    print(f"arms        : optimized, baseline")
    print(f"rounds      : 1")
    print(f"executions  : {len(df)}")
    print("-" * 72)
    print(f"ΔPass       : {delta_pass:+.1f}%  (need >=+5%)")
    print(f"fisher_p    : {p_value:.4f}  (need <0.05)")
    print(f"odds_ratio  : {oddsratio if isinstance(oddsratio, float) and not pd.isna(oddsratio) else 'nan'}")
    print(f"Verdict     : {verdict_label}")
    print("=" * 72)

    return 0

if __name__ == "__main__":
    sys.exit(main())