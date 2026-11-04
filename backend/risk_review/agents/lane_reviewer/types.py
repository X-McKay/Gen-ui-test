"""Typed output of the lane reviewer. Validated in code before anything downstream uses it."""

from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["low", "medium", "high", "critical"]
ReviewStatus = Literal["completed", "needs_information", "budget_exhausted", "failed"]


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str = Field(description="Repository-relative path")
    line: int = Field(ge=1)
    quote: str = Field(min_length=1, max_length=300, description="The exact line, trimmed")


class Finding(BaseModel):
    """One risk the reviewer claims, with the evidence to check it and the test to catch it."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=8, max_length=120)
    category: str = Field(description="Short slug, e.g. logging-leak, model-sets-decision")
    severity: Severity
    file: str
    line: int = Field(ge=1)
    invariant: str = Field(description="The rule from the skill that is at risk")
    failure_scenario: str = Field(
        min_length=20, description="Concrete input or state, then the wrong outcome"
    )
    evidence: list[Evidence] = Field(min_length=1, max_length=5)
    proposed_test: str = Field(min_length=10, description="The test that would catch it")
    confidence: float = Field(ge=0.0, le=1.0)

    @property
    def finding_id(self) -> str:
        digest = hashlib.sha256(f"{self.file}:{self.line}:{self.category}".encode()).hexdigest()
        return digest[:12]


class ReviewOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ReviewStatus
    lane: str
    findings: list[Finding] = Field(default_factory=list)
    files_examined: list[str] = Field(default_factory=list)
    notes: str | None = None
