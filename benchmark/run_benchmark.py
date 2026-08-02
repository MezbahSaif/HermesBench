"""HermesBench CLI entrypoint.

Usage:
    python benchmark/run_benchmark.py --rounds 3 --arm both
    python benchmark/run_benchmark.py --arm treatment --tasks prog_bubble_sort
    python benchmark/run_benchmark.py --dry-run
    python benchmark/run_benchmark.py --resume   (continue a previous run)
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

BENCH_ROOT = Path(__file__).resolve().parent.parent
if str(BENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(BENCH_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="HermesBench - benchmark Hermes Agent's self-improvement claim"
    )
    parser.add_argument("--config", default=str(BENCH_ROOT / "config" / "config.yaml"))
    parser.add_argument("--dataset", default=None,
                        help="override dataset path from config")
    parser.add_argument("--no-judge", action="store_true",
                        help="disable the LLM judge (llm_judge tasks score None)")
    parser.add_argument("--run-id", default=None,
                        help="short run identifier (default: timestamp)")
    parser.add_argument("--arm", choices=["treatment", "control", "both"],
                        default=None)
    parser.add_argument("--rounds", type=int, default=None)
    parser.add_argument("--round", type=int, default=None,
                        help="run exactly one round (e.g. --round 3); combine "
                             "with --resume to continue a previous run")
    parser.add_argument("--tasks", default=None,
                        help="comma-separated task_ids to run")
    parser.add_argument("--category", default=None,
                        help="comma-separated categories to run")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--resume", action="store_true",
                        help="skip tasks already completed in this run dir")
    parser.add_argument("--dry-run", action="store_true",
                        help="validate environment and print a report only")
    parser.add_argument("--refresh-pristine", action="store_true",
                        help="snapshot current workdirs as pristine "
                             "(one-time setup for hand-made datasets)")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"config not found: {config_path}", file=sys.stderr)
        return 2
    from benchmark.config_loader import load_config
    config = load_config(config_path)
    if args.dataset:
        ds = Path(args.dataset)
        if not ds.is_absolute():
            root_resolved = BENCH_ROOT / ds
            if root_resolved.exists():
                ds = root_resolved
            else:
                ds = BENCH_ROOT / "datasets" / ds
        if not ds.exists():
            print(f"dataset not found: {ds}", file=sys.stderr)
            return 2
        config.setdefault("project", {})["dataset"] = str(ds)
    if args.no_judge:
        config["lmstudio"]["judge_model"] = None

    if args.arm == "both":
        arms = ["treatment", "control"]
    elif args.arm in ("treatment", "control"):
        arms = [args.arm]
    else:
        arms = list(config["benchmark"].get("arms", ["treatment"]))

    rounds = args.rounds or int(config["benchmark"].get("rounds", 3))
    if args.round is not None and args.rounds is not None:
        print("[config] use either --round (single round) or --rounds, "
              "not both", file=sys.stderr)
        return 2
    if args.round is not None:
        rounds = args.round
        if args.round > 1 and not args.resume:
            print(
                f"[config] WARNING: running round {args.round} without "
                "--resume in a fresh run dir; rounds 1.."
                f"{args.round - 1} will be missing from the analysis."
            )
    run_id = args.run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = BENCH_ROOT / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    if not args.dry_run and not args.refresh_pristine:
        real_home = Path(config.get("hermes", {}).get("real_home", ""))
        if not real_home.exists():
            print(
                "[config] ERROR: real Hermes home not found at "
                f"{real_home}.\n"
                "[config] Your teammate must have Hermes Agent installed; "
                "or set `hermes.executable` / `hermes.real_home` in "
                "config/config.yaml for their machine.",
                file=sys.stderr,
            )
            return 2

    task_ids = [t.strip() for t in (args.tasks or "").split(",") if t.strip()] or None
    categories = [c.strip() for c in (args.category or "").split(",") if c.strip()] or None

    # Route output to a per-run log file too.
    log_path = BENCH_ROOT / "logs" / f"{run_id}.log"
    log_fh = open(log_path, "a", encoding="utf-8")
    tee = Tee(sys.stdout, log_fh)

    from benchmark.benchmark_runner import BenchmarkRunner, snapshot_pristine

    if args.refresh_pristine:
        from benchmark.task_loader import load_tasks
        ds = Path(config["project"]["dataset"])
        tasks = load_tasks(ds)
        made = sum(1 for t in tasks if snapshot_pristine(t))
        print(f"pristine snapshots created for {made}/{len(tasks)} tasks")
        return 0

    runner = BenchmarkRunner(
        config=config,
        run_dir=run_dir,
        run_id=run_id,
        arms=arms,
        rounds=rounds,
        round_no=args.round,
        task_limit=args.limit,
        task_ids=task_ids,
        categories=categories,
        resume=args.resume,
        dry_run=args.dry_run,
    )
    runner.logger = lambda msg: tee.write(str(msg) + "\n")
    runner.run()
    log_fh.close()
    return 0


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, text: str):
        for s in self.streams:
            s.write(text)
            s.flush()

    def flush(self):
        for s in self.streams:
            s.flush()


if __name__ == "__main__":
    raise SystemExit(main())
