"""Factories: manifests, allowlists and effect checks."""

from __future__ import annotations

from pathlib import Path

import pytest
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.base_toolset import BaseToolset

from risk_review.agents.finding_verifier.factory import build_finding_verifier
from risk_review.agents.lane_reviewer.factory import AGENT_DIR, build_lane_reviewer
from risk_review.agents.lane_reviewer.types import ReviewOutput
from risk_review.runtime.assembly import assemble
from risk_review.runtime.spec import SpecError
from risk_review.tools.common.policy import ToolPolicy
from risk_review.tools.repo.toolset import RepoReadToolset
from tests.risk_review.conftest import BACKEND_DIR
from tests.risk_review.scripted_llm import ScriptedLlm, text


def test_lane_reviewer_builds_with_deterministic_manifest(repository_root: Path) -> None:
    model = ScriptedLlm.with_script([text("done")])
    first = build_lane_reviewer(
        lane="logging-and-redaction", repository_root=repository_root, max_findings=8, model=model
    )
    second = build_lane_reviewer(
        lane="logging-and-redaction", repository_root=repository_root, max_findings=8, model=model
    )
    assert first.manifest.manifest_id == second.manifest.manifest_id
    assert first.manifest.tools == ["list_files", "read_file", "report_findings", "search_text"]
    active = [s.name for s in first.manifest.skills if s.active]
    assert active == ["evidence-standards", "logging-and-redaction"]
    assert "## Skill: logging-and-redaction" in first.instruction
    assert "## Skill: export-rendering" not in first.instruction
    assert first.agent.name == "lane_reviewer"


def test_different_lane_changes_manifest(repository_root: Path) -> None:
    model = ScriptedLlm.with_script([text("done")])
    a = build_lane_reviewer(
        lane="export-rendering", repository_root=repository_root, max_findings=8, model=model
    )
    b = build_lane_reviewer(
        lane="frontend-trust", repository_root=repository_root, max_findings=8, model=model
    )
    assert a.manifest.manifest_id != b.manifest.manifest_id
    assert a.manifest.instruction_hash != b.manifest.instruction_hash


def test_verifier_builds(repository_root: Path) -> None:
    built = build_finding_verifier(
        repository_root=repository_root,
        backend_dir=BACKEND_DIR,
        model=ScriptedLlm.with_script([text("done")]),
    )
    assert built.manifest.toolsets == ["backend-tests", "record-verdict", "repo-read"]
    assert built.budgets.max_tool_calls == 14


def test_unknown_lane_is_refused(repository_root: Path) -> None:
    with pytest.raises(SpecError, match="unknown lane"):
        build_lane_reviewer(lane="nope", repository_root=repository_root, max_findings=8)


class _WriteToolset(BaseToolset):
    toolset_id = "repo-read"

    @property
    def policies(self) -> dict[str, ToolPolicy]:
        return {
            "delete_file": ToolPolicy(
                name="delete_file",
                owner="x",
                effect="write_reversible",
                retry_safety="unsafe",
                timeout_seconds=1,
                data_classification="internal",
                max_output_bytes=10,
            )
        }

    async def get_tools(self, readonly_context: ReadonlyContext | None = None) -> list[BaseTool]:
        return []


def test_write_tool_is_refused_under_ephemeral_class(repository_root: Path) -> None:
    with pytest.raises(SpecError, match="not permitted"):
        assemble(
            agent_dir=AGENT_DIR,
            repository_root=repository_root,
            active_skills=["evidence-standards"],
            toolsets=[_WriteToolset()],
            output_model=ReviewOutput,
            model=ScriptedLlm.with_script([text("done")]),
        )


def test_missing_enabled_toolset_is_refused(repository_root: Path) -> None:
    with pytest.raises(SpecError, match="not supplied"):
        assemble(
            agent_dir=AGENT_DIR,
            repository_root=repository_root,
            active_skills=["evidence-standards"],
            toolsets=[RepoReadToolset(repository_root)],
            output_model=ReviewOutput,
            model=ScriptedLlm.with_script([text("done")]),
        )


def test_inactive_skill_must_still_be_enabled(repository_root: Path) -> None:
    with pytest.raises(SpecError, match="not enabled"):
        assemble(
            agent_dir=AGENT_DIR,
            repository_root=repository_root,
            active_skills=["disprove-finding"],
            toolsets=[],
            output_model=ReviewOutput,
            model=ScriptedLlm.with_script([text("done")]),
        )
