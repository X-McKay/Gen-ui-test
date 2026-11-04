"""Builds the fact finder: spec + instruction + (fact standards, one fact lane) + tools."""

from __future__ import annotations

from pathlib import Path

from google.adk.models.base_llm import BaseLlm

from risk_review.agents.fact_finder.tools.record_facts import RecordFactsToolset
from risk_review.agents.fact_finder.types import FactsOutput
from risk_review.runtime.assembly import BuiltAgent, assemble
from risk_review.runtime.spec import SpecError
from risk_review.tools.repo.toolset import RepoReadToolset

AGENT_DIR = Path(__file__).resolve().parent
STANDARDS_SKILL = "fact-standards"


def available_fact_lanes() -> list[str]:
    """Fact lane names: every private skill directory except the standards skill."""
    return sorted(
        p.name
        for p in (AGENT_DIR / "skills").iterdir()
        if (p / "SKILL.md").is_file() and p.name != STANDARDS_SKILL
    )


def build_fact_finder(
    *, lane: str, repository_root: Path, model: BaseLlm | None = None
) -> BuiltAgent:
    if lane not in available_fact_lanes():
        raise SpecError(f"unknown fact lane {lane!r}; available: {available_fact_lanes()}")
    return assemble(
        agent_dir=AGENT_DIR,
        repository_root=repository_root,
        active_skills=[STANDARDS_SKILL, lane],
        toolsets=[RepoReadToolset(repository_root), RecordFactsToolset(repository_root)],
        output_model=FactsOutput,
        model=model,
    )
