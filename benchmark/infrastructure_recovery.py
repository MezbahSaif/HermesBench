"""Windows infrastructure recovery: reserved-file cleanup, orphan processes,
workspace restoration.

Bundled into one module so the benchmark runner and the CLI stay thin and so
the recovery ladder (reserved names -> retry with backoff -> kill orphans ->
retry) is testable in isolation.

Functions moved here from ``benchmark.benchmark_runner`` (they were runner
internals; the runner still re-exports the public names for back-compat):

    * _remove_windows_reserved_files   strip nul/con/aux/... device files
    * _process_table / _ancestor_pids / _agent_orphans / kill_agent_orphans
    * restore_workspace                pristine-snapshot restore
    * safe_restore_workspace           restore_workspace + PRUNE_A_ORPHANS

The routine in :func:`safe_restore_workspace` exists so that workspace cleanup
and copy operations are wrapped in a 3-attempt retry loop: on PermissionError
it kills leftover agent processes and backs off 2**attempt seconds before
retrying (case-3 §5.3).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path


def _remove_windows_reserved_files(root: Path) -> None:
    """Delete files with Windows reserved device names (nul, con, prn, aux,
    com1-9, lpt1-9) that the agent may have created by misinterpreting shell
    redirects (e.g. `> nul`). Normal shutil.rmtree refuses to delete these
    (PermissionError 13) because Windows treats them as devices; the \\?\
    extended path prefix bypasses that."""
    if os.name != "nt":
        return
    reserved = {"nul", "con", "prn", "aux", "com1", "com2", "com3", "com4",
                "com5", "com6", "com7", "com8", "com9",
                "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7",
                "lpt8", "lpt9"}
    # NOTE: match by name only - is_file() is False for device names like
    # "nul", so an is_file() guard would silently skip the files we need to
    # delete.
    for path in list(root.rglob("*")):
        if path.name.lower().split(".")[0] in reserved:
            try:
                os.remove("\\\\?\\" + str(path.resolve()))
            except OSError:
                pass


def _process_table() -> list[dict]:
    """PID, parent PID, name and command line of every process (Windows).

    Uses PowerShell's CIM provider so we get CommandLine (which the standard
    psapi/toolhelp APIs do not expose without deeper tricks). Only called on
    failure paths, so the ~1 s cost is irrelevant.
    """
    script = (
        "Get-CimInstance Win32_Process | "
        "ForEach-Object { \"$($_.ProcessId)|$($_.ParentProcessId)|$($_.Name)|$($_.CommandLine)\" }"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=30,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"[ws] process table unavailable: {exc}")
        return []
    rows = []
    for line in out.splitlines():
        parts = line.split("|", 3)
        if len(parts) == 4 and parts[0].strip().isdigit():
            rows.append({"pid": int(parts[0]), "ppid": int(parts[1]),
                         "name": parts[2], "cmdline": parts[3]})
    return rows


def _ancestor_pids(rows: list[dict], pid: int) -> set[int]:
    by_pid = {r["pid"]: r for r in rows}
    seen, cur = set(), pid
    while cur in by_pid and cur not in seen:
        seen.add(cur)
        cur = by_pid[cur]["ppid"]
    return seen


def _agent_orphans() -> list[int]:
    """PIDs of leftover agent processes that can still lock workdirs.

    After an invocation the job object kills the whole agent process tree, so
    any surviving benchmark-agent process is an orphan from a crashed or
    aborted run (e.g. a server the agent started whose parent shell was
    hard-killed). Candidates: python/pythonw/hermes executables whose command
    line is not LM Studio and not the current runner, its ancestors, or other
    benchmark-owned scripts.
    """
    rows = _process_table()
    if not rows:
        return []
    self_pid = os.getpid()
    protected = _ancestor_pids(rows, self_pid) | {self_pid}
    protected |= {r["pid"] for r in rows
                  if "run_benchmark" in (r["cmdline"] or "")
                  or "metrics_engine" in (r["cmdline"] or "")
                  or "selftest" in (r["cmdline"] or "")}
    # Markers that only an agent-started server or hermes itself would have.
    # Being conservative here matters: we never want to kill an unrelated
    # user process that merely happens to be a venv python.
    server_markers = ("uvicorn", "app:app", "fastapi", "flask", "streamlit",
                      "manage.py", "runserver")
    orphans = []
    for r in rows:
        cmd = (r["cmdline"] or "").lower()
        if r["pid"] in protected:
            continue
        if "lmstudio" in cmd or ".lmstudio" in cmd:
            continue
        name = r["name"].lower()
        if name == "hermes.exe":
            orphans.append(r["pid"])
            continue
        if name not in ("python.exe", "pythonw.exe", "uvicorn.exe"):
            continue
        if not cmd:
            continue
        if any(m in cmd for m in server_markers):
            orphans.append(r["pid"])
    return orphans


def kill_agent_orphans() -> int:
    """Terminate leftover background processes; returns how many were killed."""
    if os.name != "nt":
        return 0
    pids = _agent_orphans()
    if not pids:
        return 0
    try:
        script = ("$ids = '" + ",".join(str(p) for p in pids)
                  + "'.Split(','); foreach ($id in $ids) { "
                  "Stop-Process -Id ([int]$id) -Force -ErrorAction SilentlyContinue }")
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                       capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"[ws] orphan kill failed: {exc}")
        return 0
    time.sleep(1.0)
    print(f"[ws] killed {len(pids)} leftover agent process(es): {pids}")
    return len(pids)


def restore_workspace(task, attempts: int = 4, delay_s: float = 2.0) -> bool:
    """Restore the task workdir from its pristine snapshot, if one exists.

    The pristine snapshot lives at <dataset>/tasks/<task_id>/pristine and is
    created by the task generator (or via --refresh-pristine for hand-made
    datasets). Restoring before every execution guarantees every (round, arm)
    starts from identical, untouched fixtures: the agent's edits never leak
    into later rounds or across arms. Returns True when a restore happened.

    Auto-recovery ladder (Windows) so the benchmark never dies on file locks:
      1. reserved-name files (nul etc.) the agent wrote are stripped first
         (shutil.rmtree can never delete them otherwise);
      2. transient locks are retried with backoff (a still-terminating child
         may briefly hold a handle);
      3. if retries are exhausted, leftover agent processes (orphaned servers
         from a crashed/aborted run) are force-killed and one final attempt
         runs. Only if that also fails does the exception propagate.
    """
    pristine = task.workdir.parent / "pristine"
    if not pristine.is_dir():
        return False
    _remove_windows_reserved_files(task.workdir)
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            if task.workdir.exists():
                shutil.rmtree(task.workdir)
            shutil.copytree(pristine, task.workdir)
            return True
        except Exception as exc:
            last_exc = exc
            _remove_windows_reserved_files(task.workdir)
            if attempt < attempts - 1:
                time.sleep(delay_s * (attempt + 1))
    if os.name == "nt" and last_exc is not None:
        print(f"[ws] restore still locked ({last_exc.__class__.__name__}); "
              "killing leftover agent processes and retrying once")
        kill_agent_orphans()
        try:
            if task.workdir.exists():
                shutil.rmtree(task.workdir)
            shutil.copytree(pristine, task.workdir)
            return True
        except Exception as exc:
            last_exc = exc
    if last_exc is not None:
        raise last_exc
    return False


def safe_restore_workspace(task, attempts: int = 3) -> bool:
    """Case-3 workspace restoration with pruner-style backoff.

    Per FIX_BRIEF/spec §5.3: wrap cleanup + copy in a 3-attempt retry loop;
    on PermissionError invoke :func:`kill_agent_orphans`, pause
    ``2 ** attempt`` seconds, and retry. A broader exception (e.g. a
    permission error that persists even after the sweep) propagates after the
    last attempt.
    """
    for attempt in range(attempts):
        try:
            return restore_workspace(task, attempts=2, delay_s=0.5)
        except PermissionError:
            if attempt >= attempts - 1:
                raise
            print(
                f"[ws] workspace lock (attempt {attempt + 1}/"
                f"{attempts}); killing orphan agents and backing off "
                f"{2 ** attempt}s"
            )
            kill_agent_orphans()
            time.sleep(2 ** attempt)


def snapshot_pristine(task) -> bool:
    """Copy the current workdir into <task_id>/pristine (one-time setup for
    hand-authored datasets). Returns True when a snapshot was created."""
    if not task.workdir.is_dir():
        return False
    pristine = task.workdir.parent / "pristine"
    if pristine.is_dir():
        return False
    shutil.copytree(task.workdir, pristine)
    return True