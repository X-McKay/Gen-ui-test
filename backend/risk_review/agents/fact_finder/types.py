"""Typed contract of the fact finder."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from risk_review.agents.lane_reviewer.types import Evidence

FactBasis = Literal["documented", "code", "absence"]
FactsStatus = Literal["completed", "needs_information", "budget_exhausted"]


class Fact(BaseModel):
    """One value for one record field, with the lines that show it."""

    model_config = ConfigDict(extra="forbid")

    field: str = Field(description="Dotted record path, e.g. data.processes_personal_data")
    value: object = Field(description="The value in the field's own type and enum values")
    confidence: float = Field(ge=0.0, le=1.0)
    basis: FactBasis = Field(
        description=(
            "documented = a document states it; code = the code shows it; "
            "absence = a thorough search found nothing (confidence at most 0.7)"
        )
    )
    evidence: list[Evidence] = Field(min_length=1, max_length=3)
    note: str | None = Field(default=None, max_length=300)


class FactsOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: FactsStatus
    lane: str
    facts: list[Fact] = Field(default_factory=list)
    files_examined: list[str] = Field(default_factory=list)
    notes: str | None = None
