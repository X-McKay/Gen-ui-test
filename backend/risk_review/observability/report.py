"""Renders a ReviewReport as Markdown. Numbers first, then findings with verdicts."""

from __future__ import annotations

from risk_review.workflows.review import LaneResult, ReviewReport, VerifiedFinding

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _verdict_label(item: VerifiedFinding) -> str:
    if item.verdict is None:
        return "unverified"
    return item.verdict.verdict


def _finding_block(lane: LaneResult, item: VerifiedFinding) -> str:
    f = item.finding
    lines = [
        f"### [{f.severity}] {f.title}",
        "",
        f"- Lane: `{lane.lane}` · Category: `{f.category}` · Verdict: **{_verdict_label(item)}**"
        f" · Reviewer confidence {f.confidence:.2f}",
        f"- Location: `{f.file}:{f.line}`",
        f"- Invariant: {f.invariant}",
        f"- Failure scenario: {f.failure_scenario}",
        "- Evidence:",
    ]
    lines += [f"  - `{e.file}:{e.line}` `{e.quote}`" for e in f.evidence]
    lines.append(f"- Proposed test: {f.proposed_test}")
    if item.verdict is not None:
        v = item.verdict
        lines.append(
            f"- Verifier ({v.confidence:.2f}): {v.reasoning}"
            + (" Existing test covers it." if v.existing_test_covers_it else "")
        )
        lines += [f"  - `{e.file}:{e.line}` `{e.quote}`" for e in v.evidence]
    return "\n".join(lines)


def render_markdown(report: ReviewReport) -> str:
    t = report.totals
    out = [
        f"# Risk review {report.report_id}",
        "",
        f"Commit `{report.git_commit}` · {report.created_at} · "
        f"lanes: {', '.join(report.lanes_requested)}",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Findings | {t.findings} (confirmed {t.confirmed}, refuted {t.refuted}, "
        f"uncertain {t.uncertain}, unverified {t.unverified}) |",
        f"| Wall time | {t.duration_ms / 1000:.0f} s |",
        f"| Model requests | {t.model_requests} |",
        f"| Tokens in / out / thinking | {t.input_tokens} / {t.output_tokens} / "
        f"{t.thinking_tokens} |",
        f"| Tool calls | {t.tool_calls} |",
        f"| Estimated cost | ${t.estimated_cost_usd:.4f} |",
        f"| Budget violations | {t.budget_violations} |",
        "",
        "## Lanes",
        "",
        "| Lane | Status | Findings | Requests | Tokens in/out | Tool calls | Time |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for lane in report.lanes:
        m = lane.metrics
        out.append(
            f"| {lane.lane} | {lane.status} | {len(lane.findings)} | {m.model_requests} | "
            f"{m.input_tokens}/{m.output_tokens} | {m.tool_calls} | {m.duration_ms / 1000:.0f} s |"
        )
    out += ["", "## Findings", ""]
    ordered = sorted(
        ((lane, item) for lane in report.lanes for item in lane.findings),
        key=lambda pair: (
            _verdict_label(pair[1]) != "confirmed",
            SEVERITY_ORDER[pair[1].finding.severity],
        ),
    )
    blocks = [_finding_block(lane, item) for lane, item in ordered]
    out.append("\n\n".join(blocks) if blocks else "_No findings._")
    notes = [(ln.lane, ln.notes or ln.error) for ln in report.lanes if ln.notes or ln.error]
    if notes:
        out += ["", "## Notes", ""] + [f"- `{lane}`: {note}" for lane, note in notes]
    out += ["", "## Manifests", ""]
    for name, manifest in report.manifests.items():
        active = [s.name for s in manifest.skills if s.active]
        thinking = "on" if manifest.model_settings.get("enable_thinking") else "off"
        out.append(
            f"- `{name}` v{manifest.agent_version} manifest `{manifest.manifest_id}` · "
            f"{manifest.model_id} ({manifest.model_policy}, thinking {thinking}) · "
            f"skills {', '.join(active)} · tools {', '.join(manifest.tools)}"
        )
    return "\n".join(out) + "\n"
