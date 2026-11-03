"""Tool: apply the user's confirmations, edits and answers to the record."""

from __future__ import annotations

from typing import Any

from google.adk.tools.tool_context import ToolContext

from app.agents.tools.context import load_intake, publish_state, tool_error
from app.intake.record_service import FieldUpdate, IntakeNotFoundError, apply_updates
from app.intake.schema import UNKNOWN


def _normalise(fields: list[dict[str, Any]]) -> list[FieldUpdate]:
    """Accept ``[{path, value}]`` objects; ``"unknown"``/``null`` means not sure."""
    pairs: list[tuple[str, object]] = []
    for item in fields:
        getter = getattr(item, "get", None)
        if getter is None:
            continue
        path = getter("path") or getter("field")
        if isinstance(path, str):
            pairs.append((path, getter("value")))
    updates: list[FieldUpdate] = []
    for path, value in pairs:
        normalised = UNKNOWN if value is None or value == "not_sure" else value
        updates.append(FieldUpdate(path=path, value=normalised, source="user", confidence=1.0))
    return updates


def update_intake_fields(fields: list[dict[str, Any]], tool_context: ToolContext) -> dict[str, Any]:
    """Store what the user confirmed, corrected or answered.

    Call this with every value from a submitted step: confirmed assumptions, edited
    assumptions and answers, in one call. Values are stored as user-confirmed. Use the string
    "unknown" when the user chose Not sure; never store false for Not sure.

    Args:
        fields: A list of {"path": "<section.field>", "value": <value>} objects.
    """
    try:
        record = load_intake(tool_context)
    except IntakeNotFoundError as error:
        return tool_error(f"intake not found: {error}")
    updates = _normalise(fields)
    if not updates:
        return tool_error("no fields given; pass [{path, value}] objects")
    record, applied, rejected = apply_updates(record, updates, policy="user")
    publish_state(tool_context, record, status="Saved. Working out what is left…")
    return {
        "status": "ok",
        "applied": applied,
        "rejected": rejected,
        "classification": record.assessment.eu_ai_act.classification.value,
        "next": "Call get_next_questions now.",
    }
