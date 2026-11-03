"""Structured extraction of intake facts from free text, via tool calling.

The tool schema is generated from the question bank (which is generated from the Pydantic
model), so both providers run the same contract. No provider-specific JSON mode is used.
``MOCK_MODEL=1`` routes to the keyword extractor instead.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.inference.model_factory import completion_kwargs
from app.intake.heuristic_extractor import extract_heuristically
from app.intake.question_bank import QUESTION_BANK, QuestionSpec
from app.settings import get_settings

logger = logging.getLogger(__name__)

EXTRACTION_TOOL_NAME = "record_intake_facts"


class ExtractedField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    value: object
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str | None = Field(default=None, description="Short quote that supports the value")


def _value_schema(spec: QuestionSpec) -> dict[str, Any]:
    if spec.control == "yes_no":
        return {"type": "boolean"}
    if spec.control == "choice":
        return {"type": "string", "enum": [option.value for option in spec.options]}
    if spec.control == "multi":
        return {
            "type": "array",
            "items": {"type": "string", "enum": [o.value for o in spec.options]},
        }
    return {"type": "string", "maxLength": 500}


def extraction_tool_schema() -> dict[str, Any]:
    """OpenAI-style tool definition with one property per askable field."""
    properties: dict[str, Any] = {}
    for spec in QUESTION_BANK:
        properties[spec.field.replace(".", "__")] = {
            "type": "object",
            "description": spec.prompt,
            "properties": {
                "value": _value_schema(spec),
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": "How sure you are, 0 to 1. Use ≥ 0.8 only when the text says so.",  # noqa: E501
                },
                "evidence": {"type": "string", "description": "Short quote from the text"},
            },
            "required": ["value", "confidence"],
        }
    return {
        "type": "function",
        "function": {
            "name": EXTRACTION_TOOL_NAME,
            "description": (
                "Record every intake fact that the text supports. Leave out fields the text "
                "says nothing about. A clear description of an unrelated system is evidence "
                "that sensitive practices are absent: record those as false with confidence ≥ 0.8."
            ),
            "parameters": {
                "type": "object",
                "properties": properties,
                "additionalProperties": False,
            },
        },
    }


SYSTEM_PROMPT = (
    "You extract facts for an AI governance intake. Read the project description and call "
    f"{EXTRACTION_TOOL_NAME} exactly once with every field the text supports. Never invent "
    "details; use confidence below 0.8 for guesses. Do not reply with prose."
)


def parse_tool_arguments(arguments: str | dict[str, Any]) -> list[ExtractedField]:
    data: dict[str, Any] = json.loads(arguments) if isinstance(arguments, str) else arguments
    specs = {spec.field.replace(".", "__"): spec for spec in QUESTION_BANK}
    fields: list[ExtractedField] = []
    for key, raw in data.items():
        spec = specs.get(key)
        if spec is None or not isinstance(raw, dict) or raw.get("value") is None:
            continue
        try:
            confidence = float(raw.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        evidence = raw.get("evidence")
        fields.append(
            ExtractedField(
                path=spec.field,
                value=raw["value"],
                confidence=max(0.0, min(1.0, confidence)),
                evidence=str(evidence)[:200] if evidence else None,
            )
        )
    return fields


async def extract_fields(text: str, *, context: str | None = None) -> list[ExtractedField]:
    """Extract intake facts from ``text``. ``context`` names the source (description, repo)."""
    settings = get_settings()
    if settings.mock_model:
        return extract_heuristically(text)
    import litellm

    user_content = text if not context else f"Source: {context}\n\n{text}"
    started = time.perf_counter()
    response = await litellm.acompletion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        tools=[extraction_tool_schema()],
        tool_choice={"type": "function", "function": {"name": EXTRACTION_TOOL_NAME}},
        temperature=0,
        max_tokens=4000,
        **completion_kwargs(settings),
    )
    message = response.choices[0].message
    usage = getattr(response, "usage", None)
    logger.info(
        "inference.extraction",
        extra={
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "tool_calls": [call.function.name for call in (message.tool_calls or [])],
        },
    )
    fields: list[ExtractedField] = []
    for call in message.tool_calls or []:
        if call.function.name != EXTRACTION_TOOL_NAME:
            continue
        try:
            fields.extend(parse_tool_arguments(call.function.arguments))
        except json.JSONDecodeError:
            logger.warning("inference.extraction.invalid_json")
    return fields
