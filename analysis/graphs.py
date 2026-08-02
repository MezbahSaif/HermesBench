"""Matplotlib graphs for the HermesBench report.

All plots are saved under analysis/plots/<run_id>/ and can also be
regenerated from any metrics.csv via `graphs.py --csv <path>`.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from analysis import statistics as stats

METRIC_PLOTS = [
    # success_rate is plotted separately in plot_all (section 1, with CI bands)
    ("score", "Mean score by round", "mean score (0-1)", None, None),
    ("duration_s", "Mean execution time by round", "seconds", None, None),
    ("api_calls", "Mean API calls by round", "API calls", None, None),
    ("tool_call_log_events", "Mean tool-call events by round", "tool events", None, None),
    ("retry_log_events", "Mean retry events by round", "retry events", None, None),
    ("error_log_events", "Mean error events by round", "error events", None, None),
]

ARM_COLORS = {"treatment": "#1f77b4", "control": "#d62728"}
ARM_STYLES = {"treatment": "o-", "control": "s--"}


def _arm_palette(df: pd.DataFrame):
    arms = sorted(df["arm"].unique())
    return {a: (ARM_COLORS.get(a, f"C{i}"), ARM_STYLES.get(a, "o-"))
            for i, a in enumerate(arms)}


def plot_all(df: pd.DataFrame, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    palette = _arm_palette(df)
    arms = sorted(df["arm"].unique())

    # 1) success rate with CI bands (bootstrap over task-level passes)
    fig, ax = plt.subplots(figsize=(8, 5))
    for arm in arms:
        s = stats.per_round_series(df, arm, "success_rate")
        x = s["round"].tolist()
        y = s["success_rate"].tolist()
        lo, hi = [], []
        for r in s["round"].tolist():
            vals = df[(df["arm"] == arm) & (df["round"] == r)]["passed"] \
                .astype(float).tolist()
            if not vals:
                lo.append(float("nan")); hi.append(float("nan")); continue
            l, h = stats.bootstrap_ci(vals, n_iter=500)
            lo.append(l); hi.append(h)
        color, style = palette[arm]
        ax.plot(x, y, style, color=color, label=arm, markersize=6)
        ax.fill_between(x, lo, hi, color=color, alpha=0.12)
    ax.set_xlabel("Round"); ax.set_ylabel("Success rate")
    ax.set_title("Self-improvement: success rate across rounds")
    ax.set_ylim(-0.02, 1.05)
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout()
    p = out_dir / "success_rate_by_round.png"
    fig.savefig(p, dpi=150); plt.close(fig); saved.append(p)

    # 2) per-metric lines
    for metric, title, ylabel, lo, hi in METRIC_PLOTS:
        fig, ax = plt.subplots(figsize=(8, 5))
        for arm in arms:
            s = stats.per_round_series(df, arm, metric)
            x = s["round"].tolist()
            y = s[metric].tolist()
            color, style = palette[arm]
            ax.plot(x, y, style, color=color, label=arm, markersize=6)
        ax.set_xlabel("Round"); ax.set_ylabel(ylabel)
        ax.set_title(title)
        if lo is not None:
            ax.set_ylim(lo, hi)
        ax.legend(); ax.grid(alpha=0.3)
        fig.tight_layout()
        p = out_dir / f"{metric}_by_round.png"
        fig.savefig(p, dpi=150); plt.close(fig); saved.append(p)

    # 3) learning artifacts (skill files + memory bytes) for treatment
    if "treatment" in arms and "after_skill_files" in df.columns:
        tr = df[df["arm"] == "treatment"]
        fig, ax = plt.subplots(figsize=(8, 5))
        s = tr.groupby("round").agg(
            skills=("after_skill_files", "max"),
            mem=("after_memory_bytes", "max"),
        ).reset_index()
        ax2 = ax.twinx()
        ax.plot(s["round"], s["skills"], "o-", color=ARM_COLORS["treatment"],
                label="skill files in home")
        ax2.plot(s["round"], s["mem"], "s--", color="#2ca02c",
                 label="memory bytes in home")
        ax.set_xlabel("Round")
        ax.set_ylabel("skill files", color=ARM_COLORS["treatment"])
        ax2.set_ylabel("memory bytes", color="#2ca02c")
        ax.set_title("Learning-loop artifacts accumulating (treatment arm)")
        ax.grid(alpha=0.3)
        fig.tight_layout()
        p = out_dir / "learning_artifacts.png"
        fig.savefig(p, dpi=150); plt.close(fig); saved.append(p)

    # 4) score distribution boxplots per round/arm
    fig, axes = plt.subplots(1, max(len(arms), 1), figsize=(5 * len(arms), 5),
                             squeeze=False)
    for i, arm in enumerate(arms):
        ax = axes[0][i]
        sub = df[df["arm"] == arm]
        data = [
            pd.to_numeric(sub[sub["round"] == r]["score"], errors="coerce")
            .dropna().tolist()
            for r in sorted(df["round"].unique())
        ]
        if data:
            ax.boxplot(data, tick_labels=[f"R{r}" for r in sorted(df["round"].unique())])
        ax.set_title(arm); ax.set_ylabel("score"); ax.set_ylim(0, 1.05)
        ax.grid(alpha=0.3)
    fig.suptitle("Score distributions by round and arm")
    fig.tight_layout()
    p = out_dir / "score_distributions.png"
    fig.savefig(p, dpi=150); plt.close(fig); saved.append(p)

    # 5) recovery rate across rounds (failure -> success transitions)
    fig, ax = plt.subplots(figsize=(8, 5))
    for arm in arms:
        s = stats.recovery_rate_series(df, arm)
        color, style = palette[arm]
        ax.plot(s["round"], s["recovery_rate"], style, color=color,
                label=arm, markersize=6)
    ax.set_xlabel("Round"); ax.set_ylabel("recovery rate")
    ax.set_title("Recovery rate: % of previously-failed tasks now passing")
    ax.set_ylim(0, 1.05)
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout()
    p = out_dir / "recovery_rate_by_round.png"
    fig.savefig(p, dpi=150); plt.close(fig); saved.append(p)

    # 6) cumulative human interventions
    if "human_interventions" in df.columns:
        fig, ax = plt.subplots(figsize=(8, 5))
        width = 0.35
        rounds = sorted(df["round"].unique())
        positions = range(len(rounds))
        for i, arm in enumerate(arms):
            sub = df[df["arm"] == arm]
            counts = [sub[sub["round"] == r]["human_interventions"].sum()
                      for r in rounds]
            offset = (i - 0.5) * width
            ax.bar([p + offset for p in positions], counts, width,
                   label=arm, color=palette[arm][0], alpha=0.8)
        ax.set_xticks(list(positions))
        ax.set_xticklabels([f"R{r}" for r in rounds])
        ax.set_xlabel("Round"); ax.set_ylabel("human interventions (tasks)")
        ax.set_title("Human interventions per round (timeout/crash/failed)")
        ax.legend(); ax.grid(alpha=0.3, axis="y")
        fig.tight_layout()
        p = out_dir / "human_interventions_by_round.png"
        fig.savefig(p, dpi=150); plt.close(fig); saved.append(p)

    return saved


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="metrics.csv path")
    parser.add_argument("--out", default="analysis/plots", help="output dir")
    args = parser.parse_args()
    df = pd.read_csv(args.csv)
    saved = plot_all(df, Path(args.out))
    for p in saved:
        print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
