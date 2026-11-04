"""Agent-facing adapters. Docstrings are the tool descriptions the model sees."""

from __future__ import annotations

from typing import Any

from risk_review.tools.repo.service import RepoService


class RepoTools:
    def __init__(self, service: RepoService) -> None:
        self._service = service

    def list_files(self, prefix: str = "", limit: int = 200) -> dict[str, Any]:
        """List files under a directory of the repository (relative path, '' for the root).

        Returns paths and sizes, sorted, at most ``limit`` entries. Ignored directories
        (node_modules, .venv, .git, build output) and secret files are never listed.
        """
        return self._service.list_files(prefix, limit).model_dump()

    def read_file(
        self, path: str, start_line: int = 1, end_line: int | None = None
    ) -> dict[str, Any]:
        """Read a file (relative path) as numbered lines 'N| text', at most 200 lines per call.

        Use start_line and end_line to page through longer files. The result says how many
        lines the file has in total.
        """
        return self._service.read_file(path, start_line, end_line).model_dump()

    def search_text(self, pattern: str, prefix: str = "", limit: int = 40) -> dict[str, Any]:
        """Search files under ``prefix`` with a Python regular expression.

        Returns up to ``limit`` hits as path, line number and the matching line. Use it to
        find call sites, loggers, sinks and definitions before reading the file.
        """
        return self._service.search_text(pattern, prefix, limit).model_dump()
