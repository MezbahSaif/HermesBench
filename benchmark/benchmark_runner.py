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
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from benchmark.graders import LLMJudge, grade
from benchmark.hermes_interface import (
    HermesInterface,
    _outcome_summary,
    verify_workdir_modified,
    prune_failing_skills,
)
from benchmark.infrastructure_recovery import (
    _remove_windows_reserved_files,
    _agent_orphans,
    _ancestor_pids,
    _process_table,
    kill_agent_orphans,
    restore_workspace,
    safe_restore_workspace,
    snapshot_pristine,
)
from benchmark.task_loader import Task, load_dataset_from_config

METRIC_COLUMNS = [
    "run_id", "round", "arm", "task_id", "family", "category", "tier",
    "status",
    "passed", "score", "score_detail", "threshold", "duration_s",
    "exit_code", "timed_out", "response_chars", "api_calls",
    "input_tokens", "output_tokens", "reasoning_tokens",
    "cache_read_tokens", "total_tokens", "session_id",
    "tool_call_log_events", "error_log_events", "retry_log_events",
    "reflection_log_events", "failed_request_dumps",
    "before_skill_files", "after_skill_files", "before_memory_files",
    "after_memory_files", "before_memory_bytes", "after_memory_bytes",
    "before_state_db_bytes", "after_state_db_bytes",
    # Case-3 quality-gated learning loop:
    #   workdir_modified         target-diff gate result (bool)
    #   pruned_skill_files       skills deleted because they were used during
    #                            a failing task (pruner, spec §4.3)
    "workdir_modified", "pruned_skill_files",
    # Post-task learning hook (treatment arm): a directed `hermes -z` session
    # that makes the agent persist lessons via Hermes's own memory/skill tools.
    "hook_status", "hook_duration_s", "hook_memory_files_delta",
    "hook_skill_files_delta", "hook_memory_bytes_delta",
    "human_interventions",
    "completed_at",
]

# Columns that stay text; everything else is numeric and is coerced when
# loading existing metrics.csv rows so resumed runs keep proper dtypes
# (build_summary / verdict run .mean() over these).
_STRING_COLUMNS = {
    "run_id", "arm", "task_id", "family", "category", "tier",
    "status",
    "score_detail", "completed_at",
    "passed", "timed_out", "session_id",
    "hook_status",
    "workdir_modified",
}


# ---------------------------------------------------------------------------
# Windows recovery routines (_remove_windows_reserved_files, restore_workspace,
# kill_agent_orphans, etc.) live in benchmark.infrastructure_recovery and are
# re-exported above for back-compat with the CLI and selftests.
# ---------------------------------------------------------------------------
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
        self.learning_hook = bool(config.get("learning_hook", {}).get(
            "enabled", True
        ))
        self.hook_arm = config.get("learning_hook", {}).get("arm", "treatment")
        # Tiers the hook must NOT touch. New is the specificity control: if
        # the hook practiced it, cli_tool/docker_configure would get 4-5
        # deliberate "practice" sessions across rounds and New would stop
        # being a no-learning baseline. Only Repeat/Variant may be hooked.
        self.hook_exclude_tiers = set(config.get("learning_hook", {}).get(
            "exclude_tiers", []
        ))
        # Case-3 quality-gated learning loop (spec §4):
        #   require_workdir_diff -> hook only when the agent modified work/
        #   hook_min_score       -> hook only perfect solutions (1.0)
        #   prune_failing_skills -> delete skills used during failing tasks
        c3 = config.get("case3", {})
        self.case3_enabled = bool(c3.get("enabled", True))
        self.require_workdir_diff = bool(c3.get("require_workdir_diff", True))
        self.hook_min_score = float(c3.get("hook_min_score", 1.0))
        self.prune_failing_skills = bool(c3.get("prune_failing_skills", True))

        self.artifacts_dir = run_dir / "artifacts"
        self.usage_dir = run_dir / "usage"
        self.homes_dir = run_dir / "homes"
        self.progress_file = run_dir / "progress.json"

        # Existing metrics (for --resume).
        self.metrics_path = run_dir / "metrics.csv"
        self.rows: list[dict] = []
        self.done: set[tuple[int, str, str]] = set()
        # Per-round dataset order (round -> {task_id: index}). One round's CSV
        # must never re-index another round's rows: fastapi_catalog etc.
        # appear in several CSVs at different positions, so a single global
        # order would scramble old rounds on resume.
        self.round_order: dict[int, dict[str, int]] = {}
        # Statuses that mean "no valid attempt happened": on resume these are
        # re-run (the old row is replaced in place), not treated as done.
        retryable_statuses = {"timeout", "skipped", "harness-error"}
        if resume and self.metrics_path.exists():
            old = pd.read_csv(self.metrics_path, dtype=str)
            n_retry = 0
            for _, r in old.iterrows():
                status = str(r.get("status", "")).strip()
                if status in retryable_statuses:
                    n_retry += 1
                else:
                    self.done.add(
                        (int(float(r["round"])), r["arm"], r["task_id"])
                    )
                row = r.to_dict()
                for col, val in row.items():
                    if col in _STRING_COLUMNS:
                        continue
                    row[col] = pd.to_numeric(val, errors="coerce")
                self.rows.append(row)
                # Preserve whatever per-round dataset order the file already
                # had for these rows; the current round's CSV only re-indexes
                # rows of the CURRENT round.
                rd = int(float(row["round"]))
                order_map = self.round_order.setdefault(rd, {})
                if row["task_id"] not in order_map:
                    order_map[row["task_id"]] = len(order_map)
            self.logger(f"[resume] found {len(self.done)} completed task rows")
            if n_retry:
                self.logger(
                    f"[resume] {n_retry} row(s) with retryable status "
                    f"({', '.join(sorted(retryable_statuses))}) will be "
                    "re-run and replaced in place"
                )

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
        # Dataset order of the loaded tasks, used to keep metrics rows in
        # canonical (round, arm, dataset) order on every flush.
        self.task_order = {t.task_id: i for i, t in enumerate(self.tasks)}
        # Rebuild the CURRENT round's map from its own CSV (fresh dataset
        # order wins for this round; other rounds keep their stored order).
        if round_no is not None:
            cur = {t.task_id: i for i, t in enumerate(self.tasks)}
            prev = self.round_order.get(round_no, {})
            for i, t in enumerate(self.tasks):
                prev.setdefault(t.task_id, i)
            self.round_order[round_no] = {t.task_id: i for i, t in enumerate(self.tasks)}

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
                        restored = (
                            safe_restore_workspace(task)
                            if self.case3_enabled
                            else restore_workspace(task)
                        )
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
                            "tier": task.tier,
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
                            "workdir_modified": None,
                            "pruned_skill_files": None,
                            "human_interventions": 1,
                            "completed_at": datetime.now().isoformat(
                                timespec="seconds"
                            ),
                        }
                        self._replace_or_add_row(row)
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
                            "tier": task.tier,
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
                            "workdir_modified": None,
                            "pruned_skill_files": None,
                            "human_interventions": 1,
                            "completed_at": datetime.now().isoformat(
                                timespec="seconds"
                            ),
                        }
                    self._replace_or_add_row(row)
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

        # Post-task learning hook (treatment arm): explicitly trigger Hermes's
        # native memory/skill write path so the learning loop can actually
        # persist across rounds (one-shot mode never auto-fires it).
        # New-tier tasks are excluded: the hook must not deliberately practice
        # the specificity-control families (cli_tool/docker_configure) or New
        # stops being a no-learning baseline.
        #
        # Case-3 quality gates (spec §4.1/§4.2):
        #   - the hook runs ONLY when the target files in work/ were
        #     verifiably modified (verify_workdir_modified), otherwise
        #     hook_status = "skipped(no-diff)";
        #   - the hook runs ONLY for solutions scoring >= hook_min_score
        #     (1.0 = perfect), otherwise "skipped(score<1.0)";
        #   - when the gate passes the hook uses the ADVERSARIAL_HOOK_PROMPT
        #     (quality filter) instead of the plain distilling prompt.
        hook_status = hook_duration = None
        hook_mem_delta = hook_skill_delta = hook_mem_bytes_delta = None
        tier_excluded = (
            self.hook_exclude_tiers and task.tier in self.hook_exclude_tiers
        )
        hook_eligible = (
            self.learning_hook is not None
            and arm == self.hook_arm
            and not self.dry_run
            and not tier_excluded
        )
        workdir_modified = (
            verify_workdir_modified(task.workdir, since=start_dt)
            if self.case3_enabled
            else True
        )
        if hook_eligible and status != "ok":
            # Only persist recalled lessons from tasks Hermes completed.
            # Otherwise failures seed wrong lessons into memory and poison
            # later rounds; the skip is still recorded so runs stay auditable.
            hook_status = "skipped(not-ok)"
            self.logger(
                f"  [hook] skipped {task.task_id} (status={status}) - "
                "not persisting lessons from a non-ok task"
            )
        elif self.learning_hook and arm == self.hook_arm and not self.dry_run \
                and tier_excluded:
            # Deliberate design: New = specificity control, the hook never
            # runs there (same auditability as the not-ok skip).
            hook_status = "skipped(tier=New)"
        elif hook_eligible and self.case3_enabled \
                and self.require_workdir_diff and not workdir_modified:
            # Case-3 target-diff quality gate: the agent did not verifiably
            # edit any file in work/ (it likely solved via a temp script or
            # only responded in chat). No lesson to distill -> skip the hook.
            hook_status = "skipped(no-diff)"
            self.logger(
                f"  [hook] skipped {task.task_id} (no target-diff in "
                "work/) - refusing to persist an unverified solution"
            )
        elif hook_eligible and self.case3_enabled \
                and (score is None or score < self.hook_min_score):
            # Quality gate: imperfect solutions must not write skills.
            hook_status = "skipped(score<1.0)"
            self.logger(
                f"  [hook] skipped {task.task_id} (score={score} < "
                f"{self.hook_min_score}) - only perfect solutions persist"
            )
        elif hook_eligible:
            hook_usage = self.usage_dir / f"r{round_no}_{arm}_{task.task_id}_hook.json"
            outcome = _outcome_summary(status, score, result.duration_s)
            hook = ifi.run_learning_hook(
                task, outcome, hook_usage,
                adversarial=self.case3_enabled,
            )
            hook_status = "ok" if hook.ok else "error"
            hook_duration = (
                round(hook.result.duration_s, 3) if hook.result else 0.0
            )
            hook_mem_delta = hook.memory_delta()
            hook_skill_delta = hook.skill_delta()
            hook_mem_bytes_delta = (
                hook.after.memory_bytes - hook.before.memory_bytes
                if hook.after is not None else None
            )

        # Case-3 active skill pruner (spec §4.3): any skill that was USED
        # during a failing task (score < 100%) is deleted from the home, so
        # harmful/ineffective procedures cannot accumulate across rounds.
        pruned_skills = 0
        if self.case3_enabled and self.prune_failing_skills \
                and not self.dry_run and score is not None and score < 1.0:
            logs = [p for p in (ifi.log_file,) if p and p.exists()]
            usage_txt = usage_path if usage_path.exists() else None
            session_logs = list(logs) + (
                [str(usage_path)] if usage_txt else []
            )
            pruned = prune_failing_skills(ifi.home_dir, session_logs)
            pruned_skills = len(pruned)
            if pruned_skills:
                self.logger(
                    f"  [pruner] removed {pruned_skills} skill file(s) after "
                    f"failing task {task.task_id}: {pruned}"
                )

        row = {
            "run_id": self.run_id,
            "round": round_no,
            "arm": arm,
            "task_id": task.task_id,
            "family": task.family,
            "category": task.category,
            "tier": task.tier,
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
            "workdir_modified": bool(workdir_modified),
            "pruned_skill_files": pruned_skills,
            "hook_status": hook_status,
            "hook_duration_s": hook_duration,
            "hook_memory_files_delta": hook_mem_delta,
            "hook_skill_files_delta": hook_skill_delta,
            "hook_memory_bytes_delta": hook_mem_bytes_delta,
            # Human intervention = the operator/harness had to act on this
            # task (timeout kill, crash, or failed exit). Headless one-shot
            # auto-approves tool prompts, so this counts manual attention.
            "human_interventions": 0 if status == "ok" else 1,
            "completed_at": datetime.now().isoformat(timespec="seconds"),
        }
        return row

    # ---------------------------------------------------------------- utils
    def _row_rank(self, row: dict) -> tuple:
        """(round, arm, dataset-order) sort key; dataset order is per-round."""
        rd = int(float(row.get("round", 0)))
        order_map = self.round_order.get(rd) or {}
        return (
            float(row.get("round", 0)),
            {"treatment": 0, "control": 1}.get(row.get("arm"), 2),
            order_map.get(str(row.get("task_id", "")), 1 << 30),
        )

    def _replace_or_add_row(self, row: dict) -> None:
        """Record a task row at its canonical position, replacing any previous
        row for the same (round, arm, task_id).

        Canonical order: round ascending, treatment before control, then
        dataset order inside a block. When a resumed run re-executes a
        timed-out/skipped task, its old row is removed and the fresh result
        lands exactly where the task sits in the round (never a duplicate,
        never appended at the end).
        """
        key = self._row_rank(row)
        dup_round = float(row.get("round", 0))
        dup_arm = row.get("arm")
        dup_task = str(row.get("task_id", ""))
        self.rows = [
            r for r in self.rows
            if not (float(r.get("round", 0)) == dup_round
                    and str(r.get("arm")) == str(dup_arm)
                    and str(r.get("task_id", "")) == dup_task)
        ]
        for i, existing in enumerate(self.rows):
            if self._row_rank(existing) > key:
                self.rows.insert(i, row)
                self.done.add((int(dup_round), dup_arm, dup_task))
                return
        self.rows.append(row)
        self.done.add((int(dup_round), dup_arm, dup_task))

    def _flush_metrics(self) -> pd.DataFrame:
        # Keep the reservoir in canonical order: round ascending, treatment
        # before control, then per-round dataset order inside a block. New
        # rows are replaced into place, but a stable full sort guarantees the
        # file is ordered even when a resume run completes rounds out of
        # sequence.
        rows = sorted(self.rows, key=self._row_rank)
        df = pd.DataFrame(rows, columns=METRIC_COLUMNS)
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
        # Case-3 verdict (spec §8.2): PassRate gate + Fisher exact gate.
        # Computed independently of the xlsx/plots stage so a plotting hiccup
        # can never swallow the faculty verdict.
        c3 = self.config.get("case3", {})
        if self.case3_enabled:
            try:
                from analysis.metrics_engine import case3_verdict
                c3v = case3_verdict(df, float(c3.get(
                    "delta_pass_threshold", 0.05)), float(c3.get(
                        "alpha", 0.05)))
                self.logger(
                    "CASE3 VERDICT: "
                    f"delta_pass={c3v['delta_pass']:+.1%} "
                    f"(need >=+{c3v['delta_threshold']:.0%}), "
                    f"fisher_p={c3v['fisher_p']:.4f} (need <{c3v['alpha']})\n"
                    + c3v["verdict"]
                )
            except Exception as exc:
                self.logger(f"case3 verdict skipped: {exc}")
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
            vt = res.get("verdict_by_tier")
            if vt:
                for tier in ("Repeat", "Variant", "New"):
                    v = vt.get(tier)
                    if v is None:
                        continue
                    self.logger(
                        f"TIER VERDICT [{tier}]: "
                        + (", ".join(v["supported_metrics"]) or "not supported")
                    )
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
