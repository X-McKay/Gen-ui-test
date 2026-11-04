"""CLI: ``uv run python -m risk_review [--lanes a,b] [--no-verify] [--out DIR]``."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from risk_review.agents.lane_reviewer.factory import available_lanes
from risk_review.observability.report import render_markdown
from risk_review.settings import get_review_settings
from risk_review.workflows.review import report_as_dict, run_review


def main(argv: list[str] | None = None) -> int:
    settings = get_review_settings()
    parser = argparse.ArgumentParser(prog="risk_review", description=__doc__)
    parser.add_argument("--lanes", help="Comma-separated lane names (default: all)")
    parser.add_argument("--list-lanes", action="store_true")
    parser.add_argument("--no-verify", action="store_true", help="Skip the verifier pass")
    parser.add_argument("--out", type=Path, default=settings.output_dir)
    parser.add_argument("--repo", type=Path, default=settings.repository_root)
    parser.add_argument("--concurrency", type=int, default=settings.concurrency)
    parser.add_argument("--max-findings", type=int, default=settings.max_findings_per_lane)
    args = parser.parse_args(argv)

    if args.list_lanes:
        print("\n".join(available_lanes()))
        return 0
    lanes = [lane.strip() for lane in args.lanes.split(",")] if args.lanes else available_lanes()
    unknown = sorted(set(lanes) - set(available_lanes()))
    if unknown:
        parser.error(f"unknown lanes {unknown}; see --list-lanes")

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")
    settings = settings.model_copy(
        update={"concurrency": args.concurrency, "max_findings_per_lane": args.max_findings}
    )
    repository_root = args.repo.resolve()
    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / "trace.jsonl" if settings.trace else None
    if trace_path is not None and trace_path.exists():
        trace_path.unlink()

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


if __name__ == "__main__":
    sys.exit(main())
