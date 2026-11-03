"""Tool: gap analysis → the next step (assumptions to confirm, at most three questions)."""

from __future__ import annotations

from typing import Any

from google.adk.tools.tool_context import ToolContext

from app.agents.surface_plan import (
    TARGET_ID,
    Finding,
    Step,
    build_operations,
    build_step,
    invalid_operations_fixture,
)
from app.agents.tools.context import load_intake, load_step, publish_state, tool_error
from app.intake import intake_store
from app.intake.record_service import IntakeNotFoundError
from app.intake.schema import IntakeRecord, IntakeStatus

INVALID_COMPONENT_FIXTURE = "[[fixture:invalid-component]]"


def _pending_findings(record: IntakeRecord) -> list[Finding]:
    """Repository findings that the user has not confirmed or corrected yet."""
    try:
        from app.repo_analysis.findings_store import load_findings
    except ImportError:  # pragma: no cover - repo analysis not installed yet
        return []
    pending: list[Finding] = []
    findings: list[Finding] = []
    for item in load_findings(record.meta.intake_id):
        payload = item.model_dump() if hasattr(item, "model_dump") else item
        try:
            findings.append(Finding.model_validate(payload))
        except ValueError:
            continue
    for finding in findings:
        try:
            field = record.get_field(finding.field)
        except KeyError:
            continue
        if not field.confirmed and field.source != "user":
            pending.append(finding)
    return pending


def get_next_questions(tool_context: ToolContext, resume: bool = False) -> dict[str, Any]:
    """Work out what still needs the user and return the next step to render.

    Returns at most three questions plus any assumptions to confirm, a ``surface_id`` for
    the step, the ``previous_surface_id`` to delete, and ``render_plan``: the exact
    operations to pass to render_ui (target "interview"). Returns ``done: true`` when nothing
    is left; then call finalize_intake. The server decides what is required; do not add or
    skip questions.

    Args:
        resume: True when the user reloaded the page and asked to resume: the current step
            is rendered again without counting its questions twice.
    """
    try:
        record = load_intake(tool_context)
    except IntakeNotFoundError as error:
        return tool_error(f"intake not found: {error}")
    previous = load_step(record.meta.intake_id)
    if resume and previous is not None and previous.kind not in {"done"}:
        step = previous.model_copy(update={"previous_surface_id": None})
    else:
        step_number = (previous.step_number + 1) if previous else 1
        previous_surface_id = previous.surface_id if previous and previous.kind != "done" else None
        findings = _pending_findings(record) if record.meta.mode.value == "existing" else []
        step = build_step(
            record,
            step_number=step_number,
            previous_surface_id=previous_surface_id,
            findings=findings,
        )
        if step.questions:
            record.meta.question_count += len(step.questions)
    if step.kind == "escalation":
        record.meta.status = IntakeStatus.ESCALATED
    intake_store.save_record(record, current_step=step.model_dump(mode="json"))
    publish_state(
        tool_context,
        record,
        step=step,
        status=None if step.kind == "done" else "Preparing the next step…",
    )
    response: dict[str, Any] = {
        "status": "ok",
        "done": step.kind == "done",
        "kind": step.kind,
        "step_number": step.step_number,
        "surface_id": step.surface_id,
        "previous_surface_id": step.previous_surface_id,
        "section": step.section.value if step.section else None,
        "question_count": record.meta.question_count,
        "assumptions": [chip.model_dump(mode="json") for chip in step.assumptions],
        "questions": [question.model_dump(mode="json") for question in step.questions],
        "findings_count": len(step.findings),
        "render_plan": {"target": TARGET_ID, "operations": build_operations(step)},
    }
    if step.kind == "done":
        response["next"] = "Call finalize_intake now."
    elif step.kind == "escalation":
        response["next"] = "Call render_ui with render_plan, then stop."
    else:
        response["next"] = (
            "Call render_ui with target 'interview' and operations = [] (the server renders "
            "render_plan). Only pass render_plan.operations yourself to rephrase the root "
            "'intro' (two sentences at most)."
        )
    description = str(record.project.description.value or "")
    if INVALID_COMPONENT_FIXTURE in description and step.step_number == 1:
        response["fixture"] = {
            "name": "invalid-component",
            "operations": invalid_operations_fixture(step),
        }
    return response


__all__ = ["INVALID_COMPONENT_FIXTURE", "Step", "get_next_questions"]
