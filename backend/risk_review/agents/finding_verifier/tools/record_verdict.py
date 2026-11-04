"""Private tool of the finding verifier: records one verdict, with evidence checked."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.base_toolset import BaseToolset
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from pydantic import ValidationError

from risk_review.agents.finding_verifier.types import Verdict, VerificationOutput
from risk_review.agents.lane_reviewer.tools.report_findings import check_evidence
from risk_review.runtime.schema import to_genai_schema
from risk_review.tools.common.policy import ToolPolicy
from risk_review.tools.repo.service import RepoService

TOOLSET_ID = "record-verdict"
TOOL_NAME = "record_verdict"
OUTPUT_KEY = "verification_output"
FINDING_ID_KEY = "finding_id"

POLICIES: dict[str, ToolPolicy] = {
    TOOL_NAME: ToolPolicy(
        name=TOOL_NAME,
        owner="platform",
        effect="read",
        retry_safety="safe",
        timeout_seconds=5,
        data_classification="internal",
        max_output_bytes=4 * 1024,
    )
}


class RecordVerdictTool(BaseTool):
    def __init__(self, service: RepoService) -> None:
        super().__init__(
            name=TOOL_NAME,
            description=(
                "Record the verdict on the finding: confirmed, refuted or uncertain, with the "
                "reasoning, the evidence lines you relied on, whether an existing test covers the "
                "scenario, and your confidence. Call it once."
            ),
        )
        self._service = service

    def _get_declaration(self) -> types.FunctionDeclaration:
        schema = Verdict.model_json_schema()
        schema["properties"].pop("finding_id", None)
        schema["required"] = [r for r in schema.get("required", []) if r != "finding_id"]
        return types.FunctionDeclaration(
            name=self.name, description=self.description, parameters=to_genai_schema(schema)
        )

    async def run_async(self, *, args: dict[str, Any], tool_context: ToolContext) -> dict[str, Any]:
        finding_id = str(tool_context.state.get(FINDING_ID_KEY) or "unknown")
        try:
            verdict = Verdict.model_validate({**args, "finding_id": finding_id})
        except ValidationError as error:
            return {
                "ok": False,
                "kind": "invalid_input",
                "message": "Arguments did not validate; fix the listed fields and call again.",
                "errors": [
                    {"loc": ".".join(str(p) for p in e["loc"]), "msg": e["msg"]}
                    for e in error.errors()[:12]
                ],
            }
        problems = [p for p in (check_evidence(self._service, ev) for ev in verdict.evidence) if p]
        if problems:
            return {
                "ok": False,
                "kind": "invalid_input",
                "message": "Evidence does not match the files; fix it and call again.",
                "problems": problems,
            }
        tool_context.state[OUTPUT_KEY] = VerificationOutput(
            status="completed", verdict=verdict
        ).model_dump()
        return {"ok": True, "message": "Recorded. You are done; reply with one sentence."}


class RecordVerdictToolset(BaseToolset):
    def __init__(self, repository_root: Path) -> None:
        super().__init__()
        self.toolset_id = TOOLSET_ID
        self._tool = RecordVerdictTool(RepoService(repository_root))

    @property
    def policies(self) -> dict[str, ToolPolicy]:
        return POLICIES

    async def get_tools(self, readonly_context: ReadonlyContext | None = None) -> list[BaseTool]:
        return [self._tool]

    async def close(self) -> None:
        return None
