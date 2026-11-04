"""Renders a ReviewReport or an AssessmentReport as Markdown. Numbers first."""

from __future__ import annotations

from app.intake.question_bank import QUESTIONS_BY_FIELD, display_value
from risk_review.workflows.assess import AssessmentReport
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


def _label(field: str) -> str:
    spec = QUESTIONS_BY_FIELD.get(field)
    return spec.label if spec else field


def render_assessment_markdown(report: AssessmentReport) -> str:
    a = report.assessment
    t = report.totals
    inherent, residual = a.inherent_risk, a.residual_risk
    out = [
        f"# Repository risk assessment {report.report_id}",
        "",
        f"Repository `{report.repository}` at `{report.git_commit}` · {report.created_at} · "
        f"lanes: {', '.join(report.lanes_requested)}",
        "",
        "| Assessment | Result |",
        "| --- | --- |",
        f"| EU AI Act classification | **{a.eu_ai_act.classification.value}** |",
        f"| Inherent risk | **{inherent.tier.value}** (score {inherent.score}"
        + (f", floor: {inherent.floor_reason}" if inherent.floor_reason else "")
        + ") |",
        f"| Residual risk, controls unconfirmed | **{residual.tier.value}** "
        f"(score {residual.score}) |",
        f"| Residual risk if claimed controls are confirmed | "
        f"**{report.residual_if_confirmed.value}** |",
        f"| Overall compliance tier | {a.overall_risk_tier.value} |",
        f"| Frameworks | {', '.join(a.applicable_frameworks) or '—'} |",
        f"| Facts recorded / rejected | {len(report.facts)} / {len(report.rejected_facts)} |",
        f"| Open questions for the owner | {len(report.open_questions)} |",
        f"| Wall time · requests · tokens in/out · tool calls | {t.duration_ms / 1000:.0f} s · "
        f"{t.model_requests} · {t.input_tokens}/{t.output_tokens} · {t.tool_calls} |",
        "",
        "## Risk lenses",
        "",
        "| Lens | Inherent | Residual (unconfirmed) | Drivers |",
        "| --- | --- | --- | --- |",
    ]
    for lens in a.risk_lenses:
        out.append(
            f"| {lens.label} | {lens.inherent.tier.value} ({lens.inherent.score}) | "
            f"{lens.residual.tier.value} ({lens.residual.score}) | "
            f"{'; '.join(d.text for d in lens.inherent.drivers) or '—'} |"
        )
    out += ["", "## Risk drivers", ""]
    if inherent.drivers:
        out += ["| Driver | Category | Points | Answer |", "| --- | --- | --- | --- |"]
        out += [
            f"| {d.text} | {d.category} | +{d.points} | {_label(d.field)}: "
            f"{display_value(d.field, d.value)} |"
            for d in inherent.drivers
        ]
    else:
        out.append("No driver was triggered by the facts found.")
    out += ["", "## Controls", "", "| Control | Status | Points removed |", "| --- | --- | --- |"]
    out += [f"| {c.text} | {c.status} | -{c.points} |" for c in residual.controls]
    if a.eu_ai_act.rationale:
        out += ["", "## Why this classification", ""]
        out += [
            f"- {r.text} ({r.article}) — {_label(r.field)}: {display_value(r.field, r.value)}"
            for r in a.eu_ai_act.rationale
        ]
    if a.obligations:
        out += ["", "## Obligations", ""]
        out += [
            f"- **{o.framework}**: {o.text}" + (f" ({o.reference})" if o.reference else "")
            for o in a.obligations
        ]
    out += [
        "",
        "## Facts and evidence",
        "",
        "| Field | Value | Conf. | Basis | Lane | Evidence |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for f in report.facts:
        quote = f.evidence_quote.replace("|", "\\|")[:100]
        conflicts = f" (conflicts: {'; '.join(f.conflicts)})" if f.conflicts else ""
        out.append(
            f"| {_label(f.field)} | {display_value(f.field, f.value)} | {f.confidence:.2f} "
            f"| {f.basis} | {f.lane} | `{f.evidence_file}:{f.evidence_line}` `{quote}`"
            f"{conflicts} |"
        )
    if report.rejected_facts:
        out += ["", "Rejected facts: " + "; ".join(report.rejected_facts)]
    out += ["", "## Open questions for the owner", ""]
    out += [f"- {_label(field)} (`{field}`)" for field in report.open_questions] or ["None."]
    out += [
        "",
        "## Lanes",
        "",
        "| Lane | Status | Facts | Requests | Tokens in/out | Tool calls | Time |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for lane in report.lanes:
        m = lane.metrics
        out.append(
            f"| {lane.lane} | {lane.status} | {len(lane.facts)} | {m.model_requests} | "
            f"{m.input_tokens}/{m.output_tokens} | {m.tool_calls} | {m.duration_ms / 1000:.0f} s |"
        )
        if lane.notes:
            out.append(f"| | notes | {lane.notes[:300]} | | | | |")
    return "\n".join(out) + "\n"
