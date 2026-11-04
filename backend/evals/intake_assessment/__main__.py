"""CLI: ``uv run python -m evals.intake_assessment run --suite facts --repeats 2 [--promote]``."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from evals.intake_assessment.runner import (
    EXPERIMENTS_DIR,
    Experiment,
    promote_baseline,
    render_experiment,
    run_suite,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evals.intake_assessment", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Run a suite on the configured model")
    run.add_argument("--suite", default="facts")
    run.add_argument("--repeats", type=int, default=1)
    run.add_argument("--case", action="append", dest="cases", help="Only these case ids")
    run.add_argument("--out", type=Path, default=None)
    run.add_argument("--concurrency", type=int, default=3)
    run.add_argument("--promote", action="store_true", help="Promote when every gate passes")
    promote = sub.add_parser("promote", help="Promote a past experiment to the baseline")
    promote.add_argument("experiment_id")
    args = parser.parse_args(argv)

    if args.command == "promote":
        path = EXPERIMENTS_DIR / args.experiment_id / "results.json"
        experiment = Experiment.model_validate_json(path.read_text())
        print(f"baseline written to {promote_baseline(experiment)}")
        return 0

    experiment = asyncio.run(
        run_suite(
            args.suite,
            repeats=args.repeats,
            case_ids=args.cases,
            out_dir=args.out,
            concurrency=args.concurrency,
        )
    )
    print(render_experiment(experiment))
    if args.promote:
        if experiment.release_ok:
            print(f"baseline written to {promote_baseline(experiment)}", file=sys.stderr)
        else:
            print("not promoted: gates failed", file=sys.stderr)
    print(
        json.dumps(
            {"experiment_id": experiment.experiment_id, "release_ok": experiment.release_ok}
        ),
        file=sys.stderr,
    )
    return 0 if experiment.release_ok else 1


if __name__ == "__main__":
    sys.exit(main())
