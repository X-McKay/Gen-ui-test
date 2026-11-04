"""The review workflow: deterministic orchestration of lane reviews and verifications.

Lanes run in parallel under a semaphore; every accepted finding is then verified by the
finding verifier. The workflow does no I/O itself: building agents and running them are
steps, and writing the report is the caller's job.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from google.adk.models.base_llm import BaseLlm
from pydantic import BaseModel, Field

from risk_review.agents.finding_verifier.factory import build_finding_verifier
from risk_review.agents.finding_verifier.tools.record_verdict import FINDING_ID_KEY
from risk_review.agents.finding_verifier.tools.record_verdict import (
    OUTPUT_KEY as VERDICT_KEY,
)
from risk_review.agents.finding_verifier.types import Verdict, VerificationOutput
from risk_review.agents.lane_reviewer.factory import build_lane_reviewer
from risk_review.agents.lane_reviewer.tools.report_findings import LANE_KEY
from risk_review.agents.lane_reviewer.tools.report_findings import OUTPUT_KEY as REVIEW_KEY
from risk_review.agents.lane_reviewer.types import Finding, ReviewOutput
from risk_review.observability.trace import RunMetrics
from risk_review.runtime.assembly import BuiltAgent
from risk_review.runtime.manifest import Manifest, git_commit
from risk_review.settings import RiskReviewSettings
from risk_review.steps.agent_step import StepResult, run_agent_step


class VerifiedFinding(BaseModel):
    finding_id: str
    finding: Finding
    verdict: Verdict | None = None
    verifier_metrics: RunMetrics | None = None


class LaneResult(BaseModel):
    lane: str
    status: str
    metrics: RunMetrics
    findings: list[VerifiedFinding] = Field(default_factory=list)
    files_examined: list[str] = Field(default_factory=list)
    notes: str | None = None
    error: str | None = None


class Totals(BaseModel):
    duration_ms: int = 0
    model_requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    tool_calls: int = 0
    estimated_cost_usd: float = 0.0
    findings: int = 0
    confirmed: int = 0
    refuted: int = 0
    uncertain: int = 0
    unverified: int = 0
    budget_violations: int = 0


class ReviewReport(BaseModel):
    report_id: str
    created_at: str
    repository_root: str
    git_commit: str
    lanes_requested: list[str]
    manifests: dict[str, Manifest]
    lanes: list[LaneResult]
    totals: Totals


def _reviewer_message(lane: str, repository_root: Path) -> str:
    return (
        f"Review lane `{lane}` of the repository at the tool root ({repository_root.name}). "
        "Follow the lane skill: find the sources and sinks, trace the paths, then call "
        "report_findings once."
    )


def _verifier_message(lane: str, finding: Finding) -> str:
    evidence = "\n".join(f"- {e.file}:{e.line}: {e.quote}" for e in finding.evidence)
    return (
        f"Verify this finding from lane `{lane}`.\n\n"
        f"Title: {finding.title}\nCategory: {finding.category}\nSeverity: {finding.severity}\n"
        f"Location: {finding.file}:{finding.line}\nInvariant: {finding.invariant}\n"
        f"Failure scenario: {finding.failure_scenario}\nEvidence:\n{evidence}\n"
        f"Proposed test: {finding.proposed_test}\nReviewer confidence: {finding.confidence}\n\n"
        "Try to disprove it, then call record_verdict once."
    )


async def run_step_with_retry[T: BaseModel](
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
    """Retry transient failures (timeouts, connection errors) up to ``spec.retries`` times.
    Every tool here is read-only and retry-safe, so a repeat cannot duplicate an effect."""
    attempts = built.spec.retries + 1
    result: StepResult[T] | None = None
    for attempt in range(1, attempts + 1):
        result = await run_agent_step(
            built,
            run_id=run_id if attempt == 1 else f"{run_id}-retry{attempt - 1}",
            user_message=user_message,
            initial_state=initial_state,
            output_key=output_key,
            output_model=output_model,
            timeout_s=timeout_s,
            trace_path=trace_path,
        )
        result.metrics.attempt = attempt
        if result.metrics.outcome != "failed_transient":
            break
    assert result is not None
    return result


async def run_review(
    *,
    lanes: list[str],
    repository_root: Path,
    backend_dir: Path,
    settings: RiskReviewSettings,
    trace_path: Path | None,
    model: BaseLlm | None = None,
    verify: bool | None = None,
) -> ReviewReport:
    started = datetime.now(UTC)
    report_id = started.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    semaphore = asyncio.Semaphore(settings.concurrency)
    manifests: dict[str, Manifest] = {}
    should_verify = settings.verify if verify is None else verify

    async def review_lane(lane: str) -> LaneResult:
        built = build_lane_reviewer(
            lane=lane,
            repository_root=repository_root,
            max_findings=settings.max_findings_per_lane,
            model=model,
        )
        manifests.setdefault(built.spec.name, built.manifest)
        async with semaphore:
            result = await run_step_with_retry(
                built,
                run_id=f"{report_id}-{lane}",
                user_message=_reviewer_message(lane, repository_root),
                initial_state={LANE_KEY: lane},
                output_key=REVIEW_KEY,
                output_model=ReviewOutput,
                timeout_s=settings.step_timeout_s,
                trace_path=trace_path,
            )
        output = result.output
        findings = output.findings if output else []
        return LaneResult(
            lane=lane,
            status=output.status if output else result.metrics.outcome,
            metrics=result.metrics,
            findings=[VerifiedFinding(finding_id=f.finding_id, finding=f) for f in findings],
            files_examined=output.files_examined if output else [],
            notes=output.notes if output else None,
            error=result.error,
        )

    lane_results = await asyncio.gather(*(review_lane(lane) for lane in lanes))

    async def verify_one(lane: str, item: VerifiedFinding) -> None:
        built = build_finding_verifier(
            repository_root=repository_root, backend_dir=backend_dir, model=model
        )
        manifests.setdefault(built.spec.name, built.manifest)
        async with semaphore:
            result = await run_step_with_retry(
                built,
                run_id=f"{report_id}-verify-{item.finding_id}",
                user_message=_verifier_message(lane, item.finding),
                initial_state={FINDING_ID_KEY: item.finding_id},
                output_key=VERDICT_KEY,
                output_model=VerificationOutput,
                timeout_s=settings.step_timeout_s,
                trace_path=trace_path,
            )
        item.verifier_metrics = result.metrics
        item.verdict = result.output.verdict if result.output else None

    if should_verify:
        await asyncio.gather(
            *(verify_one(lane.lane, item) for lane in lane_results for item in lane.findings)
        )

    return ReviewReport(
        report_id=report_id,
        created_at=started.isoformat(timespec="seconds"),
        repository_root=str(repository_root),
        git_commit=git_commit(repository_root),
        lanes_requested=list(lanes),
        manifests=manifests,
        lanes=list(lane_results),
        totals=compute_totals(list(lane_results), started),
    )


def compute_totals(lanes: list[LaneResult], started: datetime) -> Totals:
    totals = Totals(duration_ms=int((datetime.now(UTC) - started).total_seconds() * 1000))
    runs: list[RunMetrics] = []
    for lane in lanes:
        runs.append(lane.metrics)
        for item in lane.findings:
            totals.findings += 1
            if item.verifier_metrics is not None:
                runs.append(item.verifier_metrics)
            if item.verdict is None:
                totals.unverified += 1
            elif item.verdict.verdict == "confirmed":
                totals.confirmed += 1
            elif item.verdict.verdict == "refuted":
                totals.refuted += 1
            else:
                totals.uncertain += 1
    for run in runs:
        totals.model_requests += run.model_requests
        totals.input_tokens += run.input_tokens
        totals.output_tokens += run.output_tokens
        totals.thinking_tokens += run.thinking_tokens
        totals.tool_calls += run.tool_calls
        totals.estimated_cost_usd += run.estimated_cost_usd
        totals.budget_violations += len(run.budget_violations)
    return totals


def report_as_dict(report: ReviewReport) -> dict[str, Any]:
    return report.model_dump(mode="json")
