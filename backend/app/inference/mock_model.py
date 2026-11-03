"""``ScriptedLlm``: a deterministic ADK model for ``MOCK_MODEL=1``.

It drives exactly the same tools and ``render_ui`` calls as the live model, deciding the
next call from the conversation so far: the last user message or the last tool result.
CI and the Playwright mock suites run on it; it never touches the network.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncGenerator
from typing import Any, ClassVar

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

logger = logging.getLogger(__name__)

RENDER_TOOL = "render_ui"
TARGET_ID = "interview"


def _text_response(text: str) -> LlmResponse:
    return LlmResponse(
        content=types.Content(role="model", parts=[types.Part(text=text)]),
        turn_complete=True,
    )


def _call_response(name: str, args: dict[str, Any]) -> LlmResponse:
    part = types.Part(function_call=types.FunctionCall(name=name, args=args))
    return LlmResponse(content=types.Content(role="model", parts=[part]), turn_complete=True)


def _last_function_responses(contents: list[types.Content]) -> list[types.FunctionResponse]:
    """Function responses in the last content block, if that is what the model just got."""
    for content in reversed(contents):
        parts = content.parts or []
        responses = [part.function_response for part in parts if part.function_response]
        if responses:
            return responses
        if any(part.text for part in parts) and content.role == "user":
            return []
    return []


def _last_user_text(contents: list[types.Content]) -> str | None:
    for content in reversed(contents):
        if content.role != "user":
            continue
        parts = content.parts or []
        if any(part.function_response for part in parts):
            return None
        texts = [part.text for part in parts if part.text]
        if texts:
            return "\n".join(texts)
    return None


def _last_tool_response(contents: list[types.Content], name: str) -> dict[str, Any] | None:
    for content in reversed(contents):
        for part in content.parts or []:
            response = part.function_response
            if (
                response is not None
                and response.name == name
                and isinstance(response.response, dict)
            ):
                return dict(response.response)
    return None


def _render_call_was_fixture(contents: list[types.Content]) -> bool:
    """True when the most recent render_ui call carried the invalid fixture surface."""
    for content in reversed(contents):
        for part in content.parts or []:
            call = part.function_call
            if call is not None and call.name == RENDER_TOOL:
                return "-invalid" in json.dumps(call.args or {})
    return False


def parse_submitted_step(text: str) -> list[dict[str, Any]] | None:
    """Parse the user message a submitted step produces (``key: json`` lines)."""
    answers: dict[str, Any] = {}
    assumptions: dict[str, Any] = {}
    not_sure: list[str] = []
    found = False
    for line in text.splitlines():
        match = re.match(r"^(answers|assumptions|notSure):\s*(.*)$", line.strip())
        if not match:
            continue
        found = True
        key, raw = match.group(1), match.group(2)
        try:
            value = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            continue
        if key == "answers" and isinstance(value, dict):
            answers = value
        elif key == "assumptions" and isinstance(value, dict):
            assumptions = value
        elif key == "notSure" and isinstance(value, list):
            not_sure = [str(item) for item in value]
    if not found:
        return None
    fields: list[dict[str, Any]] = []
    for path, value in {**assumptions, **answers}.items():
        fields.append({"path": path, "value": value})
    for path in not_sure:
        fields.append({"path": path, "value": "unknown"})
    return fields


class ScriptedLlm(BaseLlm):
    """Deterministic stand-in for the live model."""

    model: str = "scripted/intake"
    supported_model_names: ClassVar[list[str]] = ["scripted/.*"]

    @classmethod
    def supported_models(cls) -> list[str]:
        return cls.supported_model_names

    @staticmethod
    def declared_tool_names(llm_request: LlmRequest) -> set[str]:
        """Every tool the request declares: ADK tools and client proxy tools alike."""
        names = set(llm_request.tools_dict)
        for tool in llm_request.config.tools or []:
            declarations = getattr(tool, "function_declarations", None) or []
            names.update(str(declaration.name) for declaration in declarations if declaration.name)
        return names

    def decide(self, llm_request: LlmRequest) -> LlmResponse:
        contents = llm_request.contents
        can_render = RENDER_TOOL in self.declared_tool_names(llm_request)
        logger.debug("mock.tools", extra={"tools": sorted(self.declared_tool_names(llm_request))})
        responses = _last_function_responses(contents)
        if responses:
            last = responses[-1]
            payload = last.response if isinstance(last.response, dict) else {}
            if last.name in {"extract_intake_facts", "update_intake_fields"}:
                return _call_response("get_next_questions", {})
            if last.name == "get_next_questions":
                return self._after_next_questions(payload, can_render)
            if last.name == RENDER_TOOL:
                return self._after_render(contents, payload)
            if last.name == "finalize_intake":
                return _text_response("The review is ready.")
            return _text_response("")
        text = _last_user_text(contents) or ""
        fields = parse_submitted_step(text)
        if fields is not None:
            return _call_response("update_intake_fields", {"fields": fields})
        lowered = text.lower()
        if "acknowledged the escalation" in lowered:
            return _text_response("Contact the AI governance team before any further work.")
        if lowered.startswith("resume"):
            return _call_response("get_next_questions", {"resume": True})
        if "repository findings" in lowered or "review the findings" in lowered:
            return _call_response("get_next_questions", {})
        return _call_response("extract_intake_facts", {"text": text})

    def _after_next_questions(self, payload: dict[str, Any], can_render: bool) -> LlmResponse:
        if payload.get("status") == "error":
            return _text_response(str(payload.get("error", "Something went wrong.")))
        if payload.get("done"):
            return _call_response("finalize_intake", {})
        plan = payload.get("render_plan") or {}
        operations = plan.get("operations") or []
        if not can_render:
            return _text_response("The next step is ready.")
        fixture = payload.get("fixture")
        if isinstance(fixture, dict) and fixture.get("name") == "invalid-component":
            return _call_response(
                RENDER_TOOL, {"target": TARGET_ID, "operations": fixture.get("operations", [])}
            )
        return _call_response(RENDER_TOOL, {"target": TARGET_ID, "operations": operations})

    def _after_render(self, contents: list[types.Content], payload: dict[str, Any]) -> LlmResponse:
        result: dict[str, Any] = payload
        raw = payload.get("result")
        if isinstance(raw, str):
            try:
                result = json.loads(raw)
            except json.JSONDecodeError:
                result = {}
        elif isinstance(raw, dict):
            result = raw
        rejected = result.get("rejected") or []
        if (rejected or result.get("status") == "error") and _render_call_was_fixture(contents):
            previous = _last_tool_response(contents, "get_next_questions") or {}
            plan = previous.get("render_plan") or {}
            return _call_response(
                RENDER_TOOL, {"target": TARGET_ID, "operations": plan.get("operations") or []}
            )
        return _text_response("")

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        yield self.decide(llm_request)
