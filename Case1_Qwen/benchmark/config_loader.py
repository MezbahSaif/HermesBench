"""Config loading: env-var expansion + Hermes install auto-detection.

The config ships with portable paths (e.g. `${LOCALAPPDATA}/hermes/...`) so
the same config.yaml works on any teammate's machine. If the resolved
Hermes paths don't exist, the loader tries to detect the install from
standard locations (Windows LOCALAPPDATA, Unix ~/.local/share) and falls
back to PATH lookup.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import yaml


def _expand(value):
    if isinstance(value, str):
        return os.path.expandvars(value)
    return value


def detect_hermes() -> tuple[str, str] | None:
    """Locate (executable, real_home) from standard install locations.

    Windows: %LOCALAPPDATA%/hermes/hermes-agent/venv/Scripts/hermes.exe
    Unix:    ~/.local/share/hermes/hermes-agent/venv/bin/hermes
    Fallback: `hermes` on PATH (real_home then derived from its venv).
    """
    local = os.environ.get("LOCALAPPDATA")
    if local:
        base = Path(local) / "hermes"
        exe = base / "hermes-agent" / "venv" / "Scripts" / "hermes.exe"
        if exe.exists():
            return str(exe), str(base)

    base = Path.home() / ".local" / "share" / "hermes"
    exe = base / "hermes-agent" / "venv" / "bin" / "hermes"
    if exe.exists():
        return str(exe), str(base)

    on_path = shutil.which("hermes")
    if on_path:
        p = Path(on_path).resolve()
        for root in (p.parents):
            if (root / "config.yaml").exists() or root.name == "hermes":
                return str(p), str(root)
        return str(p), str(p.parent.parent.parent)
    return None


def resolve_config(config: dict) -> dict:
    """Expand env vars in all values; auto-detect Hermes if paths missing."""
    out = {}
    for key, value in config.items():
        if isinstance(value, dict):
            out[key] = {k: _expand(v) for k, v in value.items()}
        else:
            out[key] = _expand(value)

    hermes = out.setdefault("hermes", {})
    if not Path(hermes.get("executable", "")).exists():
        detected = detect_hermes()
        if detected:
            hermes["executable"], hermes["real_home"] = detected
            print(f"[config] hermes auto-detected: {detected[0]}")
            print(f"[config] real home auto-detected: {detected[1]}")
    return out


def load_config(path: Path) -> dict:
    """Load + resolve a config file; warns (does not fail) on a missing
    Hermes install so --dry-run can still report the problem."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not raw:
        raw = {}
    config = resolve_config(raw)
    exe = Path(config.get("hermes", {}).get("executable", ""))
    if not exe.exists():
        print(
            "[config] WARNING: hermes executable not found at "
            f"{exe}\n"
            "[config] Install Hermes Agent first, or set "
            "`hermes.executable` / `hermes.real_home` in "
            "config/config.yaml to your machine's paths."
        )
    return config
