"""The capability manifest: the bill of materials for one built agent.

Its id appears in every trace line, run metric and eval report, so a result can always be
joined to the exact configuration that produced it.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from risk_review import PACKAGE_VERSION


class SkillEntry(BaseModel):
    name: str
    version: str
    content_hash: str
    active: bool


class Manifest(BaseModel):
    manifest_id: str = ""
    agent_name: str
    agent_version: str
    contract_version: int
    execution_class: str
    governance_tier: str
    risk_assessment_digest: str
    model_policy: str
    provider: str
    model_id: str
    model_settings: dict[str, float | int | bool]
    pricing_version: str
    instruction_hash: str
    skills: list[SkillEntry]
    toolsets: list[str]
    tools: list[str]
    output_schema_hash: str
    budgets: dict[str, float | int]
    worker_version: str = PACKAGE_VERSION
    git_commit: str = Field(default="unknown")

    def finalize(self) -> Manifest:
        payload = self.model_dump(exclude={"manifest_id"})
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        self.manifest_id = digest[:16]
        return self


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def text_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def git_commit(repository_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repository_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    return completed.stdout.strip() or "unknown"
