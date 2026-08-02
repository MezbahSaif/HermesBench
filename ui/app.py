r"""HermesBench Streamlit dashboard.

Run with:  .venv\Scripts\streamlit run ui\app.py

The UI spawns benchmark/run_benchmark.py as a subprocess, then shows live
progress, metrics, statistics, and graphs. All data lives on disk
(metrics.csv / results.xlsx / progress.json), so the UI is purely a viewer
plus a launcher.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
import streamlit as st

BENCH_ROOT = Path(__file__).resolve().parent.parent
PYTHON = str(BENCH_ROOT / ".venv" / "Scripts" / "python.exe")
RUNNER = str(BENCH_ROOT / "benchmark" / "run_benchmark.py")
CONFIG = str(BENCH_ROOT / "config" / "config.yaml")
ACTIVE_RUN_FILE = BENCH_ROOT / "ui" / ".active_run"

st.set_page_config(page_title="HermesBench", page_icon="⚕", layout="wide")

sys.path.insert(0, str(BENCH_ROOT))


def latest_run_id() -> str | None:
    runs = sorted(
        [p for p in (BENCH_ROOT / "runs").glob("*") if (p / "metrics.csv").exists()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return runs[0].name if runs else None


def read_progress(run_id: str) -> dict | None:
    p = BENCH_ROOT / "runs" / run_id / "progress.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def read_metrics(run_id: str) -> pd.DataFrame | None:
    p = BENCH_ROOT / "runs" / run_id / "metrics.csv"
    if not p.exists():
        return None
    try:
        return pd.read_csv(p)
    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        return None


def is_running() -> bool:
    if not ACTIVE_RUN_FILE.exists():
        return False
    data = json.loads(ACTIVE_RUN_FILE.read_text(encoding="utf-8"))
    if data.get("pid"):
        import ctypes
        try:
            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False,
                                                        int(data["pid"]))
        except Exception:
            return False
        if not handle:
            ACTIVE_RUN_FILE.unlink(missing_ok=True)
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    return False


def write_active(pid: int) -> None:
    ACTIVE_RUN_FILE.write_text(json.dumps({"pid": pid}), encoding="utf-8")


# ----------------------------------------------------------------------------
st.title("⚕ HermesBench")
st.caption(
    "Benchmark framework: does Hermes Agent measurably self-improve across "
    "repeated runs (learning loop ON) vs a control arm (state reset)?"
)

running = is_running()
active_run = latest_run_id()

with st.sidebar:
    st.header("Configuration")
    from benchmark.config_loader import load_config
    cfg = load_config(Path(CONFIG))

    dataset = st.selectbox(
        "Dataset",
        sorted(
            p.relative_to(BENCH_ROOT / "datasets").as_posix()
            for p in (BENCH_ROOT / "datasets").rglob("*.csv")
        ),
        index=0,
    )
    rounds = st.slider("Rounds", 1, 10, int(cfg["benchmark"].get("rounds", 3)))
    arm = st.selectbox("Arm", ["both", "treatment", "control"], index=0)
    use_judge = st.checkbox("Use LLM judge (lm_judge tasks)", value=True)
    threshold = st.number_input(
        "Pass threshold", 0.0, 1.0,
        float(cfg["benchmark"].get("pass_threshold", 0.7)), 0.05,
    )

    st.divider()
    st.markdown("**Environment**")
    st.text(f"Model: {cfg['hermes'].get('model') or 'config default'}")
    st.text(f"Provider: {cfg['hermes'].get('provider') or 'config default'}")
    st.text(f"Judge: {cfg['lmstudio'].get('judge_model') or 'same model'}")

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        start = st.button("Start", disabled=running, use_container_width=True)
    with col2:
        resume = st.button("Resume", disabled=running, use_container_width=True)
    dry = st.button("Dry run", disabled=running, use_container_width=True)
    if running:
        st.warning("Benchmark is running...")

# ----------------------------------------------------------------------------
def launch(extra: list[str]) -> None:
    cmd = [PYTHON, RUNNER, "--config", CONFIG, "--dataset", f"datasets/{dataset}",
           "--rounds", str(rounds), "--arm", arm]
    if not use_judge:
        cmd += ["--no-judge"]
    cmd += extra
    proc = subprocess.Popen(cmd, cwd=str(BENCH_ROOT),
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    write_active(proc.pid)
    st.rerun()


def latest_run_dir() -> Path | None:
    runs = sorted(
        [p for p in (BENCH_ROOT / "runs").glob("*")
         if (p / "metrics.csv").exists() or (p / "progress.json").exists()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return runs[0] if runs else None


if start:
    launch([])
if resume:
    prev = latest_run_dir()
    if prev:
        launch(["--resume", "--run-id", prev.name])
    else:
        st.error("Nothing to resume - no previous run found.")
if dry:
    launch(["--dry-run"])

# ----------------------------------------------------------------------------
if active_run:
    run_dir = BENCH_ROOT / "runs" / active_run
    progress = read_progress(active_run)
    metrics = read_metrics(active_run)

    st.subheader(f"Run: `{active_run}`")

    if progress:
        r, t = progress.get("round", 0), progress.get("total_tasks", 1)
        i = progress.get("task_index", 0)
        st.progress(min(i / t, 1.0), text=f"{progress.get('phase', '')} "
                                          f"{progress.get('detail', '')} "
                                          f"({i}/{t})")
        st.caption(
            f"Round {r}/{progress.get('rounds', 1)} · "
            f"{'RUNNING' if running else 'stopped'}"
        )

    if metrics is not None and not metrics.empty:
        st.markdown("### Headline metrics (latest round)")
        df = metrics
        last_round = int(df["round"].max())
        last = df[df["round"] == last_round]
        cols = st.columns(2 * len(sorted(last["arm"].unique())))
        for j, arm_name in enumerate(sorted(last["arm"].unique())):
            sub = last[last["arm"] == arm_name]
            cols[2 * j].metric(f"{arm_name} · success rate",
                               f"{sub['passed'].mean() * 100:.1f}%",
                               f"n={len(sub)}")
            cols[2 * j + 1].metric(
                f"{arm_name} · mean duration",
                f"{sub['duration_s'].mean():.1f}s",
            )

        tab1, tab2, tab3, tab4 = st.tabs(
            ["Metrics table", "Summary", "Statistics", "Graphs"]
        )
        with tab1:
            st.dataframe(df, use_container_width=True, height=420)
        with tab2:
            from benchmark.benchmark_runner import BenchmarkRunner
            summary = BenchmarkRunner.summary_table(df)
            st.dataframe(summary, use_container_width=True)
        with tab3:
            from analysis.statistics import compare_arms
            rep = compare_arms(df)
            st.dataframe(rep, use_container_width=True, height=400)
            if not rep.empty:
                sig = rep[rep["trend_significant"]]
                st.info(
                    "Mann-Kendall tau + p per arm/metric (trend across "
                    "rounds); final-round Welch t-test (slope = Cohen's d). "
                    "A p < 0.05 with tau pointing in the improving direction "
                    "supports the self-improvement claim for that metric."
                )
        with tab4:
            from analysis.graphs import plot_all
            plot_dir = run_dir / "plots"
            plot_all(df, plot_dir)
            pngs = sorted(plot_dir.glob("*.png"))
            if pngs:
                cols = st.columns(2)
                for i, p in enumerate(pngs):
                    with cols[i % 2]:
                        st.image(str(p), caption=p.stem)
        st.download_button(
            "Download metrics.csv", df.to_csv(index=False),
            file_name=f"{active_run}_metrics.csv", mime="text/csv",
        )
        xlsx = run_dir / "results.xlsx"
        if xlsx.exists():
            st.download_button(
                "Download results.xlsx", xlsx.read_bytes(),
                file_name=f"{active_run}_results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    else:
        st.info("No metrics yet for this run.")
else:
    st.info("No benchmark runs found yet. Configure and press Start.")
