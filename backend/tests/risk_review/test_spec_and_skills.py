"""Agent specs, skills and the factory refusing incomplete configuration."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from risk_review import CONTRACT_VERSION
from risk_review.agents.finding_verifier.factory import AGENT_DIR as VERIFIER_DIR
from risk_review.agents.lane_reviewer.factory import AGENT_DIR as REVIEWER_DIR
from risk_review.agents.lane_reviewer.factory import available_lanes
from risk_review.runtime.assembly import SHARED_SKILLS_DIR
from risk_review.runtime.skills import load_allowlisted_skills, load_skill
from risk_review.runtime.spec import SpecError, load_spec

PATH_PATTERN = re.compile(r"`((?:backend|frontend|docs|schema)/[A-Za-z0-9_./-]+)`")


def test_both_specs_load(repository_root: Path) -> None:
    for agent_dir in (REVIEWER_DIR, VERIFIER_DIR):
        spec = load_spec(agent_dir, project_root=repository_root, contract_version=CONTRACT_VERSION)
        assert spec.metadata.owner == "platform"
        assert spec.metadata.execution_class == "ephemeral"


def test_lane_skills_match_available_lanes() -> None:
    lanes = available_lanes()
    assert len(lanes) == 6
    spec = yaml.safe_load((REVIEWER_DIR / "agent.yaml").read_text())
    assert set(lanes) <= set(spec["metadata"]["enabled_skills"])


def test_every_skill_has_required_sections_and_metadata() -> None:
    skill_dirs = [
        *(REVIEWER_DIR / "skills").iterdir(),
        *(VERIFIER_DIR / "skills").iterdir(),
        *SHARED_SKILLS_DIR.iterdir(),
    ]
    for skill_dir in skill_dirs:
        skill = load_skill(skill_dir)
        for heading in (
            "## Use this skill when",
            "## Do not use this skill when",
            "## Procedure",
            "## Safety constraints",
            "## Completion criteria",
        ):
            assert heading in skill.body, f"{skill.name} lacks {heading!r}"
        assert re.fullmatch(r"\d+\.\d+\.\d+", skill.version), skill.name
        assert len(skill.content_hash) == 16


def test_lane_skill_paths_exist_in_repository(repository_root: Path) -> None:
    """A lane skill that names a path the repository no longer has sends the reviewer
    searching; keep the skills current."""
    missing: list[str] = []
    for skill_dir in (REVIEWER_DIR / "skills").iterdir():
        body = (skill_dir / "SKILL.md").read_text()
        for path in PATH_PATTERN.findall(body):
            if not (repository_root / path).exists():
                missing.append(f"{skill_dir.name}: {path}")
    assert missing == []


def test_allowlist_refuses_unknown_skill() -> None:
    with pytest.raises(SpecError, match="not found"):
        load_allowlisted_skills([REVIEWER_DIR / "skills"], ["does-not-exist"])


def _write_spec(tmp_path: Path, repository_root: Path, **overrides: object) -> Path:
    raw = yaml.safe_load((REVIEWER_DIR / "agent.yaml").read_text())
    for dotted, value in overrides.items():
        target = raw
        *parents, leaf = dotted.split(".")
        for key in parents:
            target = target[key]
        if value is None:
            target.pop(leaf, None)
        else:
            target[leaf] = value
    agent_dir = tmp_path / "agent"
    (agent_dir / "instructions").mkdir(parents=True)
    (agent_dir / "instructions" / "system.md").write_text("You review.")
    (agent_dir / "agent.yaml").write_text(yaml.safe_dump(raw))
    return agent_dir


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"metadata.owner": None}, "owner"),
        ({"metadata.budgets": None}, "budgets"),
        ({"metadata.governance_tier": "high"}, "governance_tier"),
        ({"metadata.model_policy": "nope"}, "model_policy|unknown"),
        ({"metadata.risk_assessment": "docs/missing.yaml"}, "risk assessment missing"),
        ({"metadata.contract_version": 99}, "contract_version"),
        ({"metadata.enabled_toolsets": ["repo-read", "repo-read"]}, "unique"),
    ],
)
def test_construction_fails_on_missing_or_invalid_governance(
    tmp_path: Path, repository_root: Path, override: dict[str, object], message: str
) -> None:
    agent_dir = _write_spec(tmp_path, repository_root, **override)
    with pytest.raises(SpecError, match=message):
        spec = load_spec(agent_dir, project_root=repository_root, contract_version=CONTRACT_VERSION)
        # model policy is resolved by assembly, not the loader
        from risk_review.runtime.model_policy import resolve_model_policy

        resolve_model_policy(spec.metadata.model_policy, spec.model_settings)
