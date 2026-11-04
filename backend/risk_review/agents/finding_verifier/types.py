"""Typed output of the finding verifier."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from risk_review.agents.lane_reviewer.types import Evidence

VerdictKind = Literal["confirmed", "refuted", "uncertain"]


class Verdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: str
    verdict: VerdictKind
    reasoning: str = Field(min_length=20, max_length=1500)
    evidence: list[Evidence] = Field(default_factory=list, max_length=5)
    existing_test_covers_it: bool = False
    confidence: float = Field(ge=0.0, le=1.0)


class VerificationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "budget_exhausted", "failed"]
    verdict: Verdict | None = None
    notes: str | None = None
