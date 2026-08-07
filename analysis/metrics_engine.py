"""HermesBench metrics engine: turns raw metrics into all report artifacts.

Pipeline stage after the deterministic graders:

    metrics.csv (raw rows)
        -> results.xlsx (metrics, summary, improvement, gain, families,
                         regression, trends, recovery sheets)
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


def _task_key(df: pd.DataFrame) -> str:
    return "family" if "family" in df.columns else "task_id"


def build_improvement(df: pd.DataFrame) -> pd.DataFrame:
    """Per-arm, per-round aggregates with deltas vs round 1 (improvement rate)."""
    if df.empty or "passed" not in df.columns:
        return pd.DataFrame()
    rows = []
    for arm in sorted(df["arm"].unique()):
        sub = df[df["arm"] == arm]
        by_round = {}
        for r in sorted(sub["round"].unique()):
            cur = sub[sub["round"] == r]
            by_round[r] = {
                "mean_score": (cur["score"].mean()
                               if "score" in cur.columns else float("nan")),
                "success_rate": cur["passed"].astype(bool).mean(),
            }
        first = min(by_round)
        base_score, base_succ = by_round[first]["mean_score"], by_round[first]["success_rate"]
        for r in sorted(by_round):
            rows.append({
                "arm": arm,
                "round": r,
                "mean_score": round(float(by_round[r]["mean_score"]), 4),
                "success_rate": round(float(by_round[r]["success_rate"]), 4),
                "score_gain_vs_round1": round(
                    float(by_round[r]["mean_score"] - base_score), 4),
                "success_gain_vs_round1": round(
                    float(by_round[r]["success_rate"] - base_succ), 4),
            })
    return pd.DataFrame(rows)


def build_gain(df: pd.DataFrame) -> pd.DataFrame:
    """Treatment minus control per round (success rate, mean score) + Welch p."""
    if df.empty or "passed" not in df.columns:
        return pd.DataFrame()
    arms = [a for a in ("treatment", "control") if a in set(df["arm"])]
    if len(arms) < 2:
        return pd.DataFrame()
    tr, co = arms
    rows = []
    for r in sorted(df["round"].unique()):
        sub_tr = df[(df["arm"] == tr) & (df["round"] == r)]
        sub_co = df[(df["arm"] == co) & (df["round"] == r)]
        succ_tr = sub_tr["passed"].astype(bool).mean()
        succ_co = sub_co["passed"].astype(bool).mean()
        score_tr = sub_tr["score"].mean() if "score" in df.columns else float("nan")
        score_co = sub_co["score"].mean() if "score" in df.columns else float("nan")
        p = stats.welch_ttest(
            sub_tr["passed"].astype(float).tolist(),
            sub_co["passed"].astype(float).tolist())["p"]
        rows.append({
            "round": r,
            "treatment_success_rate": round(float(succ_tr), 4),
            "control_success_rate": round(float(succ_co), 4),
            "success_gain_tr_minus_co": round(float(succ_tr - succ_co), 4),
            "treatment_mean_score": round(float(score_tr), 4),
            "control_mean_score": round(float(score_co), 4),
            "score_gain_tr_minus_co": round(float(score_tr - score_co), 4),
            "welch_p_success": round(float(p), 4),
        })
    return pd.DataFrame(rows)


def build_family_accuracy(df: pd.DataFrame) -> pd.DataFrame:
    """Accuracy per arm x round x task family (where improvement happens)."""
    if df.empty or "passed" not in df.columns:
        return pd.DataFrame()
    key = _task_key(df)
    g = df.groupby(["arm", "round", key])["passed"] \
        .agg(["count", "mean"]).reset_index()
    return g.rename(columns={"count": "n_tasks", "mean": "accuracy"})


def build_regression(df: pd.DataFrame) -> pd.DataFrame:
    """Per-arm, per-round regression rate: tasks that PASSED the previous
    round but FAILED the current one (stability check; the mirror of
    recovery). Also reports the recovered rate for contrast."""
    if df.empty or "passed" not in df.columns:
        return pd.DataFrame()
    key = _task_key(df)
    rows = []
    for arm in sorted(df["arm"].unique()):
        sub = df[df["arm"] == arm].copy()
        sub["passed"] = sub["passed"].astype(bool)
        prev_state = None  # (passed_set, present_set) of the previous round
        for r in sorted(sub["round"].unique()):
            cur = sub[sub["round"] == r]
            present = set(cur[key])
            passed_now = set(cur[cur["passed"]][key])
            regressed = recovered = float("nan")
            n_regressed = n_recovered = 0
            if prev_state is not None:
                p_passed, p_present = prev_state
                both = present & p_present
                if both:
                    regressed = (p_passed & (present - passed_now))
                    recovered = ((p_present - p_passed) & passed_now)
                    n_regressed, n_recovered = len(regressed), len(recovered)
                    regressed = n_regressed / len(both)
                    recovered = n_recovered / len(both)
            rows.append({
                "arm": arm, "round": r,
                "n_regressed": n_regressed, "n_recovered": n_recovered,
                "regression_rate": (round(float(regressed), 4)
                                    if regressed == regressed else None),
                "recovered_rate": (round(float(recovered), 4)
                                   if recovered == recovered else None),
            })
            prev_state = (passed_now, present)
    return pd.DataFrame(rows)


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


def _tier_names(df: pd.DataFrame) -> list[str]:
    """Tier slices present in the data, 'all' first (whole-dataset verdict)."""
    if "tier" not in df.columns:
        return ["all"]
    tiers = [t for t in ("Repeat", "Variant", "New")
             if t in set(df["tier"].dropna())]
    return ["all"] + tiers


# ---------------------------------------------------------------- case 3
# Spec §8.1 metrics. The binary "pass" for Case 3 is a PERFECT score (1.0):
# the quality-gated hook persists lessons only from flawless solutions, so the
# claim being tested is "treatment reaches 100% more often than control as
# rounds accumulate".

def _is_mask(df: pd.DataFrame) -> pd.Series:
    """True where the task scored a perfect 1.0 (Case-3 'pass')."""
    return (
        pd.to_numeric(df["score"], errors="coerce").fillna(0.0) >= 1.0
        if "score" in df.columns
        else pd.Series([False] * len(df), index=df.index)
    )


def pass_rate_per_round(df: pd.DataFrame, arm: str) -> pd.DataFrame:
    """PassRate_r = (# tasks with score == 1.0 in round r) / (tasks in r)."""
    sub = df[df["arm"] == arm].copy()
    if sub.empty:
        return pd.DataFrame()
    sub["_pass"] = _is_mask(sub).astype(float)
    out = sub.groupby("round")["_pass"].agg(["count", "mean"]).reset_index()
    return out.rename(columns={"count": "n_tasks", "mean": "pass_rate"})


def delta_pass(df: pd.DataFrame, threshold: float = 0.05) -> float:
    """ΔPass = PassRate(treatment, R5) - PassRate(control, R5).

    NaN when either arm is missing its final round.
    """
    last = df["round"].max() if "round" in df.columns else None
    if last is None:
        return float("nan")
    rates = {}
    for arm in ("treatment", "control"):
        pr = pass_rate_per_round(df, arm)
        if pr.empty or not (pr["round"] == last).any():
            return float("nan")
        rates[arm] = float(pr.loc[pr["round"] == last, "pass_rate"].iloc[0])
    return rates["treatment"] - rates["control"]


def variant_transfer_rate(df: pd.DataFrame, arm: str) -> float:
    """VTR = pass rate on tier == 'Variant' tasks for an arm.

    NaN when the frame has no tier column (pre-case-3 runs) or no Variant rows.
    """
    sub = df[df["arm"] == arm]
    if sub.empty or "tier" not in df.columns:
        return float("nan")
    sub = sub[sub["tier"].eq("Variant")]
    if sub.empty:
        return float("nan")
    return float(_is_mask(sub).mean())


def fisher_exact_final(df: pd.DataFrame) -> dict:
    """Fisher's exact test, 2x2, final round: [treatment pass/fail,
    control pass/fail]. Returns oddsratio + p (two-sided)."""
    last = df["round"].max() if "round" in df.columns else None
    if last is None:
        return {"oddsratio": float("nan"), "p": 1.0}
    fin = df[df["round"] == last]
    tr = fin[fin["arm"] == "treatment"]
    co = fin[fin["arm"] == "control"]
    if tr.empty or co.empty:
        return {"oddsratio": float("nan"), "p": 1.0}
    tr_pass = int(_is_mask(tr).sum())
    co_pass = int(_is_mask(co).sum())
    table = [[tr_pass, len(tr) - tr_pass],
             [co_pass, len(co) - co_pass]]
    from scipy.stats import fisher_exact
    oddsratio, p = fisher_exact(table, alternative="two-sided")
    return {"oddsratio": float(oddsratio), "p": float(p),
            "treatment_pass": tr_pass, "treatment_total": len(tr),
            "control_pass": co_pass, "control_total": len(co)}


def skill_utility_ratio(df: pd.DataFrame) -> float:
    """SUR = skills persisted on PASSED tasks / total skills persisted.

    Proxy definition (metrics.csv has no per-retrieval column, so):
      * numerator   = sum of (after_skill_files - before_skill_files) on
        passed treatment tasks (skills written by the reflection hook after
        a flawless solve);
      proxy definition (metrics.csv has no per-retrieval column, so):
      * numerator   = sum of (after_skill_files - before_skill_files) on
        passed treatment tasks (skills written by the reflection hook after
        a flawless solve);
      * denominator = peak after_skill_files across the treatment arm
        (total skills in memory at the end of the run).
    The ratio is clamped to [0, 100] since the coarse per-task deltas can
    over-count skills touched by several passed tasks in the same round.
    """
    tr = df[df["arm"] == "treatment"]
    if tr.empty:
        return float("nan")
    if "after_skill_files" not in df.columns \
            or "before_skill_files" not in df.columns:
        return float("nan")
    passed = tr[_is_mask(tr)]
    before = pd.to_numeric(passed["before_skill_files"], errors="coerce")
    after = pd.to_numeric(passed["after_skill_files"], errors="coerce")
    num = float((after - before).sum() or 0.0)
    denom = float(pd.to_numeric(tr["after_skill_files"],
                                errors="coerce").fillna(0.0).max() or 0.0)
    if denom <= 0:
        return float("nan")
    return min(100.0, max(0.0, num / denom * 100.0))


def case3_verdict(df: pd.DataFrame, delta_threshold: float = 0.05,
                  alpha: float = 0.05) -> dict:
    """Spec §8.2 verdict. YES only if ΔPass >= +5% AND Fisher p < 0.05.

    Returns the parsed numbers + the exact console string from the spec.
    """
    delta = delta_pass(df)
    fisher = fisher_exact_final(df)
    yes = (delta == delta and delta >= delta_threshold
           and fisher["p"] < alpha)
    if yes:
        text = ("VERDICT: YES (Hermes Agent natively self-improves "
                "under quality gates)")
    else:
        text = ("VERDICT: NO (Self-improvement hypothesis rejected; "
                "performance remains flat)")
    return {
        "delta_pass": delta,
        "delta_threshold": delta_threshold,
        "fisher_p": fisher["p"],
        "alpha": alpha,
        "fisher": fisher,
        "vtr_treatment": variant_transfer_rate(df, "treatment"),
        "vtr_control": variant_transfer_rate(df, "control"),
        "sur": skill_utility_ratio(df),
        "verdict": text,
    }


def verdict_by_tier(df: pd.DataFrame) -> dict:
    """Whole-dataset verdict plus one verdict per tier slice.

    Tier semantics (case-2 design):
      Repeat -> memorization (same task every round)
      Variant -> transfer (unseen inputs of a practiced family)
      New -> specificity control (families never practiced; should stay flat)
    """
    return {
        tier: verdict(df if tier == "all" else df[df["tier"] == tier])
        for tier in _tier_names(df)
    }


def tier_verdict_table(vt: dict) -> pd.DataFrame:
    """Compact tier x metric table for the Excel 'tier_verdict' sheet."""
    rows = []
    for tier, v in vt.items():
        for metric in IMPROVING_DIRECTIONS:
            tr = v["per_metric"].get(metric, {}).get("treatment")
            co = v["per_metric"].get(metric, {}).get("control")
            rows.append({
                "tier": tier,
                "metric": metric,
                "treatment_improving": bool(tr),
                "control_improving": bool(co),
                "supported": metric in v["supported_metrics"],
            })
    return pd.DataFrame(rows)


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


def print_tier_verdicts(vt: dict, df: pd.DataFrame) -> None:
    """Console section: whole verdict + one verdict per tier slice."""
    if len(vt) == 1:
        return  # no tier column (e.g. other_run) - whole verdict only
    print("=" * 72)
    print("VERDICT BY TIER")
    print("  Repeat  = memorization (same task every round)")
    print("  Variant = transfer (unseen inputs, practiced family)")
    print("  New     = specificity control (never-practiced families)")
    print("=" * 72)
    for tier, v in vt.items():
        sub = df if tier == "all" else df[df["tier"] == tier]
        print(f"\n--- tier={tier} ({len(sub)} executions) ---")
        for metric in IMPROVING_DIRECTIONS:
            line = v["statistics"][v["statistics"]["metric"] == metric]
            if line.empty:
                continue
            cells = []
            for arm in v["arms"]:
                sub_line = line[line["arm"] == arm]
                if sub_line.empty:
                    continue
                r = sub_line.iloc[0]
                tag = "IMPROVING" if v["per_metric"][metric].get(arm) else "none"
                cells.append(f"{arm}: tau={r['tau']:.3f} p={r['trend_p']:.3f} {tag}")
            print(f"  {metric:<24} " + " | ".join(cells))
        print("  " + (f"SUPPORTED: {', '.join(v['supported_metrics'])}"
                      if v["supported_metrics"]
                      else "not supported (or insufficient rounds)"))


def build_case3_table(df: pd.DataFrame, delta_threshold: float = 0.05,
                      alpha: float = 0.05) -> pd.DataFrame:
    """Case-3 (§8) metric table for the Excel 'case3' sheet."""
    c3 = case3_verdict(df, delta_threshold, alpha)
    rows = [{"metric": "PassRate treatment (final round)",
             "value": pass_rate_per_round(df, "treatment")},
            {"metric": "PassRate control (final round)",
             "value": pass_rate_per_round(df, "control")},
            {"metric": "DeltaPass (treatment - control)",
             "value": c3["delta_pass"]},
            {"metric": "Fisher exact p (final round)",
             "value": c3["fisher_p"]},
            {"metric": "Fisher odds ratio", "value": c3["fisher"]["oddsratio"]},
            {"metric": "VTR treatment", "value": c3["vtr_treatment"]},
            {"metric": "VTR control", "value": c3["vtr_control"]},
            {"metric": "SUR (skill utility ratio)", "value": c3["sur"]},
            {"metric": "Verdict", "value": c3["verdict"]},
            ]
    out = pd.DataFrame(rows)
    return out


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
            for name, frame in (
                ("summary", build_summary(df)),
                ("improvement", build_improvement(df)),
                ("gain", build_gain(df)),
                ("families", build_family_accuracy(df)),
                ("regression", build_regression(df)),
            ):
                if frame is not None and not frame.empty:
                    frame.to_excel(writer, sheet_name=name, index=False)
            v = verdict(df)
            v["statistics"].to_excel(writer, sheet_name="trends", index=False)
            vt = verdict_by_tier(df)
            tier_verdict_table(vt).to_excel(
                writer, sheet_name="tier_verdict", index=False)
            build_recovery(df).to_excel(writer, sheet_name="recovery",
                                        index=False)
            build_case3_table(df).to_excel(writer, sheet_name="case3",
                                           index=False)
    except Exception as exc:
        xlsx_path = None
        if not quiet:
            print(f"xlsx write skipped: {exc}")

    plots = plot_all(df, run_dir / "plots")

    v = verdict(df)
    vt = verdict_by_tier(df)
    if not quiet:
        print_verdict(v, df)
        print_tier_verdicts(vt, df)
        imp = build_improvement(df)
        if not imp.empty:
            last = imp["round"].max()
            for arm in v["arms"]:
                row = imp[(imp["arm"] == arm) & (imp["round"] == last)]
                if row.empty:
                    continue
                r = row.iloc[0]
                print(f"[delta] {arm}: round {last} vs round 1 "
                      f"score {r['score_gain_vs_round1']:+.3f}, "
                      f"success {r['success_gain_vs_round1']:+.1%}")
        g = build_gain(df)
        if not g.empty:
            fin = g[g["round"] == g["round"].max()].iloc[0]
            print(f"[gain] final round treatment-control: "
                  f"success {fin['success_gain_tr_minus_co']:+.1%} "
                  f"(p={fin['welch_p_success']:.3f}), "
                  f"score {fin['score_gain_tr_minus_co']:+.3f}")

    return {
        "metrics_csv": str(csv_path),
        "xlsx": str(xlsx_path) if xlsx_path else None,
        "plots": [str(p) for p in plots],
        "verdict": v,
        "verdict_by_tier": vt,
        "case3_verdict": case3_verdict(df),
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
