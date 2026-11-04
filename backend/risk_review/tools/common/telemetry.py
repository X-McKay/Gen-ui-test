"""Tool telemetry and the tool-call budget, as ADK tool callbacks attached by the factory.

Records tool name, outcome, latency and output size per call. Arguments and results are
never written anywhere: the trace is safe to keep.
"""

from __future__ import annotations

import json
import time
from typing import Any

from google.adk.agents.context import Context
from google.adk.tools.base_tool import BaseTool

from risk_review.observability.trace import ledger_for_state
from risk_review.policy.delivery import DELIVERY_TOOL_STATE_KEY, DELIVERY_TOOLS, soft_notice
from risk_review.tools.common.errors import limit_exceeded

_STARTED_KEY = "_risk_review_tool_started"


def _outcome_of(result: dict[str, Any]) -> str:
    if result.get("ok") is False:
        return str(result.get("kind", "error"))
    return "success"


def before_tool(tool: BaseTool, args: dict[str, Any], context: Context) -> dict[str, Any] | None:
    ledger = ledger_for_state(context.state)
    if ledger is not None and tool.name not in DELIVERY_TOOLS:
        reason = ledger.tool_call_allowed()
        if reason is not None:
            ledger.budget_violation(reason)
            ledger.tool_call(
                name=tool.name, outcome="limit_exceeded", duration_ms=0, output_bytes=0
            )
            return limit_exceeded(
                f"Tool budget spent ({reason}); report what you have."
            ).model_dump()
    started: dict[str, float] = dict(context.state.get(_STARTED_KEY) or {})
    started[tool.name] = time.perf_counter()
    context.state[_STARTED_KEY] = started
    return None


def after_tool(
    tool: BaseTool, args: dict[str, Any], context: Context, result: dict[str, Any]
) -> dict[str, Any] | None:
    started: dict[str, float] = dict(context.state.get(_STARTED_KEY) or {})
    began = started.pop(tool.name, None)
    context.state[_STARTED_KEY] = started
    duration_ms = int((time.perf_counter() - began) * 1000) if began is not None else 0
    ledger = ledger_for_state(context.state)
    if ledger is None:
        return None
    ledger.tool_call(
        name=tool.name,
        outcome=_outcome_of(result),
        duration_ms=duration_ms,
        output_bytes=len(json.dumps(result, default=str)),
    )
    remaining = ledger.tool_calls_remaining
    if tool.name not in DELIVERY_TOOLS and remaining <= max(3, ledger.budgets.max_tool_calls // 5):
        delivery = str(context.state.get(DELIVERY_TOOL_STATE_KEY) or "report_findings")
        return {**result, "budget_notice": soft_notice(remaining, delivery)}
    return None
