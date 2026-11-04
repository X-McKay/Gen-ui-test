"""Tool policy records: the reviewable contract every tool carries (playbook chapter 5).

The policy is checked by the factory: an agent whose execution class is ``ephemeral`` may
only enable tools whose effect is ``read``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

Effect = Literal["read", "write_reversible", "write_consequential"]
RetrySafety = Literal["safe", "idempotency_key_required", "unsafe"]
ExecutionClass = Literal["ephemeral", "durable", "human_governed"]
DataClassification = Literal["public", "internal", "confidential"]

MINIMUM_EXECUTION_CLASS: dict[Effect, ExecutionClass] = {
    "read": "ephemeral",
    "write_reversible": "durable",
    "write_consequential": "human_governed",
}

EXECUTION_CLASS_RANK: dict[ExecutionClass, int] = {
    "ephemeral": 0,
    "durable": 1,
    "human_governed": 2,
}


class ToolPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    owner: str
    effect: Effect
    retry_safety: RetrySafety
    timeout_seconds: int
    data_classification: DataClassification
    max_output_bytes: int

    def permitted_under(self, execution_class: ExecutionClass) -> bool:
        required = MINIMUM_EXECUTION_CLASS[self.effect]
        return EXECUTION_CLASS_RANK[execution_class] >= EXECUTION_CLASS_RANK[required]
