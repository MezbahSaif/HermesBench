"""Build the three-tier benchmark datasets (Repeat / Variant / New).

Design intent (so the professor gets the right comparison per round):
  - Repeat : the SAME task_id, verbatim, every round.
             If memory write/read works, these must improve (caching sanity).
  - Variant: same family, DIFFERENT instance inputs each round.
             Transfer test: does the learned procedure apply to unseen inputs?
             CONSTRAINED to strict same-family lanes across all 5 rounds, so
             the transfer signal is not confounded by family drift.
  - New    : instances seen exactly once, never repeated, drawn ONLY from
             families never used by Repeat or Variant.
             Control: performance here must stay flat if learning is specific.

Every task enumerated here exists under datasets/variants/tasks/<id> with a
pristine snapshot, so the allocator only recombines existing task_ids.

Output: datasets/variants/tier_round_1.csv .. tier_round_5.csv
Schema: original CSV columns + a trailing `tier` column.

Round size: 6 tasks = 2 Repeat + 3 Variant + 1 New
(bug_fix / implement_function / write_tests have >=5 instances to fill the
variant lanes; cli_tool + docker_configure provide 7 held-out instances for
the New control, keeping New families fully disjoint from anything practiced.)
"""
from __future__ import annotations

import csv
from pathlib import Path

BASE = Path(__file__).resolve().parent
VARIANT_DIR = BASE / "variants"
ROUNDS = 5

# ---- Repeat: identical instances in EVERY round (verbatim each round) -------
REPEAT = ["fastapi_catalog", "refactor_config"]

# ---- Variant: strict same-family lanes. Each lane is one family, one fresh
# instance every round. No cross-round family drift is allowed (reviewer fix).
VARIANT_LANES: dict[str, list[str]] = {
    "bug_fix": [
        "bug_fix_text_wrong_regex",       # round 1
        "bug_fix_text_offbyone",          # round 2
        "bug_fix_scheduling_offbyone",    # round 3
        "bug_fix_text_wrong_compare",     # round 4
        "bug_fix_scheduling_wrong_compare",  # round 5
    ],
    "implement_function": [
        "implement_knapsack",             # round 1
        "implement_lru_cache",            # round 2
        "implement_merge_intervals",      # round 3
        "implement_edit_distance",        # round 4
        "implement_max_profit",           # round 5
    ],
    "write_tests": [
        "write_tests_temperature",        # round 1
        "write_tests_stats",              # round 2
        "write_tests_cart",               # round 3
        "write_tests_banking",            # round 4
        "write_tests_urlparser",          # round 5
    ],
}

# ---- New: one per round, from a family that is NEVER used in Repeat or
# Variant. cli_tool + docker_tools are fully held out (never practiced).
NEW_LANE: list[str] = [
    "cli_filter",                         # round 1
    "docker_streamlit_dashboard",         # round 2
    "cli_json_pretty",                    # round 3
    "cli_word_freq",                      # round 4
    "cli_sales",                          # round 5
]


def _load_rows() -> dict[str, dict]:
    """task_id -> original CSV row, sourced from the first variant CSV that
    mentions it."""
    seen: dict[str, dict] = {}
    for csv_path in sorted(VARIANT_DIR.glob("round_*_se.csv")):
        with open(csv_path, encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                tid = (row.get("task_id") or "").strip()
                if tid and tid not in seen:
                    seen[tid] = row
    return seen


def _variant_by_round() -> dict[int, list[str]]:
    lanes = list(VARIANT_LANES.values())
    return {
        round_no: [lane[round_no - 1] for lane in lanes]
        for round_no in range(1, ROUNDS + 1)
    }


def _tiers_by_round() -> dict[int, list[tuple[str, str]]]:
    return {
        round_no: (
            [(t, "Repeat") for t in REPEAT]
            + [(t, "Variant") for t in _variant_by_round()[round_no]]
            + [(_new_lane_for_round(round_no), "New")]
        )
        for round_no in range(1, ROUNDS + 1)
    }


def _new_lane_for_round(round_no: int) -> str:
    if round_no - 1 >= len(NEW_LANE):
        raise SystemExit(
            f"NEW_LANE covers only {len(NEW_LANE)} rounds, "
            f"need {ROUNDS} (round {round_no})"
        )
    return NEW_LANE[round_no - 1]


def validate(rows: dict[str, dict], tiers: dict[int, list[tuple[str, str]]]) -> None:
    for round_no in range(1, ROUNDS + 1):
        round_tids = [t for t, _ in tiers[round_no]]

        # invariant: consistent round size
        expect = 2 + len(VARIANT_LANES) + 1
        if len(round_tids) != expect:
            raise SystemExit(
                f"round {round_no}: {len(round_tids)} tasks, expected {expect}"
            )

        # invariant: no duplicate within a single round
        intra_dupes = [t for t in set(round_tids) if round_tids.count(t) > 1]
        if intra_dupes:
            raise SystemExit(
                f"round {round_no} reuses a task within itself: {intra_dupes}"
            )

    # invariant: no task may be both a New control and a practice task, and no
    # task may sit in two different tiers across rounds. Repeat is the only
    # tier allowed to repeat a task (the SAME tid, every round, verbatim).
    tid_tiers: dict[str, set[str]] = {}
    for _round_no, tasks in tiers.items():
        for tid, tier in tasks:
            tid_tiers.setdefault(tid, set()).add(tier)
    for tid, labels in tid_tiers.items():
        if len(labels) > 1:
            raise SystemExit(
                f"task {tid} assigned to multiple tiers {sorted(labels)} "
                f"- confounds 'New' (specificity) and 'Variant' (transfer)"
            )

    # invariant: a fresh same-family variant (no cross-family drift across rounds)
    for round_no in range(2, ROUNDS + 1):
        prev_vars = [
            t for t, tn in tiers[round_no - 1] if tn == "Variant"
        ]
        cur_vars = [t for t, tn in tiers[round_no] if tn == "Variant"]
        for pid, cid in zip(prev_vars, cur_vars):
            if rows[pid]["family"] != rows[cid]["family"]:
                raise SystemExit(
                    f"Variant drift at round {round_no}: "
                    f"{pid}({rows[pid]['family']}) -> "
                    f"{cid}({rows[cid]['family']})"
                )

    missing = [t for t in tid_tiers if t not in rows]
    if missing:
        raise SystemExit(f"unknown task ids: {missing}")

    # invariant: every referenced task has a pristine workdir snapshot so the
    # benchmark can restore identical fixtures per (round, arm, execution).
    no_pristine = [
        t for t in tid_tiers
        if not (VARIANT_DIR / "tasks" / t / "pristine").is_dir()
    ]
    if no_pristine:
        raise SystemExit(
            f"task(s) missing pristine/ snapshot: {no_pristine}"
        )


def main() -> None:
    rows = _load_rows()
    tiers = _tiers_by_round()
    validate(rows, tiers)
    for round_no in range(1, ROUNDS + 1):
        tasks = tiers[round_no]
        out = VARIANT_DIR / f"tier_round_{round_no}.csv"
        fieldnames = list(rows[tasks[0][0]].keys()) + ["tier"]
        with open(out, "w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for tid, tier in tasks:
                row = dict(rows[tid])
                row["tier"] = tier
                writer.writerow(row)
        print(
            f"{out.name}: "
            + ", ".join(f"{tid}[{tier}]" for tid, tier in tasks)
        )


if __name__ == "__main__":
    main()