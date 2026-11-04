"""Ledger, budget callbacks and the content-free trace (RR-04, RR-05)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.tools.base_tool import BaseTool
from google.genai import types

from risk_review.observability.trace import (
    RUN_ID_STATE_KEY,
    Budgets,
    RunLedger,
    register_ledger,
    release_ledger,
)
from risk_review.policy.budgets import BUDGET_EXHAUSTED_TEXT, after_model, before_model
from risk_review.policy.delivery import DELIVERY_TOOL_STATE_KEY, GRACE_NOTICE
from risk_review.tools.common.telemetry import after_tool, before_tool


def _budgets(**overrides: int) -> Budgets:
    base = {
        "max_requests": 3,
        "max_input_tokens": 10_000,
        "max_output_tokens": 1_000,
        "max_tool_calls": 2,
        "max_cost_usd": 0,
    }
    base.update(overrides)
    return Budgets.model_validate(base)


def _context(run_id: str) -> Any:
    return SimpleNamespace(
        state={RUN_ID_STATE_KEY: run_id, DELIVERY_TOOL_STATE_KEY: "report_findings"}
    )


def _request() -> LlmRequest:
    request = LlmRequest()
    request.config.tools = [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(name="read_file"),
                types.FunctionDeclaration(name="report_findings"),
            ]
        )
    ]
    request.tools_dict = {"read_file": SimpleNamespace(), "report_findings": SimpleNamespace()}  # type: ignore[dict-item]
    return request


def _tool(name: str) -> BaseTool:
    return SimpleNamespace(name=name)  # type: ignore[return-value]


def test_model_budget_grants_one_grace_request_then_ends_the_turn(tmp_path: Path) -> None:
    ledger = RunLedger(run_id="r1", agent="a", manifest_id="m", budgets=_budgets(max_requests=1))
    register_ledger(ledger)
    try:
        context = _context("r1")
        assert before_model(context, _request()) is None
        response = LlmResponse(
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=500, candidates_token_count=50, thoughts_token_count=25
            ),
            finish_reason=types.FinishReason.STOP,
        )
        after_model(context, response)
        # Budget spent: the next request is the grace request, restricted to delivery tools.
        grace = _request()
        assert before_model(context, grace) is None
        assert grace.contents[-1].parts is not None
        assert grace.contents[-1].parts[0].text == GRACE_NOTICE
        assert grace.config.tools is not None
        names = [d.name for tool in grace.config.tools for d in tool.function_declarations or []]
        assert names == ["report_findings"] and list(grace.tools_dict) == ["report_findings"]
        after_model(context, response)
        # After the grace request the turn ends with a plain text response.
        stop = before_model(context, _request())
        assert stop is not None and stop.content is not None
        assert stop.content.parts is not None
        assert stop.content.parts[0].text == BUDGET_EXHAUSTED_TEXT
        metrics = ledger.finish()
        assert metrics.outcome == "budget_exhausted" and metrics.model_requests == 2
        tokens = (metrics.input_tokens, metrics.output_tokens, metrics.thinking_tokens)
        assert tokens == (1000, 100, 50)
        assert metrics.budget_violations == ["max_requests=1 reached"]
    finally:
        release_ledger("r1")


def test_spent_tool_budget_triggers_the_grace_request() -> None:
    ledger = RunLedger(run_id="r5", agent="a", manifest_id="m", budgets=_budgets(max_tool_calls=1))
    register_ledger(ledger)
    try:
        context = _context("r5")
        assert before_tool(_tool("read_file"), {}, context) is None
        after_tool(_tool("read_file"), {}, context, {"ok": True})
        grace = _request()
        assert before_model(context, grace) is None
        assert ledger.grace_used and grace.contents[-1].parts is not None
        # Exactly one grace request, even though the request budget itself is not spent.
        stop = before_model(context, _request())
        assert stop is not None and ledger.metrics.outcome == "budget_exhausted"
    finally:
        release_ledger("r5")


def test_tool_budget_short_circuits_the_call() -> None:
    ledger = RunLedger(run_id="r2", agent="a", manifest_id="m", budgets=_budgets(max_tool_calls=1))
    register_ledger(ledger)
    try:
        context = _context("r2")
        assert before_tool(_tool("read_file"), {}, context) is None
        after_tool(_tool("read_file"), {}, context, {"ok": True})
        blocked = before_tool(_tool("read_file"), {}, context)
        assert blocked is not None and blocked["kind"] == "limit_exceeded"
        # The delivery tool is exempt from the tool budget.
        assert before_tool(_tool("report_findings"), {}, context) is None
        after_tool(_tool("report_findings"), {}, context, {"ok": True})
        metrics = ledger.finish()
        assert metrics.tool_calls == 3 and metrics.tool_errors == 1
        assert metrics.tool_calls_by_name == {"read_file": 2, "report_findings": 1}
    finally:
        release_ledger("r2")


def test_callbacks_are_inert_without_a_ledger() -> None:
    context = SimpleNamespace(state={})
    assert before_model(context, SimpleNamespace()) is None  # type: ignore[arg-type]
    assert before_tool(_tool("x"), {}, context) is None  # type: ignore[arg-type]


def test_trace_contains_counts_not_content(tmp_path: Path) -> None:
    trace = tmp_path / "trace.jsonl"
    ledger = RunLedger(
        run_id="r3", agent="a", manifest_id="m", budgets=_budgets(), trace_path=trace
    )
    ledger.model_request_started()
    ledger.model_request_finished(
        input_tokens=10, output_tokens=5, thinking_tokens=0, finish_reason="stop"
    )
    ledger.tool_call(name="read_file", outcome="success", duration_ms=3, output_bytes=1234)
    ledger.finish()
    lines = [json.loads(line) for line in trace.read_text().splitlines()]
    assert [line["event"] for line in lines] == ["model_call", "tool_call", "run_finished"]
    assert lines[1]["output_bytes"] == 1234 and "args" not in lines[1] and "result" not in lines[1]
    assert all({"run_id", "agent", "manifest_id", "time"} <= set(line) for line in lines)


def test_cost_estimate_uses_price_table() -> None:
    ledger = RunLedger(
        run_id="r4", agent="a", manifest_id="m", budgets=_budgets(), price_per_million=(1.0, 2.0)
    )
    ledger.model_request_started()
    ledger.model_request_finished(
        input_tokens=1_000_000, output_tokens=500_000, thinking_tokens=0, finish_reason=None
    )
    assert ledger.finish().estimated_cost_usd == 2.0


def test_soft_notice_is_appended_when_few_tool_calls_remain() -> None:
    ledger = RunLedger(run_id="r6", agent="a", manifest_id="m", budgets=_budgets(max_tool_calls=10))
    register_ledger(ledger)
    try:
        context = _context("r6")
        for _ in range(6):
            before_tool(_tool("search_text"), {}, context)
            assert after_tool(_tool("search_text"), {}, context, {"ok": True}) is None
        before_tool(_tool("search_text"), {}, context)
        noticed = after_tool(_tool("search_text"), {}, context, {"ok": True})
        assert noticed is not None and "3 tool call(s) left" in noticed["budget_notice"]
        assert "report_findings" in noticed["budget_notice"]
    finally:
        release_ledger("r6")
