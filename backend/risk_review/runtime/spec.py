"""The Agent Spec: one reviewable YAML file per agent (playbook chapter 3).

``load_spec`` validates it; anything missing fails construction. Fields nothing checks are
documentation, not controls, so every field here is read by the factory.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from risk_review.observability.trace import Budgets
from risk_review.tools.common.policy import DataClassification, ExecutionClass

GovernanceTier = Literal["low", "medium", "high", "critical"]


class ModelSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4000, ge=256)
    enable_thinking: bool = False


class SpecMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: int
    owner: str = Field(min_length=1)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    execution_class: ExecutionClass
    governance_tier: GovernanceTier
    risk_assessment: str = Field(
        min_length=1, description="Path relative to this project's root (not the reviewed tree)"
    )
    data_classification: DataClassification
    model_policy: str = Field(min_length=1)
    enabled_skills: list[str] = Field(min_length=1)
    enabled_toolsets: list[str] = Field(min_length=1)
    budgets: Budgets

    @field_validator("enabled_skills", "enabled_toolsets")
    @classmethod
    def _unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("entries must be unique")
        return value


class AgentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    description: str = Field(min_length=1)
    instructions: str = Field(description="Instruction file, relative to the agent directory")
    model_settings: ModelSettings = Field(default_factory=ModelSettings)
    retries: int = Field(default=1, ge=0, le=5)
    tool_timeout: int = Field(default=20, ge=1)
    metadata: SpecMetadata

    # Set by the loader, not by the file.
    spec_path: Path | None = Field(default=None, exclude=True)

    @property
    def agent_dir(self) -> Path:
        if self.spec_path is None:
            raise ValueError("spec was not loaded from a file")
        return self.spec_path.parent

    @property
    def instruction_path(self) -> Path:
        return self.agent_dir / self.instructions


class SpecError(ValueError):
    """Raised when an Agent Spec is missing or invalid. Construction stops here."""


def load_spec(agent_dir: Path, *, project_root: Path, contract_version: int) -> AgentSpec:
    path = agent_dir / "agent.yaml"
    if not path.is_file():
        raise SpecError(f"missing agent spec: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SpecError(f"agent spec is not a mapping: {path}")
    try:
        spec = AgentSpec.model_validate({**raw, "spec_path": path})
    except ValueError as error:
        raise SpecError(f"invalid agent spec {path}: {error}") from error
    if spec.metadata.contract_version != contract_version:
        raise SpecError(
            f"{spec.name}: contract_version {spec.metadata.contract_version} "
            f"!= supported {contract_version}"
        )
    if not spec.instruction_path.is_file():
        raise SpecError(f"{spec.name}: instruction file missing: {spec.instruction_path}")
    assessment = project_root / spec.metadata.risk_assessment
    if not assessment.is_file():
        raise SpecError(f"{spec.name}: risk assessment missing: {assessment}")
    assessed = yaml.safe_load(assessment.read_text(encoding="utf-8")) or {}
    assessed_tier = assessed.get("governance_tier") if isinstance(assessed, dict) else None
    if assessed_tier != spec.metadata.governance_tier:
        raise SpecError(
            f"{spec.name}: governance_tier {spec.metadata.governance_tier!r} does not match "
            f"the risk assessment ({assessed_tier!r})"
        )
    return spec
