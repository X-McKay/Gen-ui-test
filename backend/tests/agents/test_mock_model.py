"""The scripted model follows the same protocol as the live model."""

from __future__ import annotations

import json
from typing import Any

from google.adk.models.llm_request import LlmRequest
from google.genai import types

from app.inference.mock_model import ScriptedLlm, parse_submitted_step


def _request(*contents: types.Content, with_render: bool = True) -> LlmRequest:
    request = LlmRequest(contents=list(contents))
    names = [
        "extract_intake_facts",
        "get_next_questions",
        "update_intake_fields",
        "finalize_intake",
    ]
    if with_render:
        names.append("render_ui")
    request.config.tools = [
        types.Tool(function_declarations=[types.FunctionDeclaration(name=name) for name in names])
    ]
    return request


def _user(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=text)])


def _call(name: str, args: dict[str, Any]) -> types.Content:
    return types.Content(
        role="model", parts=[types.Part(function_call=types.FunctionCall(name=name, args=args))]
    )


def _result(name: str, response: dict[str, Any]) -> types.Content:
    return types.Content(
        role="user",
        parts=[types.Part(function_response=types.FunctionResponse(name=name, response=response))],
    )


def _first_call(request: LlmRequest) -> tuple[str, dict[str, Any]] | None:
    response = ScriptedLlm().decide(request)
    assert response.content is not None
    for part in response.content.parts or []:
        if part.function_call:
            return str(part.function_call.name), dict(part.function_call.args or {})
    return None


def test_first_user_message_triggers_extraction() -> None:
    assert _first_call(_request(_user("Start the intake.\n\nA tool."))) == (
        "extract_intake_facts",
        {"text": "Start the intake.\n\nA tool."},
    )


def test_extraction_result_leads_to_gap_analysis() -> None:
    request = _request(
        _user("x"),
        _call("extract_intake_facts", {"text": "x"}),
        _result("extract_intake_facts", {"status": "ok"}),
    )
    assert _first_call(request) == ("get_next_questions", {})


def test_plan_is_rendered_through_render_ui() -> None:
    plan = {
        "target": "interview",
        "operations": [{"version": "1.0", "createSurface": {"surfaceId": "step-1"}}],
    }
    request = _request(
        _user("x"),
        _result("get_next_questions", {"status": "ok", "done": False, "render_plan": plan}),
    )
    assert _first_call(request) == (
        "render_ui",
        {"target": "interview", "operations": plan["operations"]},
    )


def test_done_leads_to_finalize() -> None:
    request = _request(_user("x"), _result("get_next_questions", {"status": "ok", "done": True}))
    assert _first_call(request) == ("finalize_intake", {})


def test_submitted_step_is_parsed_into_field_updates() -> None:
    text = (
        "Submitted step 1\n\n"
        'answers: {"ai_system.uses_ai": true}\n'
        'assumptions: {"use_case.domains": ["other"]}\n'
        'notSure: ["data.processes_personal_data"]'
    )
    fields = parse_submitted_step(text)
    assert fields == [
        {"path": "use_case.domains", "value": ["other"]},
        {"path": "ai_system.uses_ai", "value": True},
        {"path": "data.processes_personal_data", "value": "unknown"},
    ]
    assert _first_call(_request(_user(text))) == ("update_intake_fields", {"fields": fields})


def test_rejected_fixture_render_is_corrected_from_the_plan() -> None:
    plan = {
        "target": "interview",
        "operations": [{"version": "1.0", "createSurface": {"surfaceId": "step-1"}}],
    }
    invalid = [{"version": "1.0", "createSurface": {"surfaceId": "step-1-invalid"}}]
    request = _request(
        _user("x"),
        _result(
            "get_next_questions",
            {
                "status": "ok",
                "done": False,
                "render_plan": plan,
                "fixture": {"name": "invalid-component", "operations": invalid},
            },
        ),
        _call("render_ui", {"target": "interview", "operations": invalid}),
        _result(
            "render_ui",
            {
                "result": json.dumps(
                    {
                        "status": "rendered",
                        "applied": 0,
                        "rejected": [{"index": 0, "reason": "unknown component"}],
                    }
                )
            },
        ),
    )
    assert _first_call(request) == (
        "render_ui",
        {"target": "interview", "operations": plan["operations"]},
    )


def test_resume_message_uses_resume_flag() -> None:
    assert _first_call(_request(_user("Resume the interview where we left off."))) == (
        "get_next_questions",
        {"resume": True},
    )


def test_without_render_tool_the_model_only_talks() -> None:
    plan = {"target": "interview", "operations": []}
    request = _request(
        _user("x"),
        _result("get_next_questions", {"status": "ok", "done": False, "render_plan": plan}),
        with_render=False,
    )
    assert _first_call(request) is None
