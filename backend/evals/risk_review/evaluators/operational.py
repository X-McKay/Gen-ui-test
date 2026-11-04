"""Operational evaluator: latency, requests, tokens and cost per run, plus distributions."""

from __future__ import annotations

import math
from collections.abc import Sequence

from pydantic import BaseModel

from evals.risk_review.cases import EvalCase
from risk_review.observability.trace import RunMetrics


class OperationalScores(BaseModel):
    latency_s: float
    model_requests: int
    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    total_tokens: int
    tool_calls: int
    estimated_cost_usd: float
    budget_violations: int
    latency_ok: bool
    requests_ok: bool
    tokens_ok: bool

    @property
    def passed(self) -> bool:
        return (
            self.latency_ok and self.requests_ok and self.tokens_ok and self.budget_violations == 0
        )


def score_operational(case: EvalCase, metrics: RunMetrics) -> OperationalScores:
    latency = metrics.duration_ms / 1000
    total = metrics.total_tokens
    limits = case.operational
    return OperationalScores(
        latency_s=round(latency, 1),
        model_requests=metrics.model_requests,
        input_tokens=metrics.input_tokens,
        output_tokens=metrics.output_tokens,
        thinking_tokens=metrics.thinking_tokens,
        total_tokens=total,
        tool_calls=metrics.tool_calls,
        estimated_cost_usd=metrics.estimated_cost_usd,
        budget_violations=len(metrics.budget_violations),
        latency_ok=latency <= limits.max_latency_s,
        requests_ok=metrics.model_requests <= limits.max_model_requests,
        tokens_ok=total <= limits.max_total_tokens,
    )


def percentile(values: Sequence[float], fraction: float) -> float:
    """Nearest-rank percentile; 0 for an empty sequence."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(fraction * len(ordered)))
    return float(ordered[rank - 1])
