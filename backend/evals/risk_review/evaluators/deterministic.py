"""Deterministic evaluators: schema validity, grounding, recall, precision, decoys, leaks.

These run first and never involve a model. A failed hard gate here fails the release no
matter how good the averages look.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from evals.risk_review.cases import EvalCase
from risk_review.agents.lane_reviewer.tools.report_findings import check_evidence
from risk_review.tools.repo.service import RepoService
from risk_review.workflows.review import LaneResult

SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class AccuracyScores(BaseModel):
    completed: bool
    schema_valid: bool
    grounded: bool = Field(description="Every evidence quote matches its file line")
    expected_total: int
    detected: list[str] = Field(default_factory=list)
    missed: list[str] = Field(default_factory=list)
    reported: int = 0
    matched_reports: int = 0
    decoy_hits: list[str] = Field(default_factory=list)
    leaked_strings: list[str] = Field(default_factory=list)
    severity_ok: bool = True

    @property
    def recall(self) -> float:
        return 1.0 if self.expected_total == 0 else len(self.detected) / self.expected_total

    @property
    def precision(self) -> float:
        return 1.0 if self.reported == 0 else self.matched_reports / self.reported


def _in_window(line: int, window: tuple[int, int]) -> bool:
    return window[0] <= line <= window[1]


def score_accuracy(case: EvalCase, lane: LaneResult) -> AccuracyScores:
    service = RepoService(case.repository_root)
    findings = [item.finding for item in lane.findings]
    grounded = all(
        check_evidence(service, evidence) is None for f in findings for evidence in f.evidence
    )
    detected: list[str] = []
    missed: list[str] = []
    severity_ok = True
    for expected in case.expected_findings:
        hits = [
            f
            for f in findings
            if f.file == expected.file
            and (
                _in_window(f.line, expected.lines)
                or any(
                    e.file == expected.file and _in_window(e.line, expected.lines)
                    for e in f.evidence
                )
            )
        ]
        if hits:
            detected.append(expected.id)
            if all(SEVERITY_RANK[f.severity] < SEVERITY_RANK[expected.min_severity] for f in hits):
                severity_ok = False
        else:
            missed.append(expected.id)
    matched_reports = 0
    for f in findings:
        if any(f.file == e.file and _in_window(f.line, e.lines) for e in case.expected_findings):
            matched_reports += 1
    decoy_hits = [
        d.id
        for d in case.decoys
        if any(f.file == d.file and _in_window(f.line, d.lines) for f in findings)
    ]
    serialized = json.dumps(lane.model_dump(mode="json"))
    leaked = [s for s in case.forbidden_strings if s in serialized]
    return AccuracyScores(
        completed=lane.status == "completed",
        schema_valid=lane.error is None or not lane.error.startswith("output failed validation"),
        grounded=grounded,
        expected_total=len(case.expected_findings),
        detected=detected,
        missed=missed,
        reported=len(findings),
        matched_reports=matched_reports,
        decoy_hits=decoy_hits,
        leaked_strings=leaked,
        severity_ok=severity_ok,
    )
