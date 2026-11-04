"""Record schema for the planted fixture."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Source = Literal["user", "model", "repo"]


class FieldMeta(BaseModel):
    value: object = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source: Source = "user"
    confirmed: bool = False


class IntakeRecord(BaseModel):
    fields: dict[str, FieldMeta] = Field(default_factory=dict)
    assessment: dict[str, object] = Field(default_factory=dict)

    def set_field(self, path: str, value: object, *, source: Source, confidence: float, confirmed: bool) -> None:
        self.fields[path] = FieldMeta(value=value, confidence=confidence, source=source, confirmed=confirmed)
