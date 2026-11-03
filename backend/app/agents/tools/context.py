"""Helpers shared by the agent tools: locating the intake and publishing shared state."""

from __future__ import annotations

import logging
from typing import Any

from ag_ui_adk import CONTEXT_STATE_KEY
from google.adk.tools.tool_context import ToolContext

from app.agents.surface_plan import Step
from app.intake import repository
from app.intake.record_service import IntakeNotFoundError, get_record
from app.intake.schema import IntakeRecord

logger = logging.getLogger(__name__)

THREAD_ID_STATE_KEY = "_ag_ui_thread_id"
RECORD_STATE_KEY = "intake_record"
STEP_STATE_KEY = "intake_step"
STATUS_STATE_KEY = "intake_status"

__all__ = [
    "CONTEXT_STATE_KEY",
    "RECORD_STATE_KEY",
    "STATUS_STATE_KEY",
    "STEP_STATE_KEY",
    "intake_id_from",
    "load_intake",
    "load_step",
    "publish_state",
    "tool_error",
]


def intake_id_from(tool_context: ToolContext) -> str:
    """The intake id is the AG-UI thread id (the frontend sets ``threadId`` = intake id)."""
    explicit = tool_context.state.get("intake_id")
    if isinstance(explicit, str) and explicit:
        return explicit
    thread_id = tool_context.state.get(THREAD_ID_STATE_KEY)
    if isinstance(thread_id, str) and thread_id:
        return thread_id
    raise IntakeNotFoundError("no intake id in session state")


def load_intake(tool_context: ToolContext) -> IntakeRecord:
    return get_record(intake_id_from(tool_context))


def load_step(intake_id: str) -> Step | None:
    raw = repository.load_current_step(intake_id)
    if raw is None:
        return None
    return Step.model_validate(raw)


def publish_state(
    tool_context: ToolContext,
    record: IntakeRecord,
    *,
    step: Step | None = None,
    status: str | None = None,
) -> None:
    """Write the shared state that AG-UI streams to the browser as STATE_DELTA events."""
    tool_context.state[RECORD_STATE_KEY] = record.model_dump(mode="json")
    if step is not None:
        tool_context.state[STEP_STATE_KEY] = step.model_dump(mode="json")
    if status is not None:
        tool_context.state[STATUS_STATE_KEY] = status


def tool_error(message: str, **extra: Any) -> dict[str, Any]:
    logger.warning("tool.error", extra={"detail": message})
    return {"status": "error", "error": message, **extra}
