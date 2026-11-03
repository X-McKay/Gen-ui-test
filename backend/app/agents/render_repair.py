"""Repairs the model's ``render_ui`` call so the current step always reaches the screen.

The model copies the server's render plan into ``render_ui``; a mid-sized model sometimes
drops children or mangles props while copying 5 kB of JSON. Since the plan is deterministic
(it is rebuilt from the stored step), the server restores it after the model call and keeps
only what the model is meant to decide: the intro text. Calls that do not target the current
step's surface (for example the guardrail fixture) are left untouched, so the runtime's
validation and self-correction path stays exercised.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse

from app.agents.surface_plan import TARGET_ID, Step, build_operations
from app.agents.tools.context import THREAD_ID_STATE_KEY, load_step

logger = logging.getLogger(__name__)

RENDER_TOOL = "render_ui"
MAX_INTRO_CHARS = 320
MAX_INTRO_SENTENCES = 2
_SENTENCE_SPLIT = re.compile(r"[.!?]+(?:\s|$)")


def _surface_ids(operations: list[Any]) -> set[str]:
    ids: set[str] = set()
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        for key, body in operation.items():
            if (
                key != "version"
                and isinstance(body, dict)
                and isinstance(body.get("surfaceId"), str)
            ):
                ids.add(body["surfaceId"])
    return ids


def _model_intro(operations: list[Any]) -> str | None:
    """The intro the model wrote on the root component, when it is short and plain."""
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        for key, body in operation.items():
            if key == "version" or not isinstance(body, dict):
                continue
            for component in body.get("components") or []:
                if not isinstance(component, dict) or component.get("id") != "root":
                    continue
                intro = component.get("intro")
                if not isinstance(intro, str):
                    return None
                intro = " ".join(intro.split())
                sentences = [s for s in _SENTENCE_SPLIT.split(intro) if s.strip()]
                if 0 < len(intro) <= MAX_INTRO_CHARS and len(sentences) <= MAX_INTRO_SENTENCES:
                    return intro
                return None
    return None


def repair_operations(args: dict[str, Any], step: Step) -> dict[str, Any] | None:
    """Return repaired ``render_ui`` args for ``step``, or None when no repair applies."""
    if args.get("target") != TARGET_ID:
        return None
    operations = args.get("operations")
    if not isinstance(operations, list):
        return None
    # Two shapes trigger the repair: the plan copied (perhaps imperfectly) for this step's
    # surface, or the short form ``operations=[]`` that asks the server to render the plan.
    if operations and step.surface_id not in _surface_ids(operations):
        return None
    planned = build_operations(step)
    intro = _model_intro(operations)
    if intro:
        for operation in planned:
            body = operation.get("createSurface")
            if isinstance(body, dict):
                for component in body.get("components") or []:
                    if component.get("id") == "root" and "intro" in component:
                        component["intro"] = intro
    if operations == planned:
        return None
    return {"target": TARGET_ID, "operations": planned}


def repair_render_ui_response(
    callback_context: CallbackContext, llm_response: LlmResponse
) -> LlmResponse | None:
    """ADK ``after_model_callback``: restore the plan behind every ``render_ui`` call."""
    content = llm_response.content
    if content is None or not content.parts:
        return None
    calls = [part.function_call for part in content.parts if part.function_call]
    logger.debug(
        "render_ui.callback",
        extra={
            "calls": [call.name for call in calls],
            "partial": llm_response.partial,
            "state_keys": sorted(str(key) for key in callback_context.state),
        },
    )
    if not any(call.name == RENDER_TOOL for call in calls):
        return None
    intake_id = callback_context.state.get(THREAD_ID_STATE_KEY)
    if not isinstance(intake_id, str):
        return None
    step = load_step(intake_id)
    if step is None:
        return None
    changed = False
    for call in calls:
        if call.name != RENDER_TOOL or not isinstance(call.args, dict):
            continue
        repaired = repair_operations(dict(call.args), step)
        if repaired is None:
            continue
        call.args = repaired
        changed = True
    if changed:
        logger.info(
            "render_ui.repaired",
            extra={"intake_id": intake_id, "surface_id": step.surface_id, "kind": step.kind},
        )
        return llm_response
    return None
