"""Dataset loading. One YAML file per suite under ``datasets/``, each a list of cases.

A case is a description, or a repository, plus what a careful reviewer would record from it:

* ``expected``: fields the text supports, with the value a reviewer would record. ``false``
  and ``[]`` are legitimate expectations: an ordinary tool clearly has no biometrics.
* ``absent``: fields the text says nothing about. A confident value here is an invention.
* ``inherent`` / ``residual``: the tiers the rules engine derives from ``expected`` when every
  value is confirmed. The loader checks them against the engine, so the dataset doubles as a
  readable specification of the point tables.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from app.governance.classify import reclassify
from app.intake.record_service import coerce_value
from app.intake.schema import IntakeRecord, RiskTier, new_record

EVALS_DIR = Path(__file__).resolve().parent
DATASETS_DIR = EVALS_DIR / "datasets"
BACKEND_DIR = EVALS_DIR.parents[1]


class AssessmentCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tags: list[str] = Field(default_factory=list)
    description: str | None = Field(default=None, min_length=40)
    repository: str | None = Field(
        default=None, description="Path relative to backend/, assessed by the fact-finder agents"
    )
    expected: dict[str, object] = Field(default_factory=dict)
    absent: list[str] = Field(default_factory=list)
    inherent: RiskTier
    residual: RiskTier
    note: str | None = None


class DatasetError(ValueError):
    pass


def record_from_values(values: dict[str, object], *, confirmed: bool) -> IntakeRecord:
    """A record holding ``values`` as user answers (confirmed) or inferences (unconfirmed)."""
    record = new_record("eval")
    for path, value in values.items():
        record.set_field(
            path,
            coerce_value(path, value),
            source="user" if confirmed else "inferred",
            confidence=1.0 if confirmed else 0.9,
            confirmed=confirmed,
        )
    return reclassify(record)


def validate_case(case: AssessmentCase) -> list[str]:
    """Problems with a case: unknown fields, invalid values or tiers that disagree with the
    engine. An empty list means the case is sound."""
    problems: list[str] = []
    if (case.description is None) == (case.repository is None):
        problems.append(f"{case.id}: give exactly one of description or repository")
    if case.repository is not None and not (BACKEND_DIR / case.repository).is_dir():
        problems.append(f"{case.id}: repository {case.repository} is not a directory")
    try:
        record = record_from_values(case.expected, confirmed=True)
    except (KeyError, ValueError) as error:
        return [f"{case.id}: expected values do not fit the record: {error}"]
    probe = new_record("probe")
    for path in case.absent:
        try:
            probe.get_field(path)
        except KeyError:
            problems.append(f"{case.id}: absent names an unknown field {path}")
        if path in case.expected:
            problems.append(f"{case.id}: {path} is both expected and absent")
    inherent = record.assessment.inherent_risk.tier
    residual = record.assessment.residual_risk.tier
    if inherent is not case.inherent:
        problems.append(f"{case.id}: engine says inherent {inherent}, case says {case.inherent}")
    if residual is not case.residual:
        problems.append(f"{case.id}: engine says residual {residual}, case says {case.residual}")
    return problems


def load_suite(suite: str) -> list[AssessmentCase]:
    path = DATASETS_DIR / f"{suite}.yaml"
    if not path.is_file():
        raise DatasetError(f"no dataset {path}")
    raw = yaml.safe_load(path.read_text()) or {}
    cases = [AssessmentCase.model_validate(item) for item in raw.get("cases", [])]
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise DatasetError(f"duplicate case ids in {path}")
    problems = [problem for case in cases for problem in validate_case(case)]
    if problems:
        raise DatasetError("\n".join(problems))
    return cases


def suite_digest(cases: list[AssessmentCase]) -> str:
    payload = "\n".join(case.model_dump_json() for case in cases)
    return hashlib.sha256(payload.encode()).hexdigest()[:12]
