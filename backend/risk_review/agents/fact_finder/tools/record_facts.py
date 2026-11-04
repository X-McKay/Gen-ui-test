"""Private tool of the fact finder: the only way it can deliver facts.

Every fact is checked three ways before it is kept: the field must exist on the intake
record, the value must fit the field (coerced and validated exactly as the product does),
and every evidence quote must match the cited line of the repository. Calls accumulate: a
later value for the same field replaces the earlier one. The accepted output is stored in
session state under ``OUTPUT_KEY`` for the step to read.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.base_toolset import BaseToolset
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.intake.question_bank import QUESTION_BANK, QuestionSpec
from app.intake.record_service import coerce_value
from app.intake.schema import UNKNOWN, new_record
from risk_review.agents.fact_finder.types import Fact, FactsOutput, FactsStatus
from risk_review.agents.lane_reviewer.tools.report_findings import (
    _validation_errors,
    check_evidence,
)
from risk_review.runtime.schema import to_genai_schema
from risk_review.tools.common.policy import ToolPolicy
from risk_review.tools.repo.service import RepoService

TOOLSET_ID = "record-facts"
TOOL_NAME = "record_facts"
OUTPUT_KEY = "facts_output"
LANE_KEY = "fact_lane"
ABSENCE_MAX_CONFIDENCE = 0.7

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


class RecordFactsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: FactsStatus = Field(description="completed, needs_information or budget_exhausted")
    facts: list[Fact] = Field(default_factory=list)
    files_examined: list[str] = Field(default_factory=list, description="Paths you read")
    notes: str | None = Field(default=None, description="Anything the reader must know")


def _describe(spec: QuestionSpec) -> str:
    if spec.control == "yes_no":
        kind = "boolean"
    elif spec.control == "choice":
        kind = "one of " + ", ".join(o.value for o in spec.options)
    elif spec.control == "multi":
        kind = "list of " + ", ".join(o.value for o in spec.options)
    else:
        kind = "short text"
    return f"- {spec.field}: {kind}"


def field_catalogue() -> str:
    """The askable fields with their types and allowed values, for the tool description."""
    return "\n".join(_describe(spec) for spec in QUESTION_BANK)


def check_value(fact: Fact) -> str | None:
    """None when the value fits the field; else the reason."""
    if fact.value == UNKNOWN or fact.value is None:
        return f"{fact.field}: never record unknown or null; leave the field out"
    probe = new_record("probe")
    try:
        probe.get_field(fact.field)
    except KeyError:
        return f"{fact.field}: not a record field"
    try:
        probe.set_field(
            fact.field,
            coerce_value(fact.field, fact.value),
            source="inferred",
            confidence=fact.confidence,
            confirmed=False,
        )
    except ValueError as error:
        return f"{fact.field}: {str(error).splitlines()[0][:160]}"
    if fact.basis == "absence" and fact.confidence > ABSENCE_MAX_CONFIDENCE:
        return f"{fact.field}: a fact from absence has confidence at most {ABSENCE_MAX_CONFIDENCE}"
    return None


class RecordFactsTool(BaseTool):
    def __init__(self, service: RepoService) -> None:
        super().__init__(
            name=TOOL_NAME,
            description=(
                "Deliver facts: status, facts (field, value, confidence, basis, one to three "
                "evidence lines), files examined and notes. Call it as soon as you have grounded "
                "facts and again at the end with the final status; facts accumulate across calls "
                "(a later value for a field replaces the earlier one). A fact is rejected, with "
                "the reason, when its value does not fit the field or a quote does not match the "
                "file; fix it and call again with only that fact.\n\nFields and allowed values:\n"
                + field_catalogue()
            ),
        )
        self._service = service

    def _get_declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=to_genai_schema(RecordFactsArgs.model_json_schema()),
        )

    async def run_async(self, *, args: dict[str, Any], tool_context: ToolContext) -> dict[str, Any]:
        try:
            parsed = RecordFactsArgs.model_validate(args)
        except ValidationError as error:
            return {
                "ok": False,
                "kind": "invalid_input",
                "message": "Arguments did not validate; fix the listed fields and call again.",
                "errors": _validation_errors(error),
            }
        previous_raw = tool_context.state.get(OUTPUT_KEY)
        previous = FactsOutput.model_validate(previous_raw) if previous_raw else None
        kept: dict[str, Fact] = {f.field: f for f in (previous.facts if previous else [])}
        rejected: list[dict[str, Any]] = []
        accepted = 0
        for index, fact in enumerate(parsed.facts):
            problems = [p for p in [check_value(fact)] if p]
            problems += [
                p for p in (check_evidence(self._service, ev) for ev in fact.evidence) if p
            ]
            if problems:
                rejected.append({"index": index, "field": fact.field, "problems": problems})
                continue
            kept[fact.field] = fact
            accepted += 1
        lane = str(tool_context.state.get(LANE_KEY) or "unknown")
        examined = set(parsed.files_examined) | set(previous.files_examined if previous else [])
        output = FactsOutput(
            status=parsed.status,
            lane=lane,
            facts=list(kept.values()),
            files_examined=sorted(examined)[:200],
            notes=parsed.notes or (previous.notes if previous else None),
        )
        tool_context.state[OUTPUT_KEY] = output.model_dump()
        return {
            "ok": True,
            "accepted": accepted,
            "total_recorded": len(kept),
            "rejected": rejected,
            "message": (
                "Recorded. Correct the rejected facts and call again with only those."
                if rejected
                else "Recorded. Continue with the lane, or reply with one sentence if you are done."
            ),
        }


class RecordFactsToolset(BaseToolset):
    def __init__(self, repository_root: Path) -> None:
        super().__init__()
        self.toolset_id = TOOLSET_ID
        self._tool = RecordFactsTool(RepoService(repository_root))

    @property
    def policies(self) -> dict[str, ToolPolicy]:
        return POLICIES

    async def get_tools(self, readonly_context: ReadonlyContext | None = None) -> list[BaseTool]:
        return [self._tool]

    async def close(self) -> None:
        return None
