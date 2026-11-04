"""Controlled assembly shared by the agent factories (playbook: factory responsibilities).

``assemble`` loads the spec, validates governance metadata, resolves the model policy,
loads and allowlists skills, checks every tool's effect against the execution class,
attaches budget and telemetry callbacks, and produces the capability manifest. It raises
``SpecError`` on anything missing: an agent that refuses to build is a deploy problem; one
that builds anyway is an incident.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.models.base_llm import BaseLlm
from google.adk.tools.base_toolset import BaseToolset
from pydantic import BaseModel

from risk_review import CONTRACT_VERSION
from risk_review.observability.trace import Budgets
from risk_review.policy.budgets import after_model, before_model
from risk_review.runtime.manifest import (
    Manifest,
    SkillEntry,
    file_digest,
    git_commit,
    text_digest,
)
from risk_review.runtime.model_policy import ResolvedModel, build_model, resolve_model_policy
from risk_review.runtime.skills import LoadedSkill, load_allowlisted_skills, render_skills
from risk_review.runtime.spec import AgentSpec, SpecError, load_spec
from risk_review.settings import REPOSITORY_ROOT as PROJECT_ROOT
from risk_review.tools.common.policy import ToolPolicy
from risk_review.tools.common.telemetry import after_tool, before_tool

SHARED_SKILLS_DIR = Path(__file__).resolve().parents[1] / "skills"


class PolicyToolset(Protocol):
    """A toolset that carries a stable id and a policy per tool."""

    toolset_id: str

    @property
    def policies(self) -> dict[str, ToolPolicy]: ...


@dataclass(frozen=True)
class BuiltAgent:
    agent: LlmAgent
    spec: AgentSpec
    manifest: Manifest
    resolved_model: ResolvedModel
    active_skills: tuple[LoadedSkill, ...]
    budgets: Budgets
    instruction: str


def assemble(
    *,
    agent_dir: Path,
    repository_root: Path,  # the tree under review; the spec comes from this project
    active_skills: Sequence[str],
    toolsets: Sequence[BaseToolset],
    output_model: type[BaseModel],
    model: BaseLlm | None = None,
) -> BuiltAgent:
    spec = load_spec(agent_dir, project_root=PROJECT_ROOT, contract_version=CONTRACT_VERSION)
    metadata = spec.metadata

    # Skills: enabled set loaded and validated, active subset rendered into the instruction.
    loaded = load_allowlisted_skills(
        [agent_dir / "skills", SHARED_SKILLS_DIR], metadata.enabled_skills
    )
    unknown = [name for name in active_skills if name not in loaded]
    if unknown:
        raise SpecError(f"{spec.name}: skills {unknown} are not enabled in the spec")
    active = tuple(loaded[name] for name in active_skills)

    # Toolsets: exactly the enabled ids, every tool permitted under the execution class.
    provided: dict[str, BaseToolset] = {}
    tool_names: list[str] = []
    for toolset in toolsets:
        policy_set = _as_policy_toolset(toolset)
        if policy_set.toolset_id not in metadata.enabled_toolsets:
            raise SpecError(f"{spec.name}: toolset {policy_set.toolset_id!r} is not enabled")
        if policy_set.toolset_id in provided:
            raise SpecError(f"{spec.name}: toolset {policy_set.toolset_id!r} supplied twice")
        provided[policy_set.toolset_id] = toolset
        for name, policy in policy_set.policies.items():
            if not policy.permitted_under(metadata.execution_class):
                raise SpecError(
                    f"{spec.name}: tool {name!r} has effect {policy.effect!r}, not permitted "
                    f"under execution class {metadata.execution_class!r}"
                )
            tool_names.append(name)
    missing = [name for name in metadata.enabled_toolsets if name not in provided]
    if missing:
        raise SpecError(f"{spec.name}: enabled toolsets not supplied: {missing}")

    resolved = resolve_model_policy(metadata.model_policy, spec.model_settings)
    llm = model if model is not None else build_model(resolved)

    base_instruction = spec.instruction_path.read_text(encoding="utf-8").strip()
    instruction = base_instruction + "\n\n" + render_skills(active)

    def instruction_provider(_context: ReadonlyContext) -> str:
        # A provider bypasses ADK's ``{state_key}`` templating, so braces inside skills
        # (regular expressions, code) reach the model verbatim.
        return instruction

    agent = LlmAgent(
        name=spec.name.replace("-", "_"),
        description=spec.description.strip(),
        model=llm,
        instruction=instruction_provider,
        tools=list(toolsets),
        before_model_callback=before_model,
        after_model_callback=after_model,
        before_tool_callback=before_tool,
        after_tool_callback=after_tool,
    )

    manifest = Manifest(
        agent_name=spec.name,
        agent_version=metadata.version,
        contract_version=metadata.contract_version,
        execution_class=metadata.execution_class,
        governance_tier=metadata.governance_tier,
        risk_assessment_digest=file_digest(PROJECT_ROOT / metadata.risk_assessment),
        model_policy=resolved.policy,
        provider=resolved.provider,
        model_id=resolved.model_id,
        model_settings={
            "temperature": resolved.temperature,
            "max_tokens": resolved.max_tokens,
            "enable_thinking": resolved.enable_thinking,
        },
        pricing_version=resolved.pricing_version,
        instruction_hash=text_digest(instruction),
        skills=[
            SkillEntry(
                name=skill.name,
                version=skill.version,
                content_hash=skill.content_hash,
                active=skill.name in active_skills,
            )
            for skill in loaded.values()
        ],
        toolsets=sorted(provided),
        tools=sorted(tool_names),
        output_schema_hash=text_digest(str(output_model.model_json_schema())),
        budgets=metadata.budgets.model_dump(),
        git_commit=git_commit(repository_root),
    ).finalize()

    return BuiltAgent(
        agent=agent,
        spec=spec,
        manifest=manifest,
        resolved_model=resolved,
        active_skills=active,
        budgets=metadata.budgets,
        instruction=instruction,
    )


def _as_policy_toolset(toolset: BaseToolset) -> PolicyToolset:
    toolset_id = getattr(toolset, "toolset_id", None)
    policies = getattr(toolset, "policies", None)
    if not isinstance(toolset_id, str) or not isinstance(policies, dict):
        raise SpecError(f"toolset {type(toolset).__name__} has no toolset_id/policies")
    return cast(PolicyToolset, toolset)
