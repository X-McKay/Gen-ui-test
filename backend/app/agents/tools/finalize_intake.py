"""Tool: close the interview and hand over to the review page."""

from __future__ import annotations

from typing import Any

from google.adk.tools.tool_context import ToolContext

from app.agents.surface_plan import Step
from app.agents.tools.context import load_intake, load_step, publish_state, tool_error
from app.intake import repository
from app.intake.gap_analysis import is_complete, section_progress
from app.intake.record_service import IntakeNotFoundError, mark_completed


def finalize_intake(tool_context: ToolContext) -> dict[str, Any]:
    """Finish the intake once get_next_questions reports done.

    Records the completion time and returns the review page path. Call it only after
    get_next_questions returned ``done: true``.
    """
    try:
        record = load_intake(tool_context)
    except IntakeNotFoundError as error:
        return tool_error(f"intake not found: {error}")
    if not is_complete(record):
        return tool_error("the intake is not complete; call get_next_questions first")
    previous = load_step(record.meta.intake_id)
    record = mark_completed(record)
    step = Step(
        step_number=(previous.step_number + 1) if previous else 1,
        surface_id="done",
        previous_surface_id=previous.surface_id if previous else None,
        kind="done",
        intro="That is everything we need.",
        progress=section_progress(record),
    )
    repository.save_current_step(record.meta.intake_id, step.model_dump(mode="json"))
    publish_state(tool_context, record, step=step, status="Done. Opening the review…")
    return {
        "status": "ok",
        "review_path": f"/intake/{record.meta.intake_id}/review",
        "classification": record.assessment.eu_ai_act.classification.value,
        "question_count": record.meta.question_count,
        "next": "Tell the user the review is ready in one sentence. Do not render anything.",
    }
