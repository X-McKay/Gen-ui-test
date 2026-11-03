"""ADK agent wiring: the LlmAgent, its instruction provider and the AG-UI adapter."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ag_ui_adk import ADKAgent, AGUIToolset
from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext

from app.agents.tools import (
    extract_intake_facts,
    finalize_intake,
    get_next_questions,
    update_intake_fields,
)
from app.agents.tools.context import CONTEXT_STATE_KEY, RECORD_STATE_KEY, STEP_STATE_KEY
from app.inference.model_factory import create_agent_model
from app.settings import Settings, get_settings

logger = logging.getLogger(__name__)

INSTRUCTION_PATH = Path(__file__).parent / "prompts" / "intake_instruction.md"
AGENT_NAME = "intake_agent"
RENDER_TOOL_NAME = "render_ui"
APP_NAME = "intake"


def _context_entries(state: dict[str, Any] | Any) -> list[tuple[str, str]]:
    """AG-UI context entries (description, value) that the runtime attached to the run."""
    raw = state.get(CONTEXT_STATE_KEY) if hasattr(state, "get") else None
    entries: list[tuple[str, str]] = []
    if not isinstance(raw, list):
        return entries
    for item in raw:
        if isinstance(item, dict):
            description, value = item.get("description"), item.get("value")
        else:
            description, value = getattr(item, "description", None), getattr(item, "value", None)
        if isinstance(value, str) and value:
            entries.append((str(description or "context"), value))
    return entries


def _record_summary(state: dict[str, Any] | Any) -> str:
    record = state.get(RECORD_STATE_KEY) if hasattr(state, "get") else None
    step = state.get(STEP_STATE_KEY) if hasattr(state, "get") else None
    if not isinstance(record, dict):
        return "No intake loaded yet."
    meta = record.get("meta", {})
    classification = record.get("assessment", {}).get("eu_ai_act", {}).get("classification")
    lines = [
        f"- intake id: {meta.get('intake_id')}",
        f"- mode: {meta.get('mode')}, status: {meta.get('status')}",
        f"- questions asked so far: {meta.get('question_count', 0)}",
        f"- current classification: {classification}",
    ]
    if isinstance(step, dict):
        lines.append(
            f"- last step: {step.get('step_number')} ({step.get('kind')}), "
            f"surface {step.get('surface_id')}"
        )
    return "\n".join(lines)


def build_instruction(context: ReadonlyContext) -> str:
    """Instruction provider: the static rules, the intake summary and the render_ui guide."""
    parts = [INSTRUCTION_PATH.read_text(encoding="utf-8")]
    parts.append("## Current intake\n" + _record_summary(context.state))
    for description, value in _context_entries(context.state):
        parts.append(f"## {description}\n{value}")
    return "\n\n".join(parts)


def create_llm_agent(settings: Settings | None = None) -> LlmAgent:
    settings = settings or get_settings()
    return LlmAgent(
        name=AGENT_NAME,
        description="Runs the AI governance intake interview.",
        model=create_agent_model(settings),
        instruction=build_instruction,
        tools=[
            extract_intake_facts,
            update_intake_fields,
            get_next_questions,
            finalize_intake,
            # Frontend tools arrive per run; only render_ui is exposed to the model.
            AGUIToolset(tool_filter=[RENDER_TOOL_NAME]),
        ],
    )


def create_adk_agent(settings: Settings | None = None) -> ADKAgent:
    settings = settings or get_settings()
    return ADKAgent(
        adk_agent=create_llm_agent(settings),
        app_name=APP_NAME,
        user_id="intake-user",
        use_in_memory_services=True,
    )
