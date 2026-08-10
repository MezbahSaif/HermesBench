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
from datetime import datetime, timedelta
from pathlib import Path

try:
    import ctypes
    from ctypes import wintypes

    _HAVE_CTYPES = True
except Exception:  # pragma: no cover - non-Windows fallback
    _HAVE_CTYPES = False

_RECENT_WINDOW = timedelta(hours=1)

_TOKEN_RE = re.compile(r"[a-z0-9_]{3,}")

_STOPWORDS = {
    "and", "the", "for", "with", "you", "your", "this", "that", "task",
    "must", "should", "will", "are", "not", "from", "into", "using",
    "write", "file", "files", "code", "python", "mod", "work", "prompt",
    "expected", "following", "above", "below", "make", "sure", "then",
    "when", "they", "have", "been", "will", "list", "need", "use", "cli",
}


def _keyword_tokens(text: str) -> set[str]:
    """Case-insensitive keyword bag (fix #5 skill matching)."""
    return {t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS}


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


# Case-3 adversarial post-task reflection prompt (FIX_BRIEF/spec §4.2).
# Used ONLY when the target-diff quality gate passes (workdir modified) AND
# the task scored a perfect 1.0. The quality filter makes the learning loop
# persist only clean, generalizable lessons and DISCARD one-off hacks.
ADVERSARIAL_HOOK_PROMPT = (
    "You are performing a post-task reflection on the task you just solved.\n"
    "Your goal is to decide whether to save a skill or memory for FUTURE "
    "sessions.\n\n"
    "TASK_ID: {task_id}\n"
    "OUTCOME: {outcome}\n\n"
    "TASK PROMPT:\n{prompt}\n\n"
    "CRITICAL QUALITY FILTER:\n"
    "1. Did you solve this task by editing the target source files in "
    "`work/`?\n"
    "2. Is the solution a clean, generalizable software engineering pattern?\n"
    "3. If you used a temporary script, hardcoded hack, or one-off workaround, "
    "DISCARD IT. DO NOT WRITE A SKILL.\n\n"
    "If the task solution is high-quality and reusable:\n"
    '  - Use `skill_manage(action="create", name="...", content="...")` to '
    "save a structured workflow.\n"
    '  - Use `memory(action="add", target="memory", content="...")` for '
    "concise, universal rules.\n\n"
    "If no generalizable lesson exists, reply strictly with: "
    '"NO_SKILL_PERSISTED: Solution was task-specific or required no '
    'permanent skill."\n\n'
    "After deciding, reply with EXACTLY the single word DONE and nothing else."
)


# Case-3b memory-only reflection prompt: used when quality-gated tiering
# admits a good-but-not-perfect solution (0.7 <= score < 1.0). Lessons are
# persisted as memory entries ONLY - never as skills.
MEMORY_ONLY_HOOK_PROMPT = (
    "You are performing a post-task reflection on a task you just completed.\n"
    "Your goal is to decide whether to save a MEMORY for FUTURE sessions.\n\n"
    "TASK_ID: {task_id}\n"
    "OUTCOME: {outcome}\n\n"
    "TASK PROMPT:\n{prompt}\n\n"
    "QUALITY FILTER:\n"
    "1. Did you solve this task by editing the target source files in\n"
    "   `work/`?\n"
    "2. Even though the solution was not perfect, is there a concise, durable\n"
    "   warning rule, edge case, or negative lesson worth remembering?\n"
    "3. Hardcoded hacks or task-specific fixes: DISCARD. DO NOT WRITE A SKILL.\n\n"
    "If a durable memory exists:\n"
    '  - Use `memory(action="add", target="memory", content="...")` ONLY.\n'
    "  - NEVER create or modify any skill file - this tier is memory-only.\n\n"
    "If nothing durable exists, reply strictly with:\n"
    '"NO_MEMORY_PERSISTED: no durable lesson qualifies."\n\n'
    "After deciding, reply with EXACTLY the single word DONE and nothing else."
)


def _outcome_summary(status, score, duration_s):
    if status == "ok":
        return f"ok, score={score}"
    return f"{status} score={score} ({duration_s:.0f}s)"


def verify_workdir_modified(workdir: Path,
                            since: datetime | None = None) -> bool:
    """Case-3 target-diff quality gate (spec §4.1).

    Returns True when the agent verifiably modified files in ``workdir``.
    Methods, in order:

      1. ``git status --porcelain`` inside the workdir: non-empty output means
         new/modified files exist -> True.
      2. Fallback (git unavailable, workdir not a repo, or empty because the
         task fixtures live in gitignored paths): compare file modification
         timestamps against ``since`` (the task start time). Any file whose
         mtime is at/after ``since`` counts as proof of editing.

    The runner passes ``since`` = the task's start timestamp; when it is not
    provided we fall back to a 1-hour "recently touched" window so a caller
    without timing context still gets a meaningful answer.
    """
    if workdir is None or not Path(workdir).is_dir():
        return False
    workdir = Path(workdir)
    try:
        result = subprocess.run(
            ["git", "-C", str(workdir), "status", "--porcelain"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return True
    except (OSError, subprocess.SubprocessError):
        pass
    cutoff = since or (datetime.now() - _RECENT_WINDOW)
    for p in workdir.rglob("*"):
        try:
            if p.is_file() and p.stat().st_mtime >= cutoff.timestamp() - 1.0:
                return True
        except OSError:
            continue
    return False


def prune_failing_skills(home_dir: Path, session_logs) -> list[str]:
    """Case-3 active skill pruner (spec §4.3).

    After a failing task (score < 100%), delete any skill file that was
    USED during that session so bad procedures cannot accumulate and leak
    into later rounds.

    ``session_logs`` is a list of agent-log paths (or raw text strings); each
    is scanned for skill tool invocations (``skill_view`` /
    ``skill_manage``) and the skill name is extracted from the surrounding
    text (Hermes logs the tool name; the input args carrying the skill name
    may also appear on the same line). Matching ``.md`` files under
    ``home_dir/skills/`` are deleted.

    The seeded contract skill (``benchmark_coding_contract``) is NEVER pruned
    - it is mandated into both arms and is not a learned artifact.

    Returns the list of deleted skill file stems.
    """
    if not home_dir or not Path(home_dir).is_dir():
        return []
    skill_root = Path(home_dir) / "skills"
    if not skill_root.is_dir():
        return []
    texts: list[str] = []
    for item in session_logs or []:
        if not item:
            continue
        item = str(item)
        try:
            if len(item) < 4096 and Path(item).exists():
                texts.append(Path(item).read_text(
                    encoding="utf-8", errors="ignore"))
            else:
                texts.append(item)
        except OSError:
            texts.append(item)

    found: set[str] = set()
    for text in texts:
        # Spec §4.3: prune skills that were READ (used) during the failing
        # session. skill_view is inherently a read; skill_manage only counts
        # when action="read". Some loggers omit the action, so also accept a
        # bare name/target grab.
        for m in re.finditer(
            r"skill_(?:view|manage)([^\n]{0,180})"
            r"(?:action\s*=\s*[\"']read[\"'])?"
            r"[^\n]{0,80}"
            r"((?:name|target)\s*[=:]\s*[\"']?([\w\-\.]+)[\"']?)",
            text, re.IGNORECASE,
        ):
            action = (m.group(1) or "").lower()
            if m.group(0).startswith("skill_manage") \
                    and "action" in action \
                    and "read" not in action:
                # skill_manage with an explicit non-read action (create/delete)
                # did not consume the skill - nothing to prune here.
                continue
            name = (m.group(3) or m.group(2) or "").strip()
            if name and name.lower() != "benchmark_coding_contract":
                found.add(name.replace(".md", ""))
    deleted: list[str] = []
    for name in sorted(found):
        if name.lower() == "benchmark_coding_contract":
            continue
        hits = [p for p in skill_root.rglob("*.md")
                if p.stem.lower() == name.lower()
                or p.parent.name.lower() == name.lower()]
        for p in hits:
            try:
                p.unlink()
                deleted.append(p.name)
                print(f"[PRUNER] Deleted harmful/ineffective skill: {p.name}")
            except OSError as exc:
                print(f"[PRUNER] could not delete {p.name}: {exc!r}")
    return deleted


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
        self.config = config
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
        self.learning_hook = bool(config.get("learning_hook", {}).get(
            "enabled", True))
        case3 = config.get("case3", {})
        self.contract_skill = (
            Path(case3["seed_contract_skill"])
            if case3.get("seed_contract_skill")
            else None
        )
        self.adversarial_hook = bool(case3.get("adversarial_hook", False))
        # Case-3b hook hardening: the post-task reflection session is capped
        # at hook_timeout_s (default 120s) so a runaway hook can never stall
        # a round or burn tokens for 900s like the task invocation.
        self.hook_timeout_s = float(case3.get("hook_timeout_s", 120))
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
        self._seed_contract_skill()
        self._locate_log_file()

    def _seed_contract_skill(self) -> None:
        """Case 3: pre-load the mandatory benchmark coding contract into the
        arm home (both treatment and control) so the formatting/import rules
        are system-prompt visible from round 1 regardless of arm reset."""
        if self.contract_skill is None or not self.contract_skill.exists():
            return
        dst = self.home_dir / "skills" / "benchmark" / "coding-contract"
        dst.mkdir(parents=True, exist_ok=True)
        target = dst / "SKILL.md"
        try:
            shutil.copy2(self.contract_skill, target)
            print(f"[hermes] seeded contract skill -> {target}")
        except Exception as exc:  # pragma: no cover - defensive
            print(f"[hermes] WARNING: failed to seed contract skill: {exc}")

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
        prompt = task.prompt
        # Case-3b fix #5: active skill injection. Match task keywords against
        # the local home skill index and pre-load the top-k hits into the
        # prompt so the model does not have to discover them mid-run.
        injected = self._skill_injection_context(task)
        if injected:
            prompt = injected + "\n\n" + prompt
        return self._invocation(prompt, task.workdir, usage_path)

    def _skill_injection_context(self, task,
                                 top_k: int | None = None) -> str:
        """Fuse task keywords with the local skill library (fix #5).

        Returns a 'consult these skills' preamble, or '' when disabled or
        nothing matches. Reads SKILL.md files under HERMES_HOME/skills/ and
        scores them by keyword overlap with the task prompt.
        """
        inject_cfg = self.config.get("case3", {}).get("inject_skills", {})
        if not inject_cfg or not inject_cfg.get("enabled", False):
            return ""
        top_k = top_k or int(inject_cfg.get("top_k", 3))
        max_chars = int(inject_cfg.get("max_chars_per_skill", 600))
        skills_root = self.home_dir / "skills"
        if not skills_root.is_dir():
            return ""
        task_words = _keyword_tokens(task.prompt)
        if not task_words:
            return ""
        hits: list[tuple[int, Path, str]] = []
        for md in skills_root.rglob("SKILL.md"):
            try:
                text = md.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            score_ = len(task_words & _keyword_tokens(text[:4000]))
            if score_ > 0:
                hits.append((score_, md, md.parent.name))
        if not hits:
            return ""
        hits.sort(key=lambda h: (-h[0], h[2]))
        parts = ["RELEVANT SKILLS (consult these before answering):"]
        for _, md, name in hits[:top_k]:
            head = md.read_text(encoding="utf-8",
                                errors="ignore")[:max_chars].strip()
            parts.append(f"\n--- skill: {name} ---\n{head}")
        return "\n".join(parts)

    def run_learning_hook(
        self,
        task,
        outcome_summary: str,
        usage_path: Path | None = None,
        adversarial: bool | None = None,
        memory_only: bool = False,
    ) -> LearningHook:
        """Trigger Hermes's NATIVE memory write path (one-shot mode never
        auto-fires it): run a short `-z` session whose prompt directs the
        agent to distill lessons and persist them with the built-in `memory`
        tool (memories/MEMORY.md / USER.md) and, when warranted, the
        `skill_manage` tool. Returns before/after learning states so the
        runner can measure how much the hook actually persisted.

        Case 3: when `adversarial` (default: config) is enabled, the prompt
        is the quality-filtered ADVERSARIAL_HOOK_PROMPT (spec §4.2) instead
        of the plain distilling prompt.

        Case 3b: `memory_only` selects the MEMORY_ONLY_HOOK_PROMPT, which
        forbids skill writes (tier for 0.7 <= score < 1.0). The hook session
        is hard-capped at hook_timeout_s (default 120s), with a result
        fallback preserving the error when the cap is hit (fix #1)."""
        if adversarial is None:
            adversarial = self.adversarial_hook
        if memory_only:
            prompt_tpl = MEMORY_ONLY_HOOK_PROMPT
        elif adversarial:
            prompt_tpl = ADVERSARIAL_HOOK_PROMPT
        else:
            prompt_tpl = _HOOK_PROMPT
        prompt = prompt_tpl.format(
            task_id=task.task_id,
            outcome=outcome_summary,
            prompt=task.prompt[:4000],
        )
        before = self.learning_state()
        if self.learning_hook:
            try:
                if usage_path is None:
                    raise ValueError("learning hook requires a usage path")
                result = self._invocation(
                    prompt, task.workdir, usage_path,
                    timeout_s=self.hook_timeout_s,
                )
            except subprocess.TimeoutExpired as exc:
                # Fix #1 (defensive): _invocation() normally converts the
                # timeout into HermesRunResult(timed_out=True), so this
                # branch only fires if the subprocess layer raises directly.
                print(f"[hermes] HOOK TIMEOUT for {task.task_id}"
                      f" (>{self.hook_timeout_s}s)")
                return LearningHook(
                    task_id=task.task_id,
                    ok=False,
                    outcome=outcome_summary,
                    error=(f"hook timeout > {self.hook_timeout_s}s"
                           f": {getattr(exc, 'stdout', b'')[:200]!r}"),
                    before=before,
                    after=None,
                    result=None,
                )
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
            if result.timed_out:
                # The hook hit its 120s cap: _invocation swallowed
                # TimeoutExpired and returned a timed_out result. Record it
                # as a non-fatal error with a real message (not empty ""),
                # so hook_status = "error" rows are auditable.
                print(f"[hermes] HOOK TIMEOUT for {task.task_id}"
                      f" (>{self.hook_timeout_s}s)")
                return LearningHook(
                    task_id=task.task_id,
                    ok=False,
                    outcome=outcome_summary,
                    error=f"hook timeout > {self.hook_timeout_s}s",
                    before=before,
                    after=None,
                    result=result,
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
        self, prompt: str, workdir: Path, usage_path: Path | None,
        timeout_s: float | None = None,
    ) -> HermesRunResult:
        """Shared headless `hermes -z` subprocess driver.

        ``timeout_s`` overrides the configured task timeout for special
        invocations (post-task hook, fix #1); None = task timeout."""
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
                      timeout=(
                          timeout_s if timeout_s is not None
                          else self.timeout_s
                      ))
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
