"""CLI.

``uv run python -m risk_review [review] [--lanes a,b] [--no-verify] [--out DIR]`` runs the
defect-hunting review of this repository; ``uv run python -m risk_review assess --repo
PATH|URL [--lanes ...]`` runs the fact-based risk assessment of an arbitrary repository.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from risk_review.agents.fact_finder.factory import available_fact_lanes
from risk_review.agents.lane_reviewer.factory import available_lanes
from risk_review.observability.report import render_assessment_markdown, render_markdown
from risk_review.settings import RiskReviewSettings, get_review_settings
from risk_review.workflows.assess import report_as_dict as assessment_as_dict
from risk_review.workflows.assess import run_assessment
from risk_review.workflows.review import report_as_dict, run_review

COMMANDS = ("review", "assess")


def _prepare_output(out_dir: Path, settings: RiskReviewSettings) -> Path | None:
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / "trace.jsonl" if settings.trace else None
    if trace_path is not None and trace_path.exists():
        trace_path.unlink()
    return trace_path


@contextmanager
def _repository(target: str) -> Iterator[tuple[Path, str]]:
    """A local path as is; an https URL cloned through the product's allowlisted cloner."""
    if target.startswith("https://"):
        from app.repo_analysis.clone_repository import temporary_clone
        from app.settings import get_settings

        app_settings = get_settings()
        with temporary_clone(
            target,
            None,
            timeout_s=app_settings.repo_clone_timeout_s,
            max_size_mb=app_settings.repo_max_size_mb,
        ) as clone:
            yield clone.path, target
        return
    path = Path(target).resolve()
    if not path.is_dir():
        raise SystemExit(f"not a directory: {path}")
    yield path, str(path)


def run_review_command(args: argparse.Namespace, settings: RiskReviewSettings) -> int:
    lanes = [lane.strip() for lane in args.lanes.split(",")] if args.lanes else available_lanes()
    unknown = sorted(set(lanes) - set(available_lanes()))
    if unknown:
        raise SystemExit(f"unknown lanes {unknown}; see --list-lanes")
    repository_root = args.repo.resolve()
    out_dir: Path = args.out
    trace_path = _prepare_output(out_dir, settings)
    print(
        f"risk review: {len(lanes)} lane(s), concurrency {settings.concurrency}, "
        f"verify={'no' if args.no_verify else 'yes'}",
        file=sys.stderr,
    )
    report = asyncio.run(
        run_review(
            lanes=lanes,
            repository_root=repository_root,
            backend_dir=Path(__file__).resolve().parents[1],
            settings=settings,
            trace_path=trace_path,
            verify=not args.no_verify,
        )
    )
    (out_dir / "report.json").write_text(json.dumps(report_as_dict(report), indent=2))
    markdown = render_markdown(report)
    (out_dir / "report.md").write_text(markdown)
    print(markdown.split("## Findings")[0])
    print(f"wrote {out_dir / 'report.md'} and report.json", file=sys.stderr)
    return 0


def run_assess_command(args: argparse.Namespace, settings: RiskReviewSettings) -> int:
    lanes = [lane.strip() for lane in args.lanes.split(",")] if args.lanes else None
    unknown = sorted(set(lanes or []) - set(available_fact_lanes()))
    if unknown:
        raise SystemExit(f"unknown fact lanes {unknown}; available: {available_fact_lanes()}")
    out_dir: Path = args.out
    trace_path = _prepare_output(out_dir, settings)
    with _repository(args.repo) as (root, label):
        print(
            f"risk assessment of {label}: {len(lanes or available_fact_lanes())} lane(s), "
            f"concurrency {settings.concurrency}",
            file=sys.stderr,
        )
        report = asyncio.run(
            run_assessment(
                repository_root=root,
                repository_label=label,
                lanes=lanes,
                settings=settings,
                trace_path=trace_path,
            )
        )
    (out_dir / "assessment.json").write_text(json.dumps(assessment_as_dict(report), indent=2))
    markdown = render_assessment_markdown(report)
    (out_dir / "assessment.md").write_text(markdown)
    print(markdown.split("## Facts and evidence")[0])
    print(f"wrote {out_dir / 'assessment.md'} and assessment.json", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    settings = get_review_settings()
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or (argv[0] not in COMMANDS and not argv[0].startswith("-h")):
        argv = ["review", *argv]
    parser = argparse.ArgumentParser(prog="risk_review", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    review = sub.add_parser("review", help="Defect-hunting review of this repository")
    review.add_argument("--lanes", help="Comma-separated lane names (default: all)")
    review.add_argument("--list-lanes", action="store_true")
    review.add_argument("--no-verify", action="store_true", help="Skip the verifier pass")
    review.add_argument("--out", type=Path, default=settings.output_dir)
    review.add_argument("--repo", type=Path, default=settings.repository_root)
    review.add_argument("--concurrency", type=int, default=settings.concurrency)
    review.add_argument("--max-findings", type=int, default=settings.max_findings_per_lane)

    assess = sub.add_parser("assess", help="Fact-based risk assessment of a repository")
    assess.add_argument("--repo", help="Local path or https URL (allowlisted host)")
    assess.add_argument("--lanes", help="Comma-separated fact lanes (default: all)")
    assess.add_argument("--list-lanes", action="store_true")
    assess.add_argument("--out", type=Path, default=settings.output_dir.parent / "risk-assessment")
    assess.add_argument("--concurrency", type=int, default=settings.concurrency)

    args = parser.parse_args(argv)
    if args.list_lanes:
        print("\n".join(available_lanes() if args.command == "review" else available_fact_lanes()))
        return 0
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")
    update = {"concurrency": args.concurrency}
    if args.command == "review":
        update["max_findings_per_lane"] = args.max_findings
    settings = settings.model_copy(update=update)
    if args.command == "assess":
        if not args.repo:
            parser.error("assess needs --repo PATH|URL")
        return run_assess_command(args, settings)
    return run_review_command(args, settings)


if __name__ == "__main__":
    sys.exit(main())
