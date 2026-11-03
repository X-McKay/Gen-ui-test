"""Tool: extract intake facts from the project description."""

from __future__ import annotations

from typing import Any

from google.adk.tools.tool_context import ToolContext

from app.agents.tools.context import load_intake, publish_state, tool_error
from app.inference.structured_extraction import extract_fields
from app.intake.gap_analysis import assumptions
from app.intake.record_service import FieldUpdate, IntakeNotFoundError, apply_updates


async def extract_intake_facts(text: str, tool_context: ToolContext) -> dict[str, Any]:
    """Read the project description and fill every intake field it supports.

    Call this once, first, with the description. Each extracted value is stored as an
    inference with a confidence score; nothing is confirmed yet. Returns how many fields
    were filled and how many assumptions the user must confirm.

    Args:
        text: The project description. Pass an empty string to use the description on file.
    """
    try:
        record = load_intake(tool_context)
    except IntakeNotFoundError as error:
        return tool_error(f"intake not found: {error}")
    description = str(record.project.description.value or "").strip() or text.strip()
    if not description:
        return tool_error("no description to read")
    publish_state(tool_context, record, status="Reading your description…")
    extracted = await extract_fields(description, context="project description")
    updates = [
        FieldUpdate(
            path=field.path,
            value=field.value,
            source="inferred",
            confidence=field.confidence,
            confirmed=False,
        )
        for field in extracted
    ]
    record, applied, rejected = apply_updates(record, updates, policy="inferred")
    chips = assumptions(record)
    publish_state(tool_context, record, status="Checking what we understood…")
    return {
        "status": "ok",
        "fields_filled": len(applied),
        "assumptions_to_confirm": len(chips),
        "rejected": rejected,
        "next": "Call get_next_questions now.",
    }
