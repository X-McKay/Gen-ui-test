"""Eval case model and dataset loading. Datasets are YAML files, one case each."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

EVALS_DIR = Path(__file__).resolve().parent
DATASETS_DIR = EVALS_DIR / "datasets"
FIXTURES_DIR = EVALS_DIR / "fixtures"


class ExpectedFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    file: str
    lines: tuple[int, int] = Field(description="Inclusive window a reported line must fall in")
    categories: list[str] = Field(default_factory=list, description="Any-of; informational")
    min_severity: str = "low"


class Decoy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    file: str
    lines: tuple[int, int]


class TrajectoryExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_tools: list[str]
    required_tools: list[str] = Field(default_factory=list)
    max_report_calls: int = 3
    max_tool_errors: int = 4


class OperationalLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_latency_s: float = 600
    max_model_requests: int = 40
    max_total_tokens: int = 650_000


class EvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    suite: str = ""
    lane: str
    repository: str = Field(description="Fixture directory relative to evals/risk_review/fixtures")
    tags: list[str] = Field(default_factory=list, description="Risk scenario ids and categories")
    expected_findings: list[ExpectedFinding] = Field(default_factory=list)
    decoys: list[Decoy] = Field(default_factory=list)
    forbidden_strings: list[str] = Field(
        default_factory=list, description="Must not appear anywhere in the lane result"
    )
    planted_files: dict[str, str] = Field(
        default_factory=dict,
        description="Files written into the working copy at run time (e.g. a .env with a "
        "sentinel), so secret-looking content is never committed",
    )
    trajectory: TrajectoryExpectation
    operational: OperationalLimits = Field(default_factory=OperationalLimits)

    @property
    def repository_root(self) -> Path:
        return (FIXTURES_DIR / self.repository).resolve()


def materialize(case: EvalCase, into: Path) -> Path:
    """Copy the fixture into ``into`` and write the planted files; the review runs on the
    copy, never on the committed tree."""
    root = into / case.repository
    shutil.copytree(case.repository_root, root)
    for relative, content in case.planted_files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root


def load_suite(suite: str) -> list[EvalCase]:
    directory = DATASETS_DIR / suite
    if not directory.is_dir():
        raise FileNotFoundError(f"no dataset suite {suite!r} under {DATASETS_DIR}")
    cases: list[EvalCase] = []
    for path in sorted(directory.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        case = EvalCase.model_validate({**raw, "suite": suite})
        if not case.repository_root.is_dir():
            raise FileNotFoundError(f"{case.id}: fixture missing: {case.repository_root}")
        cases.append(case)
    if not cases:
        raise FileNotFoundError(f"suite {suite!r} has no cases")
    return cases


def suite_digest(cases: list[EvalCase]) -> str:
    payload = "\n".join(case.model_dump_json() for case in cases)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]
