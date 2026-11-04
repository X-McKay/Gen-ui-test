"""Toolset id ``backend-tests``: one tool, ``run_backend_tests``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.base_toolset import BaseToolset
from google.adk.tools.function_tool import FunctionTool

from risk_review.tools.common.policy import ToolPolicy
from risk_review.tools.testing.service import TestRunner

TOOLSET_ID = "backend-tests"

POLICIES: dict[str, ToolPolicy] = {
    "run_backend_tests": ToolPolicy(
        name="run_backend_tests",
        owner="platform",
        effect="read",
        retry_safety="safe",
        timeout_seconds=180,
        data_classification="internal",
        max_output_bytes=8 * 1024,
    )
}


class BackendTestsToolset(BaseToolset):
    def __init__(self, backend_dir: Path) -> None:
        super().__init__()
        self.toolset_id = TOOLSET_ID
        self._runner = TestRunner(backend_dir)

    @property
    def policies(self) -> dict[str, ToolPolicy]:
        return POLICIES

    def run_backend_tests(self, keyword: str) -> dict[str, Any]:
        """Run the backend pytest suite filtered by a -k keyword or test path (max 3 minutes).

        Use it to check whether an existing test already covers the behaviour a finding
        claims is unguarded. Returns pass/fail counts and the output tail.
        """
        return self._runner.run(keyword).model_dump()

    async def get_tools(self, readonly_context: ReadonlyContext | None = None) -> list[BaseTool]:
        return [FunctionTool(self.run_backend_tests)]

    async def close(self) -> None:
        return None
