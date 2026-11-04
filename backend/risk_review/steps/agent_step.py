"""The durable step that runs one built agent to completion and returns typed output plus
metrics. All model and tool I/O happens here; the workflow only sequences steps."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel, ValidationError

from risk_review.observability.trace import (
    RUN_ID_STATE_KEY,
    Outcome,
    RunLedger,
    RunMetrics,
    register_ledger,
    release_ledger,
)
from risk_review.policy.delivery import DELIVERY_TOOL_STATE_KEY, DELIVERY_TOOLS
from risk_review.runtime.assembly import BuiltAgent

logger = logging.getLogger(__name__)

APP_NAME = "risk_review"
USER_ID = "risk-review"
NUDGE_TEXT = (
    "You finished without calling your delivery tool. Call it now with everything you found; "
    "if you found nothing, call it with status `completed` and no findings."
)


@dataclass(frozen=True)
class StepResult[T: BaseModel]:
    output: T | None
    metrics: RunMetrics
    error: str | None = None


def _classify_error(error: BaseException) -> tuple[Outcome, str]:
    name = type(error).__name__
    if isinstance(error, TimeoutError):
        return "timeout", name
    transient = ("Timeout", "Connection", "RateLimit", "ServiceUnavailable", "APIError")
    if any(token in name for token in transient):
        return "failed_transient", name
    return "failed_permanent", name


async def run_agent_step[T: BaseModel](
    built: BuiltAgent,
    *,
    run_id: str,
    user_message: str,
    initial_state: dict[str, Any],
    output_key: str,
    output_model: type[T],
    timeout_s: int,
    trace_path: Path | None,
) -> StepResult[T]:
    ledger = RunLedger(
        run_id=run_id,
        agent=built.spec.name,
        manifest_id=built.manifest.manifest_id,
        budgets=built.budgets,
        price_per_million=built.resolved_model.price_per_million,
        trace_path=trace_path,
    )
    register_ledger(ledger)
    runner = InMemoryRunner(agent=built.agent, app_name=APP_NAME)
    error_text: str | None = None
    raw_output: Any = None
    try:
        delivery = next((t for t in built.manifest.tools if t in DELIVERY_TOOLS), "")
        session = await runner.session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            state={RUN_ID_STATE_KEY: run_id, DELIVERY_TOOL_STATE_KEY: delivery, **initial_state},
        )

        async def consume(message: str) -> None:
            async for _event in runner.run_async(
                user_id=USER_ID,
                session_id=session.id,
                new_message=types.Content(role="user", parts=[types.Part(text=message)]),
            ):
                pass

        async def delivered() -> Any:
            final = await runner.session_service.get_session(
                app_name=APP_NAME, user_id=USER_ID, session_id=session.id
            )
            return (final.state if final is not None else {}).get(output_key)

        try:
            await asyncio.wait_for(consume(user_message), timeout=timeout_s)
            raw_output = await delivered()
            if raw_output is None and ledger.metrics.outcome == "success":
                # One follow-up turn: models sometimes write the result as prose instead.
                ledger.nudged = True
                await asyncio.wait_for(consume(NUDGE_TEXT), timeout=timeout_s)
                raw_output = await delivered()
        except Exception as error:
            outcome, detail = _classify_error(error)
            ledger.metrics.outcome = outcome
            ledger.metrics.outcome_detail = detail
            error_text = detail
            logger.warning("risk_review.step_failed", extra={"run_id": run_id, "error": detail})
            raw_output = await delivered()
    finally:
        await runner.close()
        release_ledger(run_id)

    output: T | None = None
    if raw_output is not None:
        try:
            output = output_model.model_validate(raw_output)
        except ValidationError as error:
            error_text = f"output failed validation: {error.error_count()} errors"
            ledger.metrics.outcome = "failed_permanent"
    if output is None and ledger.metrics.outcome == "success":
        ledger.metrics.outcome = "needs_information"
        ledger.metrics.outcome_detail = "agent finished without delivering output"
    metrics = ledger.finish()
    return StepResult(output=output, metrics=metrics, error=error_text)
