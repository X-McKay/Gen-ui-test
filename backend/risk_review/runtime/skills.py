"""Runtime skills: ``SKILL.md`` packages loaded through ADK's skill loader.

The agent allowlists skills in its spec; the workflow activates a subset per run (the
shared evidence skill plus one lane). Each loaded skill records its semantic version and
content hash for the manifest.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path

from google.adk.skills import load_skill_from_dir
from pydantic import BaseModel, ConfigDict

from risk_review.runtime.spec import SpecError


class LoadedSkill(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    owner: str
    version: str
    governance_tier: str
    content_hash: str
    body: str
    path: Path

    @property
    def instruction_tokens_estimate(self) -> int:
        return len(self.body) // 4


def _skill_dirs(directories: Iterable[Path]) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for directory in directories:
        if not directory.is_dir():
            continue
        for candidate in sorted(directory.iterdir()):
            if (candidate / "SKILL.md").is_file():
                if candidate.name in found:
                    raise SpecError(
                        f"skill name {candidate.name!r} found twice: "
                        f"{found[candidate.name]} and {candidate}"
                    )
                found[candidate.name] = candidate
    return found


def load_skill(skill_dir: Path) -> LoadedSkill:
    skill = load_skill_from_dir(skill_dir)
    frontmatter = skill.frontmatter
    metadata = dict(frontmatter.metadata or {})
    missing = [key for key in ("owner", "version", "governance_tier") if not metadata.get(key)]
    if missing:
        raise SpecError(f"skill {skill_dir.name}: frontmatter metadata missing {missing}")
    if frontmatter.name != skill_dir.name:
        raise SpecError(
            f"skill {skill_dir.name}: frontmatter name {frontmatter.name!r} "
            "must match the directory"
        )
    raw = (skill_dir / "SKILL.md").read_bytes()
    return LoadedSkill(
        name=frontmatter.name,
        description=frontmatter.description,
        owner=str(metadata["owner"]),
        version=str(metadata["version"]),
        governance_tier=str(metadata["governance_tier"]),
        content_hash=hashlib.sha256(raw).hexdigest()[:16],
        body=skill.instructions.strip(),
        path=skill_dir,
    )


def load_allowlisted_skills(
    directories: Iterable[Path], enabled: Iterable[str]
) -> dict[str, LoadedSkill]:
    """Every enabled skill, loaded; an enabled name without a directory fails construction."""
    available = _skill_dirs(directories)
    loaded: dict[str, LoadedSkill] = {}
    for name in enabled:
        if name not in available:
            raise SpecError(f"enabled skill {name!r} not found in {[str(d) for d in directories]}")
        loaded[name] = load_skill(available[name])
    return loaded


def render_skills(skills: Iterable[LoadedSkill]) -> str:
    sections = [f"## Skill: {skill.name} (v{skill.version})\n\n{skill.body}" for skill in skills]
    return "\n\n".join(sections)
