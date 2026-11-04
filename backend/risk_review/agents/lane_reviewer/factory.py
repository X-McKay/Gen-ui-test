"""Builds the lane reviewer: spec + instruction + (evidence skill, one lane skill) + tools."""

from __future__ import annotations

from pathlib import Path

from google.adk.models.base_llm import BaseLlm

from risk_review.agents.lane_reviewer.tools.report_findings import ReportFindingsToolset
from risk_review.agents.lane_reviewer.types import ReviewOutput
from risk_review.runtime.assembly import BuiltAgent, assemble
from risk_review.runtime.spec import SpecError
from risk_review.tools.repo.toolset import RepoReadToolset

AGENT_DIR = Path(__file__).resolve().parent
EVIDENCE_SKILL = "evidence-standards"


def available_lanes() -> list[str]:
    """Lane names: every private skill directory of this agent."""
    return sorted(p.name for p in (AGENT_DIR / "skills").iterdir() if (p / "SKILL.md").is_file())


def build_lane_reviewer(
    *,
    lane: str,
    repository_root: Path,
    max_findings: int,
    model: BaseLlm | None = None,
) -> BuiltAgent:
    if lane not in available_lanes():
        raise SpecError(f"unknown lane {lane!r}; available: {available_lanes()}")
    return assemble(
        agent_dir=AGENT_DIR,
        repository_root=repository_root,
        active_skills=[EVIDENCE_SKILL, lane],
        toolsets=[
            RepoReadToolset(repository_root),
            ReportFindingsToolset(repository_root, max_findings=max_findings),
        ],
        output_model=ReviewOutput,
        model=model,
    )
