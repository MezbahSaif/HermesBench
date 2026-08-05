"""Benchmark orchestration: rounds x arms x tasks -> metrics.

Methodology (see README for the full rationale):
  * treatment arm: HERMES_HOME accumulates skills/memories/sessions across
    rounds -> the learning loop is allowed to persist.
  * control arm: HERMES_HOME is wiped and re-seeded before EVERY round ->
    no cross-round learning, same model, same tasks.
  * Fresh one-shot session per task (no conversational continuation), so any
    improvement must come from persistent learning artifacts, not context.
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from benchmark.graders import LLMJudge, grade
from benchmark.hermes_interface import HermesInterface
from benchmark.task_loader import Task, load_dataset_from_config

METRIC_COLUMNS = [
    "run_id", "round", "arm", "task_id", "family", "category", "status",
    "passed", "score", "score_detail", "threshold", "duration_s",
    "exit_code", "timed_out", "response_chars", "api_calls",
    "input_tokens", "output_tokens", "reasoning_tokens",
    "cache_read_tokens", "total_tokens", "session_id",
    "tool_call_log_events", "error_log_events", "retry_log_events",
    "reflection_log_events", "failed_request_dumps",
    "before_skill_files", "after_skill_files", "before_memory_files",
    "after_memory_files", "before_memory_bytes", "after_memory_bytes",
    "before_state_db_bytes", "after_state_db_bytes",
    "human_interventions",
    "completed_at",
]

# Columns that stay text; everything else is numeric and is coerced when
# loading existing metrics.csv rows so resumed runs keep proper dtypes
# (build_summary / verdict run .mean() over these).
_STRING_COLUMNS = {
    "run_id", "arm", "task_id", "family", "category", "status",
    "score_detail", "completed_at",
    "passed", "timed_out", "session_id",
}


def restore_workspace(task: Task) -> bool:
    """Restore the task workdir from its pristine snapshot, if one exists.

    The pristine snapshot lives at <dataset>/tasks/<task_id>/pristine and is
    created by the task generator (or via --refresh-pristine for hand-made
    datasets). Restoring before every execution guarantees every (round, arm)
    starts from identical, untouched fixtures: the agent's edits never leak
    into later rounds or across arms. Returns True when a restore happened.
    """
    pristine = task.workdir.parent / "pristine"
    if not pristine.is_dir():
        return False
    if task.workdir.exists():
        shutil.rmtree(task.workdir)
    shutil.copytree(pristine, task.workdir)
    return True


def snapshot_pristine(task: Task) -> bool:
    """Copy the current workdir into <task_id>/pristine (one-time setup for
    hand-authored datasets). Returns True when a snapshot was created."""
    if not task.workdir.is_dir():
        return False
    pristine = task.workdir.parent / "pristine"
    if pristine.is_dir():
        return False
    shutil.copytree(task.workdir, pristine)
    return True


class BenchmarkRunner:
    def __init__(self, config: dict, run_dir: Path, run_id: str,
                 arms: list[str], rounds: int, task_limit: int | None = None,
                 task_ids: list[str] | None = None,
                 categories: list[str] | None = None,
                 resume: bool = False, dry_run: bool = False,
                 round_no: int | None = None):
        self.config = config
        self.run_dir = run_dir
        self.run_id = run_id
        self.arms = arms
        self.rounds = rounds
        self.round_no = round_no  # run exactly this one round if given
        self.task_limit = task_limit
        self.task_ids = task_ids
        self.categories = categories
        self.resume = resume
        self.dry_run = dry_run
        self.pass_threshold = float(config["benchmark"].get("pass_threshold", 0.7))
        self.logger = print
        self._signals_warned = False

        self.artifacts_dir = run_dir / "artifacts"
        self.usage_dir = run_dir / "usage"
        self.homes_dir = run_dir / "homes"
        self.progress_file = run_dir / "progress.json"

        # Existing metrics (for --resume).
        self.metrics_path = run_dir / "metrics.csv"
        self.rows: list[dict] = []
        self.done: set[tuple[int, str, str]] = set()
        if resume and self.metrics_path.exists():
            old = pd.read_csv(self.metrics_path, dtype=str)
            for _, r in old.iterrows():
                self.done.add(
                    (int(float(r["round"])), r["arm"], r["task_id"])
                )
                row = r.to_dict()
                for col, val in row.items():
                    if col in _STRING_COLUMNS:
                        continue
                    row[col] = pd.to_numeric(val, errors="coerce")
                self.rows.append(row)
            self.logger(f"[resume] found {len(self.done)} completed task rows")

        # Load tasks once (applies limit / filters).
        self.tasks = load_dataset_from_config(config)
        if task_ids:
            self.tasks = [t for t in self.tasks if t.task_id in task_ids]
        if categories:
            self.tasks = [t for t in self.tasks if t.category in categories]
        if task_limit:
            self.tasks = self.tasks[:task_limit]
        if not self.tasks:
            raise ValueError("No tasks match the given filters")

        # LM Studio judge client (used only by llm_judge tasks).
        ls = config["lmstudio"]
        default_model = self._resolve_default_model()
        judge_model = ls.get("judge_model") or config["hermes"].get("model") \
            or default_model
        self.judge: LLMJudge | None = (
            LLMJudge(
                base_url=ls["base_url"],
                model=judge_model,
                api_key=ls.get("judge_api_key", "lm-studio"),
                timeout_s=float(ls.get("judge_timeout_s", 180)),
            )
            if judge_model
            else None
        )

    def _resolve_default_model(self) -> str:
        """Fall back to the default model in the user's real config.yaml."""
        try:
            import yaml
            real = Path(self.config["hermes"]["real_home"]) / "config.yaml"
            if real.exists():
                raw = yaml.safe_load(real.read_text(encoding="utf-8"))
                m = (raw or {}).get("model", {})
                return m.get("default") or m.get("model") or ""
        except Exception:
            pass
        return ""

    # ------------------------------------------------------------------ run
    def run(self) -> pd.DataFrame:
        start = time.time()
        self._prepare_dirs()
        interfaces = {
            arm: HermesInterface(
                self.config, self.homes_dir / f"{arm}_home",
                self.run_dir.parent.parent
            )
            for arm in self.arms
        }
        for arm in self.arms:
            interfaces[arm].seed_home()

        if self.dry_run:
            return self._dry_run_report(interfaces)

        self._write_progress("initializing", 0, 0, "")
        round_range = ([self.round_no] if self.round_no is not None
                       else range(1, self.rounds + 1))
        for round_no in round_range:
            for arm in self.arms:
                ifi = interfaces[arm]
                if arm == "control":
                    # Control: destroy and re-seed -> no learning persists.
                    ifi.reset_home()
                self._write_progress("round", round_no, 0, f"{arm} arm")
                self.logger(f"--- round {round_no}/{self.rounds} arm={arm} ---")
                for i, task in enumerate(self.tasks, start=1):
                    if (round_no, arm, task.task_id) in self.done:
                        self.logger(f"  skip (done): {task.task_id}")
                        continue
                    self._write_progress(
                        "task", round_no, i, f"{arm}:{task.task_id}"
                    )
                    try:
                        restored = restore_workspace(task)
                    except Exception as exc:
                        self.logger(
                            f"  [ws] restore FAILED for {task.task_id}: "
                            f"{exc!r}; skipping task to avoid cross-round "
                            "contamination"
                        )
                        row = {
                            "run_id": self.run_id,
                            "round": round_no,
                            "arm": arm,
                            "task_id": task.task_id,
                            "family": task.family,
                            "category": task.category,
                            "status": "skipped",
                            "passed": False,
                            "score": None,
                            "score_detail": f"restore-failed:{type(exc).__name__}",
                            "threshold": task.threshold,
                            "duration_s": 0.0,
                            "exit_code": None,
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
                            "human_interventions": 1,
                            "completed_at": datetime.now().isoformat(
                                timespec="seconds"
                            ),
                        }
                        self.rows.append(row)
                        self._flush_metrics()
                        continue
                    if restored and not self.dry_run:
                        self.logger(
                            f"  [ws] restored {task.task_id} from pristine"
                        )
                    try:
                        row = self._run_one(ifi, task, round_no, arm)
                    except Exception as exc:
                        self.logger(
                            f"  [run] execution FAILED for "
                            f"{task.task_id}: {exc!r}"
                        )
                        row = {
                            "run_id": self.run_id,
                            "round": round_no,
                            "arm": arm,
                            "task_id": task.task_id,
                            "family": task.family,
                            "category": task.category,
                            "status": "harness-error",
                            "passed": False,
                            "score": None,
                            "score_detail": f"harness-error:{type(exc).__name__}",
                            "threshold": task.threshold,
                            "duration_s": 0.0,
                            "exit_code": None,
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
                            "human_interventions": 1,
                            "completed_at": datetime.now().isoformat(
                                timespec="seconds"
                            ),
                        }
                    self.rows.append(row)
                    self._flush_metrics()
                    self.logger(
                        f"  [{i}/{len(self.tasks)}] {task.task_id}: "
                        f"status={row['status']} score={row['score']} "
                        f"dur={row['duration_s']:.1f}s"
                    )
        self._write_progress("done", self.rounds, len(self.tasks), "")
        self.logger(
            f"benchmark finished in {time.time() - start:.0f}s; "
            f"{len(self.rows)} task executions"
        )
        return self._finalize()

    def _prepare_dirs(self) -> None:
        for d in (self.artifacts_dir, self.usage_dir, self.homes_dir):
            d.mkdir(parents=True, exist_ok=True)
        # Don't wipe run_dir contents on --resume.
        if not self.resume and self.metrics_path.exists():
            self.metrics_path.unlink()

    # -------------------------------------------------------------- one task
    def _run_one(self, ifi: HermesInterface, task: Task, round_no: int,
                 arm: str) -> dict:
        usage_path = self.usage_dir / f"r{round_no}_{arm}_{task.task_id}.json"
        response_path = self.artifacts_dir / f"r{round_no}_{arm}_{task.task_id}.txt"

        before = ifi.learning_state()
        start_dt = datetime.now()
        result = ifi.run_task(task, usage_path)
        end_dt = datetime.now()
        after = ifi.learning_state()
        signals = ifi.log_signals(start_dt, end_dt)
        if (not self._signals_warned and result.exit_code == 0
                and signals.tool_calls == 0 and signals.errors == 0
                and signals.retries == 0 and signals.reflections == 0):
            self._signals_warned = True
            self.logger(
                "[signals] WARNING: agent.log shows no tool/error/retry/"
                "reflection lines for this task. Hermes disables stdlib "
                "logging during one-shot (-z) runs, so the *_log_events "
                "metrics will stay 0 for the whole run - treat them as "
                "unavailable, not as evidence of zero activity. (api_calls "
                "from the usage file remains reliable.)"
            )

        response_path.write_text(result.response or "", encoding="utf-8")

        status = "ok"
        if result.timed_out:
            status = "timeout"
        elif result.crashed:
            status = "crashed"
        elif result.exit_code != 0:
            status = "failed"

        if status == "ok" and result.response.strip():
            try:
                score, detail = grade(task, result.response, self.judge)
            except Exception as exc:
                self.logger(
                    f"  [grade] error grading {task.task_id}: {exc!r}"
                )
                score, detail = None, f"grader-error:{type(exc).__name__}"
        else:
            score, detail = None, status

        passed = bool(
            score is not None and score >= task.threshold
        ) if score is not None else False

        usage = result.usage
        row = {
            "run_id": self.run_id,
            "round": round_no,
            "arm": arm,
            "task_id": task.task_id,
            "family": task.family,
            "category": task.category,
            "status": status,
            "passed": passed,
            "score": score,
            "score_detail": detail,
            "threshold": task.threshold,
            "duration_s": round(result.duration_s, 3),
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "response_chars": len(result.response),
            "api_calls": usage.get("api_calls"),
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "reasoning_tokens": usage.get("reasoning_tokens"),
            "cache_read_tokens": usage.get("cache_read_tokens"),
            "total_tokens": usage.get("total_tokens"),
            "session_id": result.session_id,
            "tool_call_log_events": signals.tool_calls,
            "error_log_events": signals.errors,
            "retry_log_events": signals.retries,
            "reflection_log_events": signals.reflections,
            "failed_request_dumps": signals.failed_request_dumps,
            "before_skill_files": before.skill_files,
            "after_skill_files": after.skill_files,
            "before_memory_files": before.memory_files,
            "after_memory_files": after.memory_files,
            "before_memory_bytes": before.memory_bytes,
            "after_memory_bytes": after.memory_bytes,
            "before_state_db_bytes": before.state_db_bytes,
            "after_state_db_bytes": after.state_db_bytes,
            # Human intervention = the operator/harness had to act on this
            # task (timeout kill, crash, or failed exit). Headless one-shot
            # auto-approves tool prompts, so this counts manual attention.
            "human_interventions": 0 if status == "ok" else 1,
            "completed_at": datetime.now().isoformat(timespec="seconds"),
        }
        return row

    # ---------------------------------------------------------------- utils
    def _flush_metrics(self) -> pd.DataFrame:
        df = pd.DataFrame(self.rows, columns=METRIC_COLUMNS)
        # Resumed rows arrive as "True"/"False" strings (kept by
        # _STRING_COLUMNS); normalize to real booleans so the CSV round-trips
        # and the end-of-run analysis (build_summary/verdict .mean()) sees
        # proper bools instead of truthy strings.
        for col in ("passed", "timed_out"):
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip().str.lower().isin(
                    ("true", "1")
                )
        df.to_csv(self.metrics_path, index=False)
        return df

    def _write_progress(self, phase: str, round_no: int, task_i: int,
                        detail: str) -> None:
        payload = {
            "run_id": self.run_id,
            "phase": phase,
            "round": round_no,
            "rounds": self.rounds,
            "task_index": task_i,
            "total_tasks": len(self.tasks),
            "detail": detail,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.progress_file.write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )

    def _finalize(self) -> pd.DataFrame:
        df = self._flush_metrics()
        try:
            from analysis.metrics_engine import generate_outputs
            res = generate_outputs(df, self.run_dir, quiet=True)
            self.logger(
                f"metrics engine: csv={res['metrics_csv']} "
                f"xlsx={res['xlsx']} plots={len(res['plots'])}"
            )
            if res["verdict"]["supported_metrics"]:
                self.logger(
                    "VERDICT: claim supported for "
                    f"{', '.join(res['verdict']['supported_metrics'])}"
                )
            else:
                self.logger("VERDICT: claim not supported (yet)")
        except Exception as exc:
            self.logger(f"metrics engine skipped: {exc}")
        return df

    @staticmethod
    def summary_table(df: pd.DataFrame) -> pd.DataFrame:
        from analysis.metrics_engine import build_summary
        return build_summary(df)

    # ------------------------------------------------------------ dry run
    def _dry_run_report(self, interfaces: dict[str, HermesInterface]) -> pd.DataFrame:
        print("=" * 60)
        print("HERMESBENCH DRY RUN (no agent executions)")
        print("=" * 60)
        print(f"hermes executable : {interfaces[self.arms[0]].exe}")
        print(f"  exists          : {interfaces[self.arms[0]].exe.exists()}")
        home = interfaces[self.arms[0]].real_home
        print(f"real hermes home  : {home} (exists={home.exists()})")
        for arm in self.arms:
            h = interfaces[arm].home_dir
            print(f"arm home ({arm}) : {h} (seeded={h.exists()})")
        print(f"tasks loaded      : {len(self.tasks)}")
        for t in self.tasks:
            wd = t.workdir
            print(
                f"  {t.task_id:<22} {t.category:<10} {t.check_type:<16} "
                f"workdir={'ok' if wd.exists() else 'MISSING'}"
            )
        if self.judge is not None:
            print(f"judge model       : {self.judge.model} "
                  f"(server reachable={self.judge.available()})")
        else:
            print("judge model       : DISABLED (llm_judge tasks will score None)")
        print("=" * 60)
        print("start LM Studio, load the model, then run without --dry-run")
        return pd.DataFrame()
