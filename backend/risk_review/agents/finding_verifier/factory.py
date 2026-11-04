"""Builds the finding verifier: spec + instruction + skills + repo, tests and verdict tools."""

from __future__ import annotations

from pathlib import Path

from google.adk.models.base_llm import BaseLlm

from risk_review.agents.finding_verifier.tools.record_verdict import RecordVerdictToolset
from risk_review.agents.finding_verifier.types import VerificationOutput
from risk_review.runtime.assembly import BuiltAgent, assemble
from risk_review.tools.repo.toolset import RepoReadToolset
from risk_review.tools.testing.toolset import BackendTestsToolset

AGENT_DIR = Path(__file__).resolve().parent


def build_finding_verifier(
    *, repository_root: Path, backend_dir: Path, model: BaseLlm | None = None
) -> BuiltAgent:
    return assemble(
        agent_dir=AGENT_DIR,
        repository_root=repository_root,
        active_skills=["evidence-standards", "disprove-finding"],
        toolsets=[
            RepoReadToolset(repository_root),
            BackendTestsToolset(backend_dir),
            RecordVerdictToolset(repository_root),
        ],
        output_model=VerificationOutput,
        model=model,
    )
