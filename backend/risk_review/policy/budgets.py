"""Budget enforcement as ADK model callbacks. Attached by the factory, never by the agent.

``before_model`` watches the request, token and tool budgets. The first time a budget is
spent it grants one **grace request**: the conversation gets a budget notice and only the
delivery tools stay available, so the agent can still hand in what it has. The next request
ends the turn with a plain text response and the run reports ``budget_exhausted``.
``after_model`` records token usage and latency from the provider's usage metadata.
"""

from __future__ import annotations

from typing import Any

from google.adk.agents.context import Context
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from risk_review.observability.trace import RunLedger, ledger_for_state
from risk_review.policy.delivery import DELIVERY_TOOLS, GRACE_NOTICE

BUDGET_EXHAUSTED_TEXT = "Budget exhausted; stopping without a complete result."


def _restrict_to_delivery_tools(llm_request: LlmRequest) -> None:
    config = llm_request.config
    if config is None or not config.tools:
        return
    kept: list[Any] = []
    for tool in config.tools:
        declarations = getattr(tool, "function_declarations", None)
        if not declarations:
            continue
        delivery = [d for d in declarations if d.name in DELIVERY_TOOLS]
        if delivery:
            kept.append(types.Tool(function_declarations=delivery))
    config.tools = kept or None
    llm_request.tools_dict = {
        name: tool for name, tool in llm_request.tools_dict.items() if name in DELIVERY_TOOLS
    }


def _grant_grace(ledger: RunLedger, llm_request: LlmRequest, reason: str) -> None:
    ledger.grace_used = True
    ledger.budget_violation(reason)
    llm_request.contents.append(types.Content(role="user", parts=[types.Part(text=GRACE_NOTICE)]))
    _restrict_to_delivery_tools(llm_request)


def before_model(context: Context, llm_request: LlmRequest) -> LlmResponse | None:
    ledger = ledger_for_state(context.state)
    if ledger is None:
        return None
    if ledger.grace_used:
        # The grace request was the last one; whatever came back is the result.
        violations = ledger.metrics.budget_violations
        ledger.metrics.outcome = "budget_exhausted"
        ledger.metrics.outcome_detail = violations[-1] if violations else "grace request used"
        return LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=BUDGET_EXHAUSTED_TEXT)]),
            turn_complete=True,
        )
    reason: str | None = ledger.model_request_allowed()
    if reason is None and ledger.tool_calls_remaining == 0:
        reason = f"max_tool_calls={ledger.budgets.max_tool_calls} reached"
    if reason is not None:
        _grant_grace(ledger, llm_request, reason)
    ledger.model_request_started()
    return None


def after_model(context: Context, llm_response: LlmResponse) -> LlmResponse | None:
    ledger = ledger_for_state(context.state)
    if ledger is None or llm_response.partial:
        return None
    usage = llm_response.usage_metadata
    ledger.model_request_finished(
        input_tokens=int(getattr(usage, "prompt_token_count", 0) or 0),
        output_tokens=int(getattr(usage, "candidates_token_count", 0) or 0),
        thinking_tokens=int(getattr(usage, "thoughts_token_count", 0) or 0),
        finish_reason=str(llm_response.finish_reason) if llm_response.finish_reason else None,
    )
    return None
