"""Registers the repository tools under the stable toolset id ``repo-read``."""

from __future__ import annotations

from pathlib import Path

from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.base_toolset import BaseToolset
from google.adk.tools.function_tool import FunctionTool

from risk_review.tools.common.policy import ToolPolicy
from risk_review.tools.repo.policy import REPO_TOOL_POLICIES
from risk_review.tools.repo.service import RepoService
from risk_review.tools.repo.tools import RepoTools

TOOLSET_ID = "repo-read"


class RepoReadToolset(BaseToolset):
    def __init__(self, root: Path) -> None:
        super().__init__()
        self.toolset_id = TOOLSET_ID
        self._tools = RepoTools(RepoService(root))

    @property
    def policies(self) -> dict[str, ToolPolicy]:
        return REPO_TOOL_POLICIES

    async def get_tools(self, readonly_context: ReadonlyContext | None = None) -> list[BaseTool]:
        return [
            FunctionTool(self._tools.list_files),
            FunctionTool(self._tools.read_file),
            FunctionTool(self._tools.search_text),
        ]

    async def close(self) -> None:
        return None
