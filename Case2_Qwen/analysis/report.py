"""HermesBench final report: print the self-improvement verdict.

Reads a run's metrics.csv, recomputes the statistics, and prints a
plain-text conclusion for the thesis:

    python analysis/report.py                        # latest run
    python analysis/report.py --csv runs/<id>/metrics.csv

Exit code 0 = all claims unsupported, 1 = at least one supported metric.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis import statistics as stats  # noqa: E402

ALPHA = 0.05
IMPROVING_DIRECTIONS = {
    "score": "up", "success_rate": "up", "recovery_rate": "up",
    "duration_s": "down", "api_calls": "down",
    "tool_call_log_events": "down", "error_log_events": "down",
    "retry_log_events": "down", "reflection_log_events": "down",
    "human_interventions": "down",
}


def load_latest_metrics() -> Path:
    runs = sorted(
        [p for p in (Path(__file__).resolve().parent.parent / "runs").glob("*")
         if (p / "metrics.csv").exists()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not runs:
        raise SystemExit("No runs found. Run the benchmark first.")
    return runs[0] / "metrics.csv"


def report(df: pd.DataFrame) -> int:
    arms = sorted(df["arm"].unique())
    rounds_ran = sorted(df["round"].unique())
    print("=" * 72)
    print("HERMESBENCH - SELF-IMPROVEMENT VERDICT REPORT")
    print("=" * 72)
    print(f"run id        : {df['run_id'].iloc[0]}")
    print(f"arms          : {', '.join(arms)}")
    print(f"rounds        : {len(rounds_ran)}  ({rounds_ran[0]}..{rounds_ran[-1]})")
    print(f"tasks/round   : {df[df['round'] == rounds_ran[-1]]['task_id'].nunique()}")
    print(f"executions    : {len(df)}")
    print("-" * 72)

    if len(rounds_ran) < 5:
        print("! WARNING: fewer than 5 rounds -> Mann-Kendall cannot reach")
        print("  p<0.05 even for a perfect trend. Keep running more rounds.")
        print("-" * 72)

    rep = stats.compare_arms(df)
    rows = rep[rep["metric"] != "_note"]

    print()
    print("TREND (across rounds, Mann-Kendall tau / p; OLS slope p):")
    print(f"{'metric':<28}{'arm':<11}{'tau':>7}{'trend_p':>10}{'slope_p':>10}  verdict")
    print("-" * 72)
    verdicts = {}
    for metric in IMPROVING_DIRECTIONS:
        line = rows[rows["metric"] == metric]
        for arm in arms:
            sub = line[line["arm"] == arm]
            if sub.empty:
                continue
            r = sub.iloc[0]
            sig = bool(r["trend_significant"])
            improving = sig
            if sig:
                tau = float(r["tau"])
                direction = IMPROVING_DIRECTIONS[metric]
                improving = tau > 0 if direction == "up" else tau < 0
            print(
                f"{metric:<28}{arm:<11}"
                f"{r['tau']:>7.3f}{r['trend_p']:>10.3f}{r['slope_p']:>10.3f}"
                f"  {'IMPROVING' if improving else 'none'}"
            )
            verdicts.setdefault(metric, {})[arm] = improving

    print()
    print("FINAL-ROUND COMPARISON (treatment vs control, Welch t-test):")
    cmp_rows = rows[rows["arm"].str.contains(" vs ")]
    if not cmp_rows.empty:
        print(f"{'metric':<28}{'mean_diff':>12}{'cohens_d':>10}{'p':>10}  verdict")
        print("-" * 72)
        for _, r in cmp_rows.iterrows():
            sig = bool(r["trend_significant"])
            print(
                f"{r['metric']:<28}{r['mean']:>12.4f}{r['slope']:>10.3f}"
                f"{r['slope_p']:>10.3f}  {'treatment better' if sig else 'none'}"
            )
    else:
        print("  (only one arm ran - no comparison possible)")

    print()
    print("=" * 72)
    supported = []
    if len(arms) == 2:
        for metric, direction in IMPROVING_DIRECTIONS.items():
            tr = verdicts.get(metric, {}).get("treatment")
            co = verdicts.get(metric, {}).get("control")
            if tr is True and co is not True:
                supported.append(metric)
        if supported:
            print(f"CLAIM SUPPORTED for: {', '.join(supported)}")
            print("Treatment improved significantly across rounds where control")
            print("did not. NOTE: this supports the 'learning loop' claim for")
            print("these metrics - the model weights were never updated.")
            return 1
        print("CLAIM NOT SUPPORTED by this data: no metric improved")
        print("significantly in treatment without also improving in control.")
        print("This means the self-improvement claim is either false, too")
        print("small to detect, or needs more rounds/tasks.")
        return 0
    print("Run both arms (--arm both) to test the claim.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=None)
    args = parser.parse_args()
    path = Path(args.csv) if args.csv else load_latest_metrics()
    df = pd.read_csv(path)
    return report(df)


if __name__ == "__main__":
    raise SystemExit(main())
