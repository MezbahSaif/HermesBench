"""Statistics for the self-improvement evaluation.

The research question: "Does the treatment arm (learning loop ON) improve
across rounds, beyond what the control arm (learning loop reset) does?"

Tests provided:
  * mann_kendall(x)        - monotonic trend test per arm/metric
  * linear_trend(x)        - OLS slope, R2, p-value of the slope
  * welch_ttest(a, b)      - treatment vs control at the final round
  * bootstrap_ci(x, stat)  - non-parametric confidence intervals
  * compare_arms(df)       - end-to-end report over a metrics DataFrame
"""
from __future__ import annotations

import math
from itertools import combinations
from typing import Callable

import pandas as pd

from scipy import stats as sps

METRICS = [
    ("score", "mean score"),
    ("duration_s", "mean duration (s)"),
    ("api_calls", "mean API calls"),
    ("tool_call_log_events", "mean tool-call events"),
    ("error_log_events", "mean error events"),
    ("retry_log_events", "mean retry events"),
    ("reflection_log_events", "mean reflection events"),
    ("success_rate", "success rate"),
    ("recovery_rate", "recovery rate"),
    ("human_interventions", "human interventions"),
]


def mann_kendall(x: list[float]) -> tuple[float, float]:
    """Mann-Kendall trend test -> (tau, two-sided p-value).

    Pure-python implementation with the normal approximation and the
    continuity correction; handles ties via the standard variance formula.
    """
    n = len(x)
    if n < 3:
        return 0.0, 1.0
    s = 0
    for i, j in combinations(range(n), 2):
        s += (x[j] > x[i]) - (x[j] < x[i])
    # Ties -> variance reduction factor.
    tie = {}
    for v in x:
        tie[v] = tie.get(v, 0) + 1
    var = (
        n * (n - 1) * (2 * n + 5)
        - sum(t * (t - 1) * (2 * t + 5) for t in tie.values())
    ) / 18.0
    if var <= 0:
        return 0.0, 1.0
    z = (s - 1) / math.sqrt(var) if s > 0 else (s + 1) / math.sqrt(var)
    p = 2.0 * (1.0 - _normal_cdf(abs(z)))
    tau = 2 * s / (n * (n - 1))
    return tau, p


def _normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def linear_trend(x: list[float]) -> dict:
    """OLS slope of x vs index + R2 + slope p-value."""
    n = len(x)
    if n < 3:
        return {"slope": float("nan"), "r2": float("nan"), "p": 1.0}
    y = list(map(float, x))
    idx = list(range(n))
    res = sps.linregress(idx, y)
    return {
        "slope": res.slope,
        "r2": res.rvalue ** 2,
        "p": res.pvalue,
    }


def welch_ttest(a: list[float], b: list[float]) -> dict:
    import math as _m
    a = [float(v) for v in a if v is not None and _m.isfinite(float(v))]
    b = [float(v) for v in b if v is not None and _m.isfinite(float(v))]
    if len(a) < 2 or len(b) < 2:
        return {"t": float("nan"), "p": 1.0, "mean_a": float("nan"),
                "mean_b": float("nan"), "d": float("nan")}
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        t, p = sps.ttest_ind(a, b, equal_var=False)
    pooled = math.sqrt(
        (sum((v - (sa := sum(a) / len(a))) ** 2 for v in a)
         + sum((v - (sb := sum(b) / len(b))) ** 2 for v in b))
        / (len(a) + len(b) - 2)
    ) if len(a) + len(b) > 2 else 1.0
    d = (sum(a) / len(a) - sum(b) / len(b)) / (pooled or 1.0)
    return {"t": t, "p": p, "mean_a": sum(a) / len(a),
            "mean_b": sum(b) / len(b), "d": d}


def bootstrap_ci(x: list[float], stat: Callable = lambda v: sum(v) / len(v),
                 n_iter: int = 2000, alpha: float = 0.05,
                 rng_seed: int = 42) -> tuple[float, float]:
    """Bootstrap confidence interval for `stat` over `x`."""
    import random
    rng = random.Random(rng_seed)
    n = len(x)
    if n == 0:
        return float("nan"), float("nan")
    vals = [stat([rng.choice(x) for _ in range(n)]) for _ in range(n_iter)]
    vals.sort()
    lo = vals[int(round(alpha / 2 * n_iter))]
    hi = vals[int(round((1 - alpha / 2) * n_iter))]
    return lo, hi


# ---------------------------------------------------------------- data prep
def recovery_rate_series(df: pd.DataFrame, arm: str) -> pd.DataFrame:
    """Round-by-round recovery rate for one arm.

    recovery_rate(r) = (# tasks that failed in an earlier round and PASSED
    in round r) / (# tasks that had failed before r and appeared at r).

    A rising recovery rate across rounds is the strongest direct evidence of
    the learning loop fixing its own past failures.
    """
    sub = df[df["arm"] == arm].copy()
    sub["passed"] = sub["passed"].astype(bool)
    key = "family" if "family" in sub.columns else "task_id"
    rows = []
    pending: set = set()  # task families still in the failed state
    for r in sorted(sub["round"].unique()):
        cur = sub[sub["round"] == r]
        present = set(cur[key])
        passed_now = set(cur[cur["passed"]][key])
        failed_now = present - passed_now
        recoverable = pending & present
        recovered = recoverable & passed_now
        rate = float("nan")
        if recoverable:
            rate = len(recovered) / len(recoverable)
        rows.append({"round": r, "recovery_rate": rate,
                     "recoverable": len(recoverable),
                     "recovered": len(recovered)})
        pending = (pending - recovered) | failed_now
    return pd.DataFrame(rows)


def per_round_series(df: pd.DataFrame, arm: str, metric: str,
                     agg: str = "mean") -> pd.DataFrame:
    """Round-by-round aggregated series for one arm and metric."""
    if metric == "recovery_rate":
        return recovery_rate_series(df, arm)
    sub = df[df["arm"] == arm].copy()
    if metric == "success_rate":
        sub["_v"] = sub["passed"].astype(float)
    else:
        sub["_v"] = pd.to_numeric(sub[metric], errors="coerce")
    if agg == "mean":
        out = sub.groupby("round")["_v"].mean().reset_index()
    elif agg == "median":
        out = sub.groupby("round")["_v"].median().reset_index()
    else:
        raise ValueError(f"unknown agg {agg}")
    return out.rename(columns={"_v": metric})


# ------------------------------------------------------------------ report
def compare_arms(df: pd.DataFrame, alpha: float = 0.05) -> pd.DataFrame:
    """End-to-end statistical report over a full metrics DataFrame."""
    rows = []
    arms = sorted(df["arm"].unique(),
                  key=lambda a: (a != "treatment", a))  # treatment first
    for metric, label in METRICS:
        if metric not in df.columns and metric not in (
            "success_rate", "recovery_rate"
        ):
            continue  # column added in a later framework version
        for arm in arms:
            s = per_round_series(df, arm, metric)
            x = s[metric].dropna().tolist()
            if len(x) < 2:
                continue
            tau, p_trend = mann_kendall(x)
            trend = linear_trend(x)
            mean = sum(x) / len(x)
            lo, hi = bootstrap_ci(x)
            rows.append({
                "metric": metric,
                "label": label,
                "arm": arm,
                "rounds": len(x),
                "mean": round(mean, 4),
                "ci_lo": round(lo, 4),
                "ci_hi": round(hi, 4),
                "tau": round(tau, 4),
                "trend_p": round(p_trend, 4),
                "slope": round(trend["slope"], 4),
                "slope_r2": round(trend["r2"], 4),
                "slope_p": round(trend["p"], 4),
                "trend_significant": bool(
                    p_trend < alpha and abs(tau) > 0
                ),
            })
    # Power warning: with n < 5 rounds the Mann-Kendall normal
    # approximation cannot reach p < 0.05 even for a perfect trend.
    rounds_used = sorted(df["round"].unique())
    if len(rounds_used) < 5:
        rows.append({
            "metric": "_note",
            "label": (
                f"POWER WARNING: only {len(rounds_used)} round(s) ran. "
                "Mann-Kendall needs >= 5 rounds to reach p < 0.05 even for "
                "a perfect monotonic trend; run more rounds before "
                "concluding anything."
            ),
            "arm": "-", "rounds": len(rounds_used),
            "mean": float("nan"), "ci_lo": float("nan"),
            "ci_hi": float("nan"), "tau": float("nan"),
            "trend_p": float("nan"), "slope": float("nan"),
            "slope_r2": float("nan"), "slope_p": float("nan"),
            "trend_significant": False,
        })
    # Pairwise treatment vs control on the FINAL round (head-to-head).
    if len(arms) == 2:
        last = df["round"].max()
        for metric, label in METRICS:
            a = df[(df["arm"] == arms[0]) & (df["round"] == last)]
            b = df[(df["arm"] == arms[1]) & (df["round"] == last)]
            if metric == "success_rate":
                va = a["passed"].astype(float).tolist()
                vb = b["passed"].astype(float).tolist()
            elif metric == "recovery_rate":
                continue  # derived per-round series; no per-task values
            elif metric in df.columns:
                va = pd.to_numeric(a[metric], errors="coerce").tolist()
                vb = pd.to_numeric(b[metric], errors="coerce").tolist()
            else:
                continue  # column added in a later framework version
            t = welch_ttest(va, vb)
            rows.append({
                "metric": metric,
                "label": f"final-round {label}",
                "arm": f"{arms[0]} vs {arms[1]}",
                "rounds": last,
                "mean": round(t["mean_a"] - t["mean_b"], 4),
                "ci_lo": float("nan"), "ci_hi": float("nan"),
                "tau": float("nan"), "trend_p": float("nan"),
                "slope": round(t["d"], 4), "slope_r2": float("nan"),
                "slope_p": round(t["p"], 4),
                "trend_significant": bool(
                    t["p"] < alpha and abs(t["d"]) > 0.2
                ),
            })
    return pd.DataFrame(rows)
