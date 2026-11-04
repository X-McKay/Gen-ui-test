"""Trajectory evaluator: the path matters, not only the answer. Invariants, not sequences."""

from __future__ import annotations

from pydantic import BaseModel, Field

from evals.risk_review.cases import EvalCase
from risk_review.observability.trace import RunMetrics


class TrajectoryScores(BaseModel):
    only_allowed_tools: bool
    forbidden_tools_used: list[str] = Field(default_factory=list)
    required_tools_present: bool
    report_calls: int
    report_calls_ok: bool
    tool_errors: int
    tool_errors_ok: bool
    read_before_report: bool = Field(
        description="At least one read_file or search_text happened before reporting"
    )

    @property
    def passed(self) -> bool:
        return (
            self.only_allowed_tools
            and self.required_tools_present
            and self.report_calls_ok
            and self.tool_errors_ok
            and self.read_before_report
        )


def score_trajectory(case: EvalCase, metrics: RunMetrics) -> TrajectoryScores:
    used = metrics.tool_calls_by_name
    forbidden = sorted(name for name in used if name not in case.trajectory.allowed_tools)
    report_calls = used.get("report_findings", 0)
    reads = used.get("read_file", 0) + used.get("search_text", 0)
    return TrajectoryScores(
        only_allowed_tools=not forbidden,
        forbidden_tools_used=forbidden,
        required_tools_present=all(used.get(n, 0) > 0 for n in case.trajectory.required_tools),
        report_calls=report_calls,
        report_calls_ok=0 < report_calls <= case.trajectory.max_report_calls,
        tool_errors=metrics.tool_errors,
        tool_errors_ok=metrics.tool_errors <= case.trajectory.max_tool_errors,
        read_before_report=reads > 0,
    )
