"""Private tool of the lane reviewer: the only way it can deliver findings.

The tool validates every finding into the typed contract **and** checks each evidence
quote against the actual file line, so a hallucinated citation never reaches the report.
The accepted output is stored in session state under ``OUTPUT_KEY`` for the step to read.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.base_toolset import BaseToolset
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from risk_review.agents.lane_reviewer.types import Evidence, Finding, ReviewOutput, ReviewStatus
from risk_review.runtime.schema import to_genai_schema
from risk_review.tools.common.policy import ToolPolicy
from risk_review.tools.repo.service import RepoService

TOOLSET_ID = "report-findings"
TOOL_NAME = "report_findings"
OUTPUT_KEY = "review_output"
LANE_KEY = "review_lane"

POLICIES: dict[str, ToolPolicy] = {
    TOOL_NAME: ToolPolicy(
        name=TOOL_NAME,
        owner="platform",
        effect="read",
        retry_safety="safe",
        timeout_seconds=5,
        data_classification="internal",
        max_output_bytes=8 * 1024,
    )
}


class ReportFindingsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ReviewStatus = Field(description="completed, needs_information or budget_exhausted")
    findings: list[Finding] = Field(default_factory=list)
    files_examined: list[str] = Field(default_factory=list, description="Paths you read")
    notes: str | None = Field(default=None, description="Anything the reader must know")


_WS = re.compile(r"\s+")


def _normalise(text: str) -> str:
    return _WS.sub(" ", text).strip()


def check_evidence(service: RepoService, evidence: Evidence) -> str | None:
    """None when the quote matches the cited line (whitespace-insensitive, either may be a
    substring of the other), else the reason."""
    resolved = service.resolve(evidence.file)
    if isinstance(resolved, BaseModel):
        return f"{evidence.file}: {resolved.message}"
    if not resolved.is_file():
        return f"{evidence.file}: file not found"
    try:
        lines = resolved.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return f"{evidence.file}: not a text file"
    if evidence.line > len(lines):
        return f"{evidence.file}:{evidence.line}: file has {len(lines)} lines"
    actual, quoted = _normalise(lines[evidence.line - 1]), _normalise(evidence.quote)
    if not quoted or (quoted not in actual and actual not in quoted):
        window = range(max(1, evidence.line - 5), min(len(lines), evidence.line + 5) + 1)
        nearby = [n for n in window if quoted and quoted in _normalise(lines[n - 1])]
        hint = f"; the quote appears at line {nearby[0]}" if nearby else ""
        return f"{evidence.file}:{evidence.line}: quote does not match the line{hint}"
    return None


def _validation_errors(error: ValidationError) -> list[dict[str, str]]:
    return [
        {"loc": ".".join(str(p) for p in e["loc"]), "msg": e["msg"]} for e in error.errors()[:12]
    ]


class ReportFindingsTool(BaseTool):
    def __init__(self, service: RepoService, *, max_findings: int) -> None:
        super().__init__(
            name=TOOL_NAME,
            description=(
                "Deliver the review result: status, findings (each with file, line, invariant, "
                "failure scenario, evidence lines and a proposed test), files examined and notes. "
                "Call it once when the review is complete. Findings whose evidence quotes do not "
                "match the file are rejected with the reason; fix them and call again."
            ),
        )
        self._service = service
        self._max_findings = max_findings

    def _get_declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=to_genai_schema(ReportFindingsArgs.model_json_schema()),
        )

    async def run_async(self, *, args: dict[str, Any], tool_context: ToolContext) -> dict[str, Any]:
        try:
            parsed = ReportFindingsArgs.model_validate(args)
        except ValidationError as error:
            return {
                "ok": False,
                "kind": "invalid_input",
                "message": "Arguments did not validate; fix the listed fields and call again.",
                "errors": _validation_errors(error),
            }
        rejected: list[dict[str, Any]] = []
        accepted: list[Finding] = []
        for index, finding in enumerate(parsed.findings):
            problems = [
                p for p in (check_evidence(self._service, ev) for ev in finding.evidence) if p
            ]
            if problems:
                rejected.append({"index": index, "title": finding.title, "problems": problems})
            elif len(accepted) < self._max_findings:
                accepted.append(finding)
            else:
                rejected.append(
                    {"index": index, "title": finding.title, "problems": ["max findings reached"]}
                )
        lane = str(tool_context.state.get(LANE_KEY) or "unknown")
        output = ReviewOutput(
            status=parsed.status,
            lane=lane,
            findings=accepted,
            files_examined=sorted(set(parsed.files_examined))[:200],
            notes=parsed.notes,
        )
        tool_context.state[OUTPUT_KEY] = output.model_dump()
        return {
            "ok": True,
            "accepted": len(accepted),
            "rejected": rejected,
            "message": (
                "Recorded. If anything was rejected, correct it and call again with ALL findings; "
                "the last call replaces the previous one."
                if rejected
                else "Recorded. You are done; reply with one sentence."
            ),
        }


class ReportFindingsToolset(BaseToolset):
    def __init__(self, repository_root: Path, *, max_findings: int) -> None:
        super().__init__()
        self.toolset_id = TOOLSET_ID
        self._tool = ReportFindingsTool(RepoService(repository_root), max_findings=max_findings)

    @property
    def policies(self) -> dict[str, ToolPolicy]:
        return POLICIES

    async def get_tools(self, readonly_context: ReadonlyContext | None = None) -> list[BaseTool]:
        return [self._tool]

    async def close(self) -> None:
        return None
