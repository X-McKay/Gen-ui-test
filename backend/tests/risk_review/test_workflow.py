"""Component tests: the workflow with a scripted model, no network."""

from __future__ import annotations

import json
from pathlib import Path

from risk_review.agents.finding_verifier.factory import build_finding_verifier
from risk_review.agents.finding_verifier.tools.record_verdict import FINDING_ID_KEY
from risk_review.agents.finding_verifier.tools.record_verdict import (
    OUTPUT_KEY as VERDICT_KEY,
)
from risk_review.agents.finding_verifier.types import VerificationOutput
from risk_review.observability.report import render_markdown
from risk_review.settings import RiskReviewSettings
from risk_review.steps.agent_step import run_agent_step
from risk_review.workflows.review import run_review
from tests.risk_review.conftest import BACKEND_DIR
from tests.risk_review.scripted_llm import ScriptedLlm, call, text

FINDING = {
    "title": "Description reaches an INFO log line",
    "category": "content-logged",
    "severity": "high",
    "file": "backend/app/api.py",
    "line": 5,
    "invariant": "Never log the project description at any level.",
    "failure_scenario": "A description containing a token is written to the INFO log.",
    "evidence": [{"file": "backend/app/api.py", "line": 5, "quote": "logger.info("}],
    "proposed_test": "Call create('x') with caplog and assert 'x' is not in the records.",
    "confidence": 0.9,
}


def _settings(tmp_path: Path) -> RiskReviewSettings:
    return RiskReviewSettings(
        repository_root=tmp_path, output_dir=tmp_path / "out", concurrency=2, step_timeout_s=60
    )


async def test_review_workflow_collects_findings_and_metrics(
    tiny_repo: Path, tmp_path: Path
) -> None:
    model = ScriptedLlm.with_script(
        [
            call("search_text", {"pattern": r"logger\.info", "prefix": "backend"}),
            call("read_file", {"path": "backend/app/api.py"}),
            call(
                "report_findings",
                {
                    "status": "completed",
                    "findings": [FINDING],
                    "files_examined": ["backend/app/api.py"],
                },
            ),
            text("Done."),
        ]
    )
    trace = tmp_path / "trace.jsonl"
    report = await run_review(
        lanes=["logging-and-redaction"],
        repository_root=tiny_repo,
        backend_dir=BACKEND_DIR,
        settings=_settings(tmp_path),
        trace_path=trace,
        model=model,
        verify=False,
    )
    lane = report.lanes[0]
    assert lane.status == "completed" and lane.error is None
    assert [f.finding.category for f in lane.findings] == ["content-logged"]
    assert lane.metrics.outcome == "success"
    assert lane.metrics.model_requests == 4
    assert lane.metrics.tool_calls == 3 and lane.metrics.tool_errors == 0
    assert lane.metrics.input_tokens == 400 and lane.metrics.output_tokens == 80
    assert report.totals.findings == 1 and report.totals.unverified == 1
    assert "lane-reviewer" in report.manifests
    # The trace never carries file content.
    assert "logger.info" not in trace.read_text()
    assert "SENTINELSECRET" not in json.dumps(report.model_dump(mode="json"))
    markdown = render_markdown(report)
    assert "### [high] Description reaches an INFO log line" in markdown
    assert "unverified" in markdown
    # The model saw the lane skill and the tools.
    first_request = model.requests[0]
    assert "## Skill: logging-and-redaction" in str(first_request.config.system_instruction)


async def test_agent_that_writes_prose_is_nudged_once(tiny_repo: Path, tmp_path: Path) -> None:
    model = ScriptedLlm.with_script(
        [
            text("Here is my report as prose instead of a tool call."),
            call("report_findings", {"status": "completed", "findings": [FINDING]}),
            text("Done."),
        ]
    )
    report = await run_review(
        lanes=["export-rendering"],
        repository_root=tiny_repo,
        backend_dir=BACKEND_DIR,
        settings=_settings(tmp_path),
        trace_path=None,
        model=model,
        verify=False,
    )
    lane = report.lanes[0]
    assert lane.status == "completed" and len(lane.findings) == 1
    assert lane.metrics.nudged and lane.metrics.model_requests == 3
    nudge_turn = model.requests[1]
    assert any(
        part.text and "delivery tool" in part.text
        for content in nudge_turn.contents
        for part in (content.parts or [])
    )


async def test_transient_failure_is_retried_once(tiny_repo: Path, tmp_path: Path) -> None:
    model = _FailOnce(
        ScriptedLlm.with_script(
            [call("report_findings", {"status": "completed", "findings": [FINDING]}), text("ok")]
        )
    )
    report = await run_review(
        lanes=["export-rendering"],
        repository_root=tiny_repo,
        backend_dir=BACKEND_DIR,
        settings=_settings(tmp_path),
        trace_path=None,
        model=model,
        verify=False,
    )
    lane = report.lanes[0]
    assert lane.status == "completed" and lane.metrics.attempt == 2
    assert lane.metrics.outcome == "success"


class _ConnectionTimeoutError(Exception):
    pass


class _FailOnce(ScriptedLlm):
    def __init__(self, inner: ScriptedLlm) -> None:
        super().__init__()
        self._inner = inner
        self._failed = False

    async def generate_content_async(self, llm_request, stream=False):  # type: ignore[no-untyped-def]
        if not self._failed:
            self._failed = True
            raise _ConnectionTimeoutError("simulated provider timeout")
        async for response in self._inner.generate_content_async(llm_request, stream):
            yield response


async def test_agent_that_never_reports_is_needs_information(
    tiny_repo: Path, tmp_path: Path
) -> None:
    model = ScriptedLlm.with_script([text("I looked around and have nothing to say.")])
    report = await run_review(
        lanes=["export-rendering"],
        repository_root=tiny_repo,
        backend_dir=BACKEND_DIR,
        settings=_settings(tmp_path),
        trace_path=None,
        model=model,
        verify=False,
    )
    lane = report.lanes[0]
    assert lane.status == "needs_information" and lane.findings == []
    assert lane.metrics.outcome_detail == "agent finished without delivering output"


async def test_verifier_step_records_a_verdict(tiny_repo: Path) -> None:
    model = ScriptedLlm.with_script(
        [
            call("read_file", {"path": "backend/app/api.py"}),
            call(
                "record_verdict",
                {
                    "verdict": "confirmed",
                    "reasoning": "The description is interpolated straight into the log call.",
                    "evidence": [
                        {"file": "backend/app/api.py", "line": 5, "quote": "logger.info("}
                    ],
                    "existing_test_covers_it": False,
                    "confidence": 0.85,
                },
            ),
            text("Done."),
        ]
    )
    built = build_finding_verifier(repository_root=tiny_repo, backend_dir=BACKEND_DIR, model=model)
    result = await run_agent_step(
        built,
        run_id="verify-1",
        user_message="Verify this finding.",
        initial_state={FINDING_ID_KEY: "f1"},
        output_key=VERDICT_KEY,
        output_model=VerificationOutput,
        timeout_s=60,
        trace_path=None,
    )
    assert result.output is not None and result.output.verdict is not None
    assert result.output.verdict.verdict == "confirmed"
    assert result.output.verdict.finding_id == "f1"
    assert result.metrics.tool_calls_by_name == {"read_file": 1, "record_verdict": 1}


async def test_full_workflow_with_verification(tiny_repo: Path, tmp_path: Path) -> None:
    """The same scripted model serves both agents: reviewer calls land first, then the
    verifier's. Tool names that do not exist for an agent are reported as errors by ADK and
    the script continues, so the order below is reviewer then verifier."""
    model = ScriptedLlm.with_script(
        [
            call("report_findings", {"status": "completed", "findings": [FINDING]}),
            text("Done."),
        ]
    )
    verifier_model = ScriptedLlm.with_script(
        [
            call(
                "record_verdict",
                {
                    "verdict": "refuted",
                    "reasoning": "A redaction filter strips the description before the log call.",
                    "evidence": [
                        {"file": "backend/app/api.py", "line": 5, "quote": "logger.info("}
                    ],
                    "existing_test_covers_it": True,
                    "confidence": 0.7,
                },
            ),
            text("Done."),
        ]
    )
    # run_review takes one model override; drive verification through a two-phase model.
    phased = _Phased(model, verifier_model)
    report = await run_review(
        lanes=["logging-and-redaction"],
        repository_root=tiny_repo,
        backend_dir=BACKEND_DIR,
        settings=_settings(tmp_path),
        trace_path=None,
        model=phased,
        verify=True,
    )
    item = report.lanes[0].findings[0]
    assert item.verdict is not None and item.verdict.verdict == "refuted"
    assert item.verifier_metrics is not None and item.verifier_metrics.model_requests == 2
    assert report.totals.refuted == 1 and report.totals.model_requests == 4


class _Phased(ScriptedLlm):
    """Routes requests to the reviewer or verifier script by the tools the request offers."""

    def __init__(self, reviewer: ScriptedLlm, verifier: ScriptedLlm) -> None:
        super().__init__()
        self._reviewer = reviewer
        self._verifier = verifier

    async def generate_content_async(self, llm_request, stream=False):  # type: ignore[no-untyped-def]
        tools = llm_request.tools_dict if hasattr(llm_request, "tools_dict") else {}
        target = self._verifier if "record_verdict" in tools else self._reviewer
        async for response in target.generate_content_async(llm_request, stream):
            yield response
