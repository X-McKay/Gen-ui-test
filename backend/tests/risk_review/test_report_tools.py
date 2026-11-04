"""report_findings / record_verdict: typed validation and evidence grounding (RR-03)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from risk_review.agents.finding_verifier.tools.record_verdict import (
    FINDING_ID_KEY,
    RecordVerdictTool,
)
from risk_review.agents.finding_verifier.tools.record_verdict import (
    OUTPUT_KEY as VERDICT_KEY,
)
from risk_review.agents.lane_reviewer.tools.report_findings import (
    LANE_KEY,
    OUTPUT_KEY,
    ReportFindingsTool,
    check_evidence,
)
from risk_review.agents.lane_reviewer.types import Evidence
from risk_review.tools.repo.service import RepoService


def _finding(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "title": "Description reaches an INFO log line",
        "category": "content-logged",
        "severity": "high",
        "file": "backend/app/api.py",
        "line": 5,
        "invariant": "Never log the project description at any level.",
        "failure_scenario": "A description containing a token is written to the INFO log.",
        "evidence": [
            {
                "file": "backend/app/api.py",
                "line": 5,
                "quote": 'logger.info("intake.create description=%s", description)',
            }
        ],
        "proposed_test": "Call create('x') with caplog and assert 'x' is not in the records.",
        "confidence": 0.9,
    }
    base.update(overrides)
    return base


def _context(**state: Any) -> Any:
    return SimpleNamespace(state=dict(state))


def test_check_evidence_matches_whitespace_insensitively(tiny_repo: Path) -> None:
    service = RepoService(tiny_repo)
    ok = Evidence(file="backend/app/api.py", line=5, quote="logger.info(  'intake.create'")
    assert (
        check_evidence(service, Evidence(file="backend/app/api.py", line=5, quote="logger.info("))
        is None
    )
    assert check_evidence(service, ok) is not None  # different quoting is a different line
    wrong = check_evidence(
        service, Evidence(file="backend/app/api.py", line=2, quote="logger.info(")
    )
    assert wrong is not None and "appears at line 5" in wrong
    assert (
        check_evidence(service, Evidence(file="backend/app/api.py", line=99, quote="x")) is not None
    )
    assert check_evidence(service, Evidence(file="missing.py", line=1, quote="x")) is not None
    secret = check_evidence(service, Evidence(file=".env", line=1, quote="OPENAI"))
    assert secret is not None and "secrets policy" in secret


async def test_report_findings_accepts_grounded_and_rejects_hallucinated(tiny_repo: Path) -> None:
    tool = ReportFindingsTool(RepoService(tiny_repo), max_findings=8)
    context = _context(**{LANE_KEY: "logging-and-redaction"})
    result = await tool.run_async(
        args={
            "status": "completed",
            "findings": [
                _finding(),
                _finding(
                    title="Hallucinated citation that must be rejected",
                    evidence=[{"file": "backend/app/api.py", "line": 5, "quote": "os.system(cmd)"}],
                ),
            ],
            "files_examined": ["backend/app/api.py", "backend/app/api.py"],
        },
        tool_context=context,
    )
    assert result["ok"] is True and result["accepted"] == 1
    assert result["rejected"][0]["index"] == 1
    stored = context.state[OUTPUT_KEY]
    assert stored["lane"] == "logging-and-redaction"
    assert len(stored["findings"]) == 1 and stored["files_examined"] == ["backend/app/api.py"]


async def test_report_findings_rejects_invalid_schema(tiny_repo: Path) -> None:
    tool = ReportFindingsTool(RepoService(tiny_repo), max_findings=8)
    context = _context()
    result = await tool.run_async(
        args={"status": "completed", "findings": [{"title": "too short"}]}, tool_context=context
    )
    assert result["ok"] is False and result["kind"] == "invalid_input"
    assert OUTPUT_KEY not in context.state


async def test_report_findings_enforces_the_cap(tiny_repo: Path) -> None:
    tool = ReportFindingsTool(RepoService(tiny_repo), max_findings=1)
    context = _context()
    result = await tool.run_async(
        args={
            "status": "completed",
            "findings": [_finding(), _finding(title="Second finding here")],
        },
        tool_context=context,
    )
    assert result["accepted"] == 1 and result["rejected"][0]["problems"] == ["max findings reached"]


async def test_record_verdict_requires_grounded_evidence(tiny_repo: Path) -> None:
    tool = RecordVerdictTool(RepoService(tiny_repo))
    context = _context(**{FINDING_ID_KEY: "abc123"})
    bad = await tool.run_async(
        args={
            "verdict": "refuted",
            "reasoning": "A guard upstream prevents the scenario from being reachable.",
            "evidence": [{"file": "backend/app/api.py", "line": 1, "quote": "nothing like this"}],
            "confidence": 0.8,
        },
        tool_context=context,
    )
    assert bad["ok"] is False and VERDICT_KEY not in context.state
    good = await tool.run_async(
        args={
            "verdict": "confirmed",
            "reasoning": "The description is interpolated into the INFO log with no redaction.",
            "evidence": [{"file": "backend/app/api.py", "line": 5, "quote": "logger.info("}],
            "existing_test_covers_it": False,
            "confidence": 0.9,
        },
        tool_context=context,
    )
    assert good["ok"] is True
    assert context.state[VERDICT_KEY]["verdict"]["finding_id"] == "abc123"
