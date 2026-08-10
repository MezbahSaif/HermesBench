"""Programmatic interface to the Hermes Agent CLI (headless one-shot mode).

Drives ``hermes -z PROMPT --usage-file PATH`` as a subprocess with an
isolated HERMES_HOME per benchmark arm, collects the final response, the JSON
usage report, wall-clock time, and parses the agent log for tool-call /
error / retry / reflection signals.

Learning-loop instrumentation: each arm gets its own HERMES_HOME. The
treatment arm's home accumulates skills/memories/sessions across rounds;
the control arm's home is reset (and re-seeded) before every round.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

_LOG_LINE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+\s+\w+\s+[\w.]+:\s*(.*)$"
)


@dataclass
class HermesRunResult:
    exit_code: int
    response: str
    stderr: str
    duration_s: float
    usage: dict
    session_id: str | None
    timed_out: bool = False
    crashed: bool = False


@dataclass
class LogSignalCounts:
    tool_calls: int = 0
    errors: int = 0
    retries: int = 0
    reflections: int = 0
    failed_request_dumps: int = 0


@dataclass
class LearningState:
    """Snapshot of learning-loop artifacts in a Hermes home."""
    skill_files: int = 0
    memory_files: int = 0
    memory_bytes: int = 0
    state_db_bytes: int = 0

    def to_dict(self, prefix: str) -> dict:
        return {
            f"{prefix}_skill_files": self.skill_files,
            f"{prefix}_memory_files": self.memory_files,
            f"{prefix}_memory_bytes": self.memory_bytes,
            f"{prefix}_state_db_bytes": self.state_db_bytes,
        }


class HermesInterface:
    def __init__(self, config: dict, home_dir: Path, workdir_root: Path):
        self.exe = Path(config["hermes"]["executable"])
        self.real_home = Path(config["hermes"]["real_home"])
        self.model = config["hermes"].get("model") or ""
        self.provider = config["hermes"].get("provider") or ""
        self.extra_args = list(config["hermes"].get("extra_args") or [])
        self.timeout_s = float(config["hermes"].get("timeout_s", 900))
        self.home_dir = home_dir
        self.workdir_root = workdir_root
        self.log_metrics_cfg = config.get("log_metrics", {})
        self.log_file = None

    # ------------------------------------------------------------------ setup
    def seed_home(self) -> None:
        """Create a fresh HERMES_HOME with only config.yaml + .env copied
        from the real home (no skills, memories, or sessions)."""
        self.home_dir.mkdir(parents=True, exist_ok=True)
        copied = 0
        for name in ("config.yaml", ".env", "SOUL.md"):
            src = self.real_home / name
            if src.exists():
                shutil.copy2(src, self.home_dir / name)
                copied += 1
        if copied == 0:
            print(
                f"[hermes] WARNING: nothing to seed from real home "
                f"{self.real_home} (no config.yaml/.env/SOUL.md) - the "
                "agent will run with Hermes defaults!"
            )
        self._locate_log_file()

    def reset_home(self) -> None:
        """Delete and re-seed the home (control arm: no learning persists)."""
        if self.home_dir.exists():
            shutil.rmtree(self.home_dir)
        self.seed_home()

    def _locate_log_file(self) -> None:
        # Logs live under HERMES_HOME/logs/agent.log for the bench home.
        candidate = self.home_dir / "logs" / "agent.log"
        self.log_file = candidate if candidate.exists() else None

    # ------------------------------------------------------------- invocation
    def run_task(self, task, usage_path: Path) -> HermesRunResult:
        """Execute one task via `hermes -z` and return everything we know."""
        start_ts = datetime.now()
        if len(task.prompt) > 30000:
            raise ValueError(
                f"task {task.task_id}: prompt too long for the command line "
                f"({len(task.prompt)} chars, Windows limit ~32767)"
            )
        if not task.prompt.strip():
            raise ValueError(f"task {task.task_id}: empty prompt")
        cmd = [str(self.exe), "-z", task.prompt, "--usage-file", str(usage_path)]
        if self.model:
            cmd += ["--model", self.model]
        if self.provider:
            cmd += ["--provider", self.provider]
        cmd += self.extra_args

        env = os.environ.copy()
        env["HERMES_HOME"] = str(self.home_dir)

        if not task.workdir.exists():
            print(
                f"[hermes] WARNING: task workdir missing: {task.workdir}; "
                "running in project root is unsafe - treating as harness error"
            )
            raise FileNotFoundError(
                f"task workdir missing: {task.workdir}"
            )
        workdir = task.workdir
        workdir.mkdir(parents=True, exist_ok=True)

        timed_out = crashed = False
        kwargs = dict(cwd=str(workdir), env=env, capture_output=True,
                      text=True, encoding="utf-8", errors="replace",
                      timeout=self.timeout_s)
        if os.name == "nt":
            kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
        try:
            proc = subprocess.run(cmd, **kwargs)
            exit_code, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = -1
            stdout = (exc.stdout or b"").decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = (exc.stderr or b"").decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        except Exception as exc:  # pragma: no cover - defensive
            crashed = True
            exit_code = -2
            stdout, stderr = "", f"harness crash: {exc}"

        end_ts = datetime.now()
        self._locate_log_file()  # agent.log is only created after the first run
        usage = self._load_usage(usage_path)
        return HermesRunResult(
            exit_code=exit_code,
            response=stdout.strip(),
            stderr=stderr.strip(),
            duration_s=(end_ts - start_ts).total_seconds(),
            usage=usage,
            session_id=usage.get("session_id"),
            timed_out=timed_out,
            crashed=crashed,
        )

    @staticmethod
    def _load_usage(usage_path: Path) -> dict:
        if not usage_path.exists():
            return {}
        try:
            return json.loads(usage_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    # -------------------------------------------------------------- signals
    def log_signals(self, start_dt: datetime, end_dt: datetime) -> LogSignalCounts:
        """Heuristic counts from agent.log within [start, end]."""
        cfg = self.log_metrics_cfg
        pattern_map = {
            "tool_calls": cfg.get("tool_call_patterns", []),
            "errors": cfg.get("error_patterns", []),
            "retries": cfg.get("retry_patterns", []),
            "reflections": cfg.get("reflection_patterns", []),
        }
        counts = LogSignalCounts()
        if self.log_file and self.log_file.exists():
            try:
                for line in self.log_file.read_text(
                    encoding="utf-8", errors="ignore"
                ).splitlines():
                    m = _LOG_LINE_RE.match(line)
                    if not m:
                        continue
                    ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                    if not (start_dt <= ts <= end_dt):
                        continue
                    low = line.lower()
                    if any(p in low for p in pattern_map["tool_calls"]):
                        counts.tool_calls += 1
                    if any(p in low for p in pattern_map["errors"]):
                        counts.errors += 1
                    if any(p in low for p in pattern_map["retries"]):
                        counts.retries += 1
                    if any(p in low for p in pattern_map["reflections"]):
                        counts.reflections += 1
            except OSError:
                pass
        counts.failed_request_dumps = self._count_request_dumps(start_dt, end_dt)
        return counts

    def _count_request_dumps(self, start_dt: datetime, end_dt: datetime) -> int:
        """Failed API requests are dumped as JSON under HERMES_HOME/sessions
        with a `timestamp` field; each one is evidence of a retried/failed
        model call."""
        dumps_dir = self.home_dir / "sessions"
        if not dumps_dir.exists():
            return 0
        n = 0
        for f in dumps_dir.glob("request_dump_*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                raw = data.get("timestamp", "")
                if not isinstance(raw, str):
                    continue
                ts = datetime.fromisoformat(raw)
                if start_dt <= ts <= end_dt:
                    n += 1
            except (json.JSONDecodeError, ValueError, TypeError, OSError):
                continue
        return n

    # -------------------------------------------------------- learning state
    def learning_state(self) -> LearningState:
        state = LearningState()
        skills_dir = self.home_dir / "skills"
        if skills_dir.exists():
            state.skill_files = len(
                [p for p in skills_dir.rglob("*") if p.is_file()]
            )
        memories_dir = self.home_dir / "memories"
        if memories_dir.exists():
            files = [p for p in memories_dir.rglob("*") if p.is_file()]
            state.memory_files = len(files)
            state.memory_bytes = sum(p.stat().st_size for p in files)
        state_db = self.home_dir / "state.db"
        if state_db.exists():
            state.state_db_bytes = state_db.stat().st_size
        return state
