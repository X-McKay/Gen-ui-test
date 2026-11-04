"""Delivery tools: the one call each agent must always be able to make.

They are exempt from the tool-call budget, and when the model budget is spent the agent
gets exactly one grace request in which only these tools are offered.
"""

from __future__ import annotations

DELIVERY_TOOLS: frozenset[str] = frozenset({"report_findings", "record_verdict"})

# Session-state key naming the delivery tool of the running agent (set by the step).
DELIVERY_TOOL_STATE_KEY = "_risk_review_delivery_tool"

GRACE_NOTICE = (
    "BUDGET NOTICE: the review budget is spent. This is your last request. Call your delivery "
    "tool now with everything you have (status `budget_exhausted`, or verdict `uncertain` with "
    "what would settle it). No other tool is available."
)


def soft_notice(remaining: int, delivery_tool: str) -> str:
    return (
        f"BUDGET NOTICE: {remaining} tool call(s) left before the budget ends; "
        f"call {delivery_tool} with what you have before they run out."
    )
