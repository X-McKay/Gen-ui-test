"""CLI: ``uv run python -m evals.risk_review run --suite smoke --repeats 3`` and
``... promote <experiment_id>``."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from evals.risk_review.runner import (
    EXPERIMENTS_DIR,
    Experiment,
    promote_baseline,
    run_suite,
)
from risk_review.settings import get_review_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evals.risk_review")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Run a suite and compare with its baseline")
    run.add_argument("--suite", default="smoke")
    run.add_argument("--repeats", type=int, default=1)
    run.add_argument("--case", action="append", help="Only this case id (repeatable)")
    run.add_argument("--out", type=Path, default=None)
    run.add_argument("--promote", action="store_true", help="Accept the result as the baseline")
    promote = commands.add_parser("promote", help="Accept an earlier experiment as the baseline")
    promote.add_argument("experiment_id")
    args = parser.parse_args(argv)

    if args.command == "promote":
        path = EXPERIMENTS_DIR / args.experiment_id / "results.json"
        experiment = Experiment.model_validate_json(path.read_text(encoding="utf-8"))
        print(f"baseline written: {promote_baseline(experiment)}")
        return 0

    settings = get_review_settings().model_copy(update={"concurrency": 1})
    experiment, folder = asyncio.run(
        run_suite(
            args.suite,
            repeats=args.repeats,
            settings=settings,
            case_ids=args.case,
            out_dir=args.out,
        )
    )
    print((folder / "summary.md").read_text())
    print(f"results: {folder}", file=sys.stderr)
    if args.promote:
        print(f"baseline written: {promote_baseline(experiment)}", file=sys.stderr)
    return 0 if experiment.release_ok else 1


if __name__ == "__main__":
    sys.exit(main())
