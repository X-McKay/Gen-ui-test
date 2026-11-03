"""A minimal stand-in for ADK's ToolContext: only ``state`` is used by the tools."""

from __future__ import annotations

from typing import Any


class FakeToolContext:
    def __init__(self, intake_id: str) -> None:
        self.state: dict[str, Any] = {"_ag_ui_thread_id": intake_id}
