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

try:
    import ctypes
    from ctypes import wintypes

    _HAVE_CTYPES = True
except Exception:  # pragma: no cover - non-Windows fallback
    _HAVE_CTYPES = False

_LOG_LINE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+\s+\w+\s+[\w.]+:\s*(.*)$"
)

# Instructs the agent to persist lessons through Hermes's native write paths
# (the `memory` tool -> memories/MEMORY.md|USER.md, `skill_manage` ->
# skills/). One-shot mode never auto-fires these; this hook is the explicit
# "memorize trigger" that makes the learning loop testable headlessly.
_HOOK_PROMPT = (
    "You are Hermes. You just worked on the task below inside this repository.\n\n"
    "TASK_ID: {task_id}\n"
    "OUTCOME: {outcome}\n\n"
    "TASK PROMPT:\n{prompt}\n\n"
    "Now act as a persistent, self-improving agent. Distill 1-3 durable, "
    "concrete lessons from this task that would materially help a FUTURE "
    "session succeed on this exact task (or a very similar one) faster and "
    "more accurately.\n\n"
    "Persist each lesson using the MEMORY TOOL that is available to you:\n"
    '  - memory(action="add", target="memory", content="<one declarative '
    'lesson as a concise fact, not an instruction>")'
    "\n"
    "- Prefer memory entries for per-repo/per-stack facts; prefer SKILL.md "
    "writes (skills/ folder) for genuinely reusable procedures.\n"
    "- Do not duplicate existing entries; keep each entry short.\n"
    "- If nothing is worth persisting, call the memory tool once with a short "
    "'nothing learned' note so your decision is visible.\n\n"
    "After making the needed tool calls, reply with EXACTLY the single word "
    "DONE and nothing else."
)


def _outcome_summary(status, score, duration_s):
    if status == "ok":
        return f"ok, score={score}"
    return f"{status} score={score} ({duration_s:.0f}s)"


def _run_kill_on_close(cmd, **kwargs):
    """subprocess.run() that ALSO kills the whole process tree afterwards.

    The agent may start background servers (e.g. `uvicorn app:app`) while
    solving a task. Those children survive `hermes -z`'s exit and hold file
    locks on the task workdir, which made the next arm's restore_workspace
    fail with PermissionError (pilot round 1: 2 control tasks skipped). On
    Windows, put the process in a Job Object with KILL_ON_JOB_CLOSE so every
    descendant dies when the run finishes; elsewhere fall back to plain run().
    """
    if not _HAVE_CTYPES or os.name != "nt":
        return subprocess.run(cmd, **kwargs)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
            ("IoCounters", ctypes.c_uint64 * 6),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
    timeout = kwargs.pop("timeout", None)
    if kwargs.pop("capture_output", False):
        kwargs.setdefault("stdout", subprocess.PIPE)
        kwargs.setdefault("stderr", subprocess.PIPE)
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        if timeout is not None:
            kwargs["timeout"] = timeout
        return subprocess.run(cmd, **kwargs)
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    ok = kernel32.SetInformationJobObject(
        job, 9, ctypes.byref(info), ctypes.sizeof(info)
    )
    if not ok:
        kernel32.CloseHandle(job)
        if timeout is not None:
            kwargs["timeout"] = timeout
        return subprocess.run(cmd, **kwargs)
    try:
        proc = subprocess.Popen(cmd, **kwargs)
    except Exception:
        kernel32.CloseHandle(job)
        raise
    assigned = kernel32.AssignProcessToJobObject(job, proc._handle)

    # Read stdout/stderr on threads: communicate() waits for PIPE EOF, but a
    # background child (uvicorn etc.) inherits the pipe handles, so EOF never
    # comes while it lives - communicate() would block until timeout even
    # though the parent already exited.
    import threading

    text_mode = bool(kwargs.get("text") or kwargs.get("encoding"))
    eof = "" if text_mode else b""
    chunks_out, chunks_err = [], []

    def _pump(stream, sink):
        if stream is not None:
            for line in iter(stream.readline, eof):
                sink.append(line)

    t_out = threading.Thread(target=_pump, args=(proc.stdout, chunks_out), daemon=True)
    t_err = threading.Thread(target=_pump, args=(proc.stderr, chunks_err), daemon=True)
    t_out.start()
    t_err.start()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise
    finally:
        # Closing the last job handle kills every process still in the job,
        # including any background servers the agent spawned. The daemon
        # reader threads then see EOF on the freed pipes and stop.
        kernel32.CloseHandle(job)
        t_out.join(timeout=5)
        t_err.join(timeout=5)
        if not assigned:
            proc.kill()
    stdout = "".join(chunks_out)
    stderr = "".join(chunks_err)
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", errors="replace")
    return subprocess.CompletedProcess(
        proc.args, proc.returncode, stdout, stderr
    )


@dataclass
class LearningHook:
    """Result of the explicit post-task memorization hook."""
    task_id: str
    ok: bool
    outcome: str
    error: str
    before: LearningState
    after: LearningState | None
    result: HermesRunResult | None

    def memory_delta(self) -> int:
        if self.after is None:
            return 0
        return self.after.memory_files - self.before.memory_files

    def skill_delta(self) -> int:
        if self.after is None:
            return 0
        return self.after.skill_files - self.before.skill_files


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
        self.seed_skills = bool(config["hermes"].get("seed_skills", True))
        self.learning_hook = bool(config["benchmark"].get("learning_hook", True))
        self.log_file = None

    # ------------------------------------------------------------------ setup
    def seed_home(self) -> None:
        """Create a fresh HERMES_HOME with config.yaml + .env copied from
        the real home, and — when seed_skills is enabled (default) — a full
        copy of the real home's bundled `skills/` tree.

        Both arms start with Hermes's real pre-existing knowledge base (the
        542 bundled skills); the treatment arm may then *add* to it (via the
        native skill/memory write paths exposed by the learning hook), which
        is what the "self-improvement" claim is really about."""
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
        if self.seed_skills:
            self._seed_skills_from_real_home()
        self._locate_log_file()

    def _seed_skills_from_real_home(self) -> None:
        """Copy the real home's skills/ tree into HERMES_HOME/skills.

        The bundled snapshot (.skills_prompt_snapshot.json) is deliberately
        NOT copied: it caches real-home mtimes and would immediately be
        rebuilt anyway; letting Hermes regenerate it keeps the bench home
        self-consistent."""
        src = self.real_home / "skills"
        dst = self.home_dir / "skills"
        if not src.is_dir():
            return
        if dst.exists():
            return
        try:
            shutil.copytree(src, dst)
            n = sum(1 for p in dst.rglob("*") if p.is_file())
            print(f"[hermes] seeded {n} skills -> {dst}")
        except Exception as exc:  # pragma: no cover - defensive
            print(f"[hermes] WARNING: failed to seed skills: {exc}")

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
        if not task.prompt.strip():
            raise ValueError(f"task {task.task_id}: empty prompt")
        return self._invocation(task.prompt, task.workdir, usage_path)

    def run_learning_hook(
        self,
        task,
        outcome_summary: str,
        usage_path: Path | None = None,
    ) -> LearningHook:
        """Trigger Hermes's NATIVE memory write path (one-shot mode never
        auto-fires it): run a short `-z` session whose prompt directs the
        agent to distill lessons and persist them with the built-in `memory`
        tool (memories/MEMORY.md / USER.md) and, when warranted, the
        `skill_manage` tool. Returns before/after learning states so the
        runner can measure how much the hook actually persisted."""
        prompt = _HOOK_PROMPT.format(
            task_id=task.task_id,
            outcome=outcome_summary,
            prompt=task.prompt[:4000],
        )
        before = self.learning_state()
        if self.learning_hook:
            try:
                if usage_path is None:
                    raise ValueError("learning hook requires a usage path")
                result = self._invocation(prompt, task.workdir, usage_path)
            except Exception as exc:  # defensive: never fail the round
                print(f"[hermes] HOOK FAILED for {task.task_id}: {exc!r}")
                return LearningHook(
                    task_id=task.task_id,
                    ok=False,
                    outcome=outcome_summary,
                    error=f"{type(exc).__name__}: {exc}",
                    before=before,
                    after=None,
                    result=None,
                )
        else:
            result = None
        after = self.learning_state()
        return LearningHook(
            task_id=task.task_id,
            ok=result is None or result.exit_code == 0,
            outcome=outcome_summary,
            error="",
            before=before,
            after=after,
            result=result,
        )

    def _invocation(
        self, prompt: str, workdir: Path, usage_path: Path | None
    ) -> HermesRunResult:
        """Shared headless `hermes -z` subprocess driver."""
        if len(prompt) > 30000:
            raise ValueError(
                f"prompt too long for the command line "
                f"({len(prompt)} chars, Windows limit ~32767)"
            )
        cmd = [str(self.exe), "-z", prompt]
        if usage_path is not None:
            cmd += ["--usage-file", str(usage_path)]
        if self.model:
            cmd += ["--model", self.model]
        if self.provider:
            cmd += ["--provider", self.provider]
        cmd += self.extra_args

        env = os.environ.copy()
        env["HERMES_HOME"] = str(self.home_dir)

        if not workdir.exists():
            print(
                f"[hermes] WARNING: task workdir missing: {workdir}; "
                "running in project root is unsafe - treating as harness error"
            )
            raise FileNotFoundError(f"task workdir missing: {workdir}")
        workdir.mkdir(parents=True, exist_ok=True)

        timed_out = crashed = False
        kwargs = dict(cwd=str(workdir), env=env, capture_output=True,
                      text=True, encoding="utf-8", errors="replace",
                      timeout=self.timeout_s)
        if os.name == "nt":
            kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
        start_ts = datetime.now()
        try:
            proc = _run_kill_on_close(cmd, **kwargs)
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
        duration_s = (end_ts - start_ts).total_seconds()

        self._locate_log_file()  # agent.log is only created after the first run
        usage = self._load_usage(usage_path)
        return HermesRunResult(
            exit_code=exit_code,
            response=stdout.strip(),
            stderr=stderr.strip(),
            duration_s=duration_s,
            usage=usage,
            session_id=usage.get("session_id"),
            timed_out=timed_out,
            crashed=crashed,
        )

    @staticmethod
    def _load_usage(usage_path: Path | None) -> dict:
        if usage_path is None or not usage_path.exists():
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
        # Hermes persists its built-in memory under HERMES_HOME/n/
        # (MEMORY.md / USER.md / *.md) rather than a `memories/` dir; both
        # locations are counted so the learning-loop metrics track the real
        # memory store (see agent docs: n/MEMORY.md).
        memory_dirs = []
        n_dir = self.home_dir / "n"
        if n_dir.exists():
            memory_dirs.append(n_dir)
        memories_dir = self.home_dir / "memories"
        if memories_dir.exists():
            memory_dirs.append(memories_dir)
        files = [
            p for d in memory_dirs for p in d.rglob("*") if p.is_file()
        ]
        state.memory_files = len(files)
        state.memory_bytes = sum(p.stat().st_size for p in files)
        state_db = self.home_dir / "state.db"
        if state_db.exists():
            state.state_db_bytes = state_db.stat().st_size
        return state
