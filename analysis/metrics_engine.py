"""HermesBench metrics engine: turns raw metrics into all report artifacts.

Pipeline stage after the deterministic graders:

    metrics.csv (raw rows)
        -> results.xlsx (metrics, summary, trends, recovery sheets)
        -> plots/       (PNGs per metric, per arm)
        -> console verdict (compact)

Everything is derived from the same metrics.csv, so the stage is idempotent
and can be re-run on any existing run:

    python analysis/metrics_engine.py --csv runs/<run_id>/metrics.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis import statistics as stats  # noqa: E402
from analysis.graphs import plot_all  # noqa: E402

IMPROVING_DIRECTIONS = {
    "score": "up", "success_rate": "up", "recovery_rate": "up",
    "duration_s": "down", "api_calls": "down",
    "tool_call_log_events": "down", "error_log_events": "down",
    "retry_log_events": "down", "reflection_log_events": "down",
    "human_interventions": "down",
}

ALPHA = 0.05


def build_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Round x arm aggregate table (also used by the Excel 'summary' sheet)."""
    if df.empty:
        return pd.DataFrame()
    aggs = {
        "n_tasks": ("task_id", "count"),
        "success_rate": ("passed", "mean"),
        "mean_score": ("score", "mean"),
        "mean_duration_s": ("duration_s", "mean"),
        "mean_api_calls": ("api_calls", "mean"),
        "mean_tool_events": ("tool_call_log_events", "mean"),
        "mean_error_events": ("error_log_events", "mean"),
        "mean_retry_events": ("retry_log_events", "mean"),
        "human_interventions": ("human_interventions", "sum"),
        "total_skill_files": ("after_skill_files", "max"),
        "total_memory_bytes": ("after_memory_bytes", "max"),
    }
    aggs = {k: v for k, v in aggs.items() if v[0] in df.columns}
    return (
        df.groupby(["round", "arm"])
        .agg(**aggs)
        .reset_index()
    )


def build_recovery(df: pd.DataFrame) -> pd.DataFrame:
    """Wide recovery-rate table: one column per arm, one row per round."""
    arms = [a for a in sorted(df["arm"].unique()) if a not in (None, "")]
    if not arms or df.empty:
        return pd.DataFrame()
    frames = []
    for arm in arms:
        s = stats.recovery_rate_series(df, arm)
        s = s[["round", "recovery_rate"]].rename(
            columns={"recovery_rate": f"{arm}_recovery_rate"})
        frames.append(s)
    out = frames[0]
    for f in frames[1:]:
        out = out.merge(f, on="round", how="outer")
    return out


def verdict(df: pd.DataFrame) -> dict:
    """Compute the thesis verdict: which metrics support the claim."""
    rep = stats.compare_arms(df, alpha=ALPHA)
    arms = sorted(df["arm"].unique())
    rows = rep[rep["metric"] != "_note"]
    per_metric: dict[str, dict[str, bool]] = {}
    for metric in IMPROVING_DIRECTIONS:
        per_metric[metric] = {}
        line = rows[rows["metric"] == metric]
        for arm in arms:
            sub = line[line["arm"] == arm]
            improving = False
            if not sub.empty:
                r = sub.iloc[0]
                if bool(r["trend_significant"]):
                    tau = float(r["tau"])
                    direction = IMPROVING_DIRECTIONS[metric]
                    improving = tau > 0 if direction == "up" else tau < 0
            per_metric[metric][arm] = improving
    supported = []
    if len(arms) == 2:
        for metric, arm_verdicts in per_metric.items():
            tr = arm_verdicts.get("treatment")
            co = arm_verdicts.get("control")
            if tr is True and co is not True:
                supported.append(metric)
    return {
        "arms": arms,
        "supported_metrics": supported,
        "per_metric": per_metric,
        "statistics": rep,
    }


def print_verdict(v: dict, df: pd.DataFrame) -> None:
    print("=" * 72)
    print("METRICS ENGINE - VERDICT")
    print("=" * 72)
    print(f"run id      : {df['run_id'].iloc[0]}")
    print(f"arms        : {', '.join(v['arms'])}")
    rounds_ran = sorted(df["round"].unique())
    print(f"rounds      : {len(rounds_ran)} ({rounds_ran[0]}..{rounds_ran[-1]})")
    print(f"executions  : {len(df)}")
    print("-" * 72)
    rows = v["statistics"]
    for metric, dirn in IMPROVING_DIRECTIONS.items():
        line = rows[rows["metric"] == metric]
        if line.empty:
            continue
        cells = []
        for arm in v["arms"]:
            sub = line[line["arm"] == arm]
            if sub.empty:
                continue
            r = sub.iloc[0]
            tag = "IMPROVING" if v["per_metric"][metric].get(arm) else "none"
            cells.append(f"{arm}: tau={r['tau']:.3f} p={r['trend_p']:.3f} {tag}")
        print(f"{metric:<26} " + " | ".join(cells))
    print("-" * 72)
    if v["supported_metrics"]:
        print(f"CLAIM SUPPORTED for: {', '.join(v['supported_metrics'])}")
    else:
        print("CLAIM NOT SUPPORTED by this data (or fewer than 5 rounds / "
              "single arm).")
    print("=" * 72)


def generate_outputs(df: pd.DataFrame, run_dir: Path,
                     quiet: bool = False) -> dict:
    """Full metrics stage: csv + xlsx + plots + verdict.

    Returns {"metrics_csv", "xlsx", "plots", "verdict"} paths/objects.
    """
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    csv_path = run_dir / "metrics.csv"
    df.to_csv(csv_path, index=False)

    xlsx_path = run_dir / "results.xlsx"
    try:
        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="metrics", index=False)
            build_summary(df).to_excel(writer, sheet_name="summary",
                                       index=False)
            v = verdict(df)
            v["statistics"].to_excel(writer, sheet_name="trends", index=False)
            build_recovery(df).to_excel(writer, sheet_name="recovery",
                                        index=False)
    except Exception as exc:
        xlsx_path = None
        if not quiet:
            print(f"xlsx write skipped: {exc}")

    plots = plot_all(df, run_dir / "plots")

    v = verdict(df)
    if not quiet:
        print_verdict(v, df)

    return {
        "metrics_csv": str(csv_path),
        "xlsx": str(xlsx_path) if xlsx_path else None,
        "plots": [str(p) for p in plots],
        "verdict": v,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Metrics engine: regenerate all artifacts from a "
                    "metrics.csv")
    parser.add_argument("--csv", default=None,
                        help="metrics.csv path (default: latest run)")
    parser.add_argument("--out", default=None,
                        help="output dir (default: same as the CSV's run dir)")
    args = parser.parse_args()
    if args.csv:
        path = Path(args.csv)
    else:
        from analysis.report import load_latest_metrics
        path = load_latest_metrics()
    df = pd.read_csv(path)
    out = Path(args.out) if args.out else path.parent
    res = generate_outputs(df, out)
    print(f"csv   : {res['metrics_csv']}")
    print(f"xlsx  : {res['xlsx']}")
    print(f"plots : {len(res['plots'])} pngs -> {out / 'plots'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
