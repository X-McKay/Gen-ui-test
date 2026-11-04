"""Per-run ledger and JSONL trace.

The ledger counts model requests, tokens, tool calls and latency for one agent run and
enforces the budgets from the Agent Spec. It is registered under a run id; session state
only carries that id (a string), never the object, so state stays serializable.

Nothing here records prompt or completion text: only sizes, counts, hashes and timings.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

RUN_ID_STATE_KEY = "_risk_review_run_id"

Outcome = Literal[
    "success",
    "needs_information",
    "budget_exhausted",
    "timeout",
    "policy_blocked",
    "failed_transient",
    "failed_permanent",
]


class Budgets(BaseModel):
    """Budget policy from the Agent Spec. Measured first, then given headroom."""

    max_requests: int = Field(ge=1)
    max_input_tokens: int = Field(ge=1)
    max_output_tokens: int = Field(ge=1)
    max_tool_calls: int = Field(ge=0)
    max_cost_usd: float = Field(ge=0)


class ModelCallRecord(BaseModel):
    request_number: int
    duration_ms: int
    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    finish_reason: str | None = None


class ToolCallRecord(BaseModel):
    name: str
    outcome: str
    duration_ms: int
    output_bytes: int


class RunMetrics(BaseModel):
    """What a run cost and how it ended. Joined to the manifest id in every report."""

    run_id: str
    agent: str
    manifest_id: str
    outcome: Outcome = "success"
    outcome_detail: str | None = None
    started_at: str
    duration_ms: int = 0
    model_requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    tool_calls: int = 0
    tool_calls_by_name: dict[str, int] = Field(default_factory=dict)
    tool_errors: int = 0
    estimated_cost_usd: float = 0.0
    budget_violations: list[str] = Field(default_factory=list)
    nudged: bool = False
    attempt: int = 1

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.thinking_tokens


class RunLedger:
    """Mutable counters for one run plus the budget checks the callbacks apply."""

    def __init__(
        self,
        *,
        run_id: str,
        agent: str,
        manifest_id: str,
        budgets: Budgets,
        price_per_million: tuple[float, float] = (0.0, 0.0),
        trace_path: Path | None = None,
    ) -> None:
        self.budgets = budgets
        self.price_per_million = price_per_million
        self.metrics = RunMetrics(
            run_id=run_id,
            agent=agent,
            manifest_id=manifest_id,
            started_at=datetime.now(UTC).isoformat(timespec="seconds"),
        )
        self.model_calls: list[ModelCallRecord] = []
        self.tool_call_records: list[ToolCallRecord] = []
        self._run_started = time.perf_counter()
        self._model_started: float | None = None
        self._trace_path = trace_path
        self._lock = threading.Lock()
        self.grace_used = False
        self.nudged = False

    # -- model calls ---------------------------------------------------------------------

    def model_request_allowed(self) -> str | None:
        """None when another model request fits the budget, else the reason it does not."""
        m, b = self.metrics, self.budgets
        if m.model_requests >= b.max_requests:
            return f"max_requests={b.max_requests} reached"
        if m.input_tokens >= b.max_input_tokens:
            return f"max_input_tokens={b.max_input_tokens} reached"
        if m.output_tokens + m.thinking_tokens >= b.max_output_tokens:
            return f"max_output_tokens={b.max_output_tokens} reached"
        return None

    def model_request_started(self) -> None:
        self._model_started = time.perf_counter()
        self.metrics.model_requests += 1

    def model_request_finished(
        self,
        *,
        input_tokens: int,
        output_tokens: int,
        thinking_tokens: int,
        finish_reason: str | None,
    ) -> None:
        duration_ms = (
            int((time.perf_counter() - self._model_started) * 1000)
            if self._model_started is not None
            else 0
        )
        self._model_started = None
        m = self.metrics
        m.input_tokens += input_tokens
        m.output_tokens += output_tokens
        m.thinking_tokens += thinking_tokens
        price_in, price_out = self.price_per_million
        m.estimated_cost_usd += (
            input_tokens * price_in + (output_tokens + thinking_tokens) * price_out
        ) / 1_000_000
        record = ModelCallRecord(
            request_number=m.model_requests,
            duration_ms=duration_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            thinking_tokens=thinking_tokens,
            finish_reason=finish_reason,
        )
        self.model_calls.append(record)
        self._emit("model_call", record.model_dump())

    # -- tool calls ----------------------------------------------------------------------

    def tool_call_allowed(self) -> str | None:
        if self.metrics.tool_calls >= self.budgets.max_tool_calls:
            return f"max_tool_calls={self.budgets.max_tool_calls} reached"
        return None

    @property
    def tool_calls_remaining(self) -> int:
        return max(0, self.budgets.max_tool_calls - self.metrics.tool_calls)

    def tool_call(self, *, name: str, outcome: str, duration_ms: int, output_bytes: int) -> None:
        m = self.metrics
        m.tool_calls += 1
        m.tool_calls_by_name[name] = m.tool_calls_by_name.get(name, 0) + 1
        if outcome != "success":
            m.tool_errors += 1
        record = ToolCallRecord(
            name=name, outcome=outcome, duration_ms=duration_ms, output_bytes=output_bytes
        )
        self.tool_call_records.append(record)
        self._emit("tool_call", record.model_dump())

    # -- outcome -------------------------------------------------------------------------

    def budget_violation(self, reason: str) -> None:
        if reason not in self.metrics.budget_violations:
            self.metrics.budget_violations.append(reason)

    def finish(self, outcome: Outcome | None = None, detail: str | None = None) -> RunMetrics:
        m = self.metrics
        m.nudged = self.nudged
        m.duration_ms = int((time.perf_counter() - self._run_started) * 1000)
        if outcome is not None:
            m.outcome = outcome
        if detail is not None:
            m.outcome_detail = detail
        if m.estimated_cost_usd > self.budgets.max_cost_usd > 0:
            self.budget_violation(f"max_cost_usd={self.budgets.max_cost_usd} exceeded")
        self._emit("run_finished", m.model_dump())
        return m

    def _emit(self, event: str, payload: Mapping[str, Any]) -> None:
        if self._trace_path is None:
            return
        line = {
            "time": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "event": event,
            "run_id": self.metrics.run_id,
            "agent": self.metrics.agent,
            "manifest_id": self.metrics.manifest_id,
            **payload,
        }
        with self._lock:
            self._trace_path.parent.mkdir(parents=True, exist_ok=True)
            with self._trace_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(line, default=str) + "\n")


# -- registry ------------------------------------------------------------------------------

_LEDGERS: dict[str, RunLedger] = {}
_REGISTRY_LOCK = threading.Lock()


def register_ledger(ledger: RunLedger) -> None:
    with _REGISTRY_LOCK:
        _LEDGERS[ledger.metrics.run_id] = ledger


def release_ledger(run_id: str) -> None:
    with _REGISTRY_LOCK:
        _LEDGERS.pop(run_id, None)


class SupportsGet(Protocol):
    def get(self, key: str, default: Any = None, /) -> Any: ...


def ledger_for_state(state: SupportsGet) -> RunLedger | None:
    run_id = state.get(RUN_ID_STATE_KEY)
    if not isinstance(run_id, str):
        return None
    with _REGISTRY_LOCK:
        return _LEDGERS.get(run_id)
