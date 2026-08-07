"""Build the Case-3 curriculum datasets: tier_round_1.csv .. tier_round_5.csv.

Case-3 design (spec §6):

  * n = 10 tasks per round, 5 rounds.
  * 3 Repeat  : the SAME task_id, verbatim, every round
                (fastapi_catalog, refactor_config, write_tests_temperature).
  * 5 Variant : per-round lanes that share an architectural family but change
                instance across rounds (bug_fixing x2, algorithms x1,
                testing x1, algorithms #2 x1) - transfer test.
  * 2 New     : never-practiced held-out families (cli_tool / docker_configure)
                - zero-shot baseline, must stay flat.

Capacity audit (34-instance pool, spec 6.2):
  * bug_fixing  has 10 instances  -> two full 5-round bug lanes.
  * algorithms (implement_*) has 6 -> one 5-round lane; the second algorithms
    lane must therefore reuse 4 of those instances (documented above).
  * testing (write_tests) has 4 instances left after write_tests_temperature is
    consumed by Repeat -> 1 lane with a 1-instance reuse in round 5.
  * New needs 10 rows but cli+docker hold only 7 held-out instances -> 3 rows
    reuse an earlier held-out instance (documented in the plan).

Output schema: original vendor CSV columns + a trailing `tier` column.
"""
from __future__ import annotations

import csv
from pathlib import Path

BASE = Path(__file__).resolve().parent
VARIANT_DIR = BASE / "variants"
ROUNDS = 5

# Spec §6.1 taxonomy: `family` in the tier CSVs must be one of these domain
# classifications. Maps the loader-internal family names onto the spec's set.
FAMILY_TAXONOMY = {
    "fastapi_setup": "web_api",
    "refactor": "refactoring",
    "write_tests": "testing",
    "bug_fix": "bug_fixing",
    "implement_function": "algorithms",
    "cli_tool": "cli_tool",
    "docker_configure": "devops",
}

# -------------------------------------------------------------------------- #
# Curriculum board (this IS the Case-3 design; edit here, re-run the script). #
# -------------------------------------------------------------------------- #

# 3 Repeat: identical task_id, every round, verbatim (spec 6.2).
REPEAT = ["fastapi_catalog", "refactor_config", "write_tests_temperature"]

# 5 Variant lanes. Each key is the architectural family; the value is one
# instance per round (round index = position in the list). Changing the
# instance (same pbnd) across rounds is what makes it a *variant* lane.
# Pool limits force two reuse rows, explicitly flagged so the plan can cite
# them:
#   algorithms2 round 2..5 re-use algorithms1's round 1..4 instances;
#   testing round 5 reuses testing round 1 (only 4 distinct instances exist).
VARIANT_LANES: dict[str, list[str]] = {
    "bug_fix": [                              # 10 distinct bug instances -> OK
        "bug_fix_text_wrong_regex",           # round 1
        "bug_fix_text_offbyone",              # round 2
        "bug_fix_scheduling_offbyone",        # round 3
        "bug_fix_finance_wrong_compare",      # round 4
        "bug_fix_finance_bad_default",        # round 5
    ],
    "bug_fixing_2": [
        "bug_fix_finance_offbyone",           # round 1
        "bug_fix_scheduling_wrong_key",       # round 2
        "bug_fix_text_wrong_compare",         # round 3
        "bug_fix_scheduling_wrong_compare",   # round 4
        "bug_fix_finance_wrong_accum",        # round 5
    ],
    "algorithms": [
        "implement_knapsack",                 # round 1
        "implement_lru_cache",                # round 2
        "implement_merge_intervals",          # round 3
        "implement_edit_distance",            # round 4
        "implement_max_profit",               # round 5
    ],
    "algorithms_2": [
        "implement_flatten_json",             # round 1
        "implement_knapsack",                 # round 2 (reuse-1)
        "implement_lru_cache",                # round 3 (reuse-2)
        "implement_merge_intervals",          # round 4 (reuse-3)
        "implement_edit_distance",            # round 5 (reuse-4)
    ],
    "testing": [
        "write_tests_stats",                  # round 1
        "write_tests_cart",                   # round 2
        "write_tests_banking",                # round 3
        "write_tests_urlparser",              # round 4
        "write_tests_stats",                  # round 5 (reuse-5)
    ],
}

# 2 New tasks per round, from never-practiced held-out families. Only 7
# held-out instances exist (4 cli_tool + 3 docker_configure), so rounds 4-5
# reuse two earlier held-out instances.
NEW_LANE: list[list[str]] = [
    ["cli_filter", "docker_streamlit_dashboard"],       # round 1
    ["cli_json_pretty", "docker_cron_worker"],          # round 2
    ["cli_word_freq", "docker_flask_api"],              # round 3
    ["cli_sales", "cli_filter"],                        # round 4 (reuse-1)
    ["docker_streamlit_dashboard", "cli_json_pretty"],  # round 5 (reuse-2,3)
]

REUSE_NOTES = {
    "algorithms_2": [None] + [f"reuse implement round {i-1} instance"
                              for i in range(2, ROUNDS + 1)],
    "testing": [None, None, None, None, "reuse round 1 (pool exhausted)"],
}


def _load_rows() -> dict[str, dict]:
    """task_id -> original vendor CSV row."""
    seen: dict[str, dict] = {}
    for csv_path in sorted(VARIANT_DIR.glob("round_*_se.csv")):
        with open(csv_path, encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                tid = (row.get("task_id") or "").strip()
                if tid and tid not in seen:
                    seen[tid] = row
    return seen


def _variant_by_round() -> dict[int, list[str]]:
    lanes = list(VARIANT_LANES.items())
    return {
        round_no: [lane[round_no - 1] for _fam, lane in lanes]
        for round_no in range(1, ROUNDS + 1)
    }


def _rounds() -> dict[int, list[tuple[str, str]]]:
    out: dict[int, list[tuple[str, str]]] = {}
    for round_no in range(1, ROUNDS + 1):
        tasks = (
            [(t, "Repeat") for t in REPEAT]
            + [(t, "Variant") for t in _variant_by_round()[round_no]]
            + [(t, "New") for t in NEW_LANE[round_no - 1]]
        )
        out[round_no] = tasks
    return out


def validate(rows: dict[str, dict], rounds: dict[int, list[tuple[str, str]]]
             ) -> None:
    for round_no in range(1, ROUNDS + 1):
        tids = [t for t, _ in rounds[round_no]]
        assert len(tids) == 10, (
            f"round {round_no}: {len(tids)} tasks, expected 10"
        )
        dupes = [t for t in set(tids) if tids.count(t) > 1]
        assert not dupes, f"round {round_no} duplicates within: {dupes}"
    tier_map: dict[str, set[str]] = {}
    for _r, tasks in rounds.items():
        for tid, tier in tasks:
            tier_map.setdefault(tid, set()).add(tier)
    for tid, labels in tier_map.items():
        assert len(labels) == 1, (
            f"task {tid} in multiple tiers {labels}"
        )
        # Repeats must be identical every round; Variant/New must repeat task.
    missing = [t for t in tier_map if t not in rows]
    assert not missing, f"unknown task ids: {missing}"
    no_pristine = [
        t for t in tier_map
        if not (VARIANT_DIR / "tasks" / t / "pristine").is_dir()
    ]
    assert not no_pristine, f"missing pristine/: {no_pristine}"


def main() -> None:
    rows = _load_rows()
    rounds = _rounds()
    validate(rows, rounds)
    for round_no in range(1, ROUNDS + 1):
        tasks = rounds[round_no]
        out = VARIANT_DIR / f"tier_round_{round_no}.csv"
        fieldnames = list(rows[tasks[0][0]].keys()) + ["tier"]
        with open(out, "w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for tid, tier in tasks:
                row = dict(rows[tid])
                row["tier"] = tier
                row["family"] = FAMILY_TAXONOMY.get(
                    row.get("family", ""), row.get("family", ""))
                writer.writerow(row)
        print(
            f"{out.name} (n={len(tasks)}): "
            + ", ".join(f"{tid}[{tier}]" for tid, tier in tasks)
        )


if __name__ == "__main__":
    main()