"""The repository service: a bounded, read-only view of a directory tree.

Every path is resolved under the root and refused when it escapes it, is a symlink out of
it, or matches the secret patterns (``.env*``, ``*.db``, key material). Outputs are capped
in lines, bytes and hit counts so a tool result can never flood the model's context.
"""

from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path

from risk_review.tools.common.errors import (
    ToolError,
    invalid_input,
    limit_exceeded,
    not_found,
    policy_rejected,
)
from risk_review.tools.repo.types import (
    FileEntry,
    ListFilesResult,
    ReadFileResult,
    SearchHit,
    SearchResult,
)

IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        "node_modules",
        ".venv",
        ".next",
        "__pycache__",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        "dist",
        "build",
        "out",
        "htmlcov",
        "playwright-report",
        "test-results",
        "blob-report",
        ".playwright-mcp",
        "reports",
    }
)
DENIED_FILE_PATTERNS = (
    ".env",
    ".env.*",
    "*.db",
    "*.pem",
    "*.key",
    "*.p12",
    "*.sqlite",
    "*.sqlite3",
)
DENIED_SUFFIXES = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".woff",
    ".woff2",
    ".pdf",
    ".zip",
)

MAX_FILE_BYTES = 512 * 1024
MAX_READ_LINES = 200
MAX_READ_BYTES = 24 * 1024
MAX_LIST_ENTRIES = 200
MAX_SEARCH_HITS = 40
MAX_SEARCH_FILES = 4000
MAX_PATTERN_LENGTH = 200
MAX_HIT_TEXT = 200


class RepoService:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        if not self.root.is_dir():
            raise ValueError(f"repository root is not a directory: {self.root}")

    # -- path policy ---------------------------------------------------------------------

    def _denied(self, relative: str) -> bool:
        name = Path(relative).name
        if any(fnmatch.fnmatch(name, pattern) for pattern in DENIED_FILE_PATTERNS):
            return True
        return name.lower().endswith(DENIED_SUFFIXES)

    def resolve(self, path: str) -> Path | ToolError:
        if not path or path.startswith(("/", "~")) or "\\" in path or "\x00" in path:
            return invalid_input("Use a relative path inside the repository.")
        candidate = (self.root / path).resolve()
        try:
            relative = candidate.relative_to(self.root)
        except ValueError:
            return policy_rejected("Path escapes the repository root.")
        if any(part in IGNORED_DIRECTORIES for part in relative.parts):
            return policy_rejected("Path is inside an ignored directory.")
        if self._denied(str(relative)):
            return policy_rejected("Path matches the secrets policy and cannot be read.")
        return candidate

    def iter_files(self, prefix: str = "") -> list[Path]:
        start = self.resolve(prefix) if prefix else self.root
        if isinstance(start, ToolError):
            return []
        if start.is_file():
            return [start]
        found: list[Path] = []
        for current, directories, files in os.walk(start, followlinks=False):
            directories[:] = sorted(d for d in directories if d not in IGNORED_DIRECTORIES)
            for name in sorted(files):
                full = Path(current) / name
                if full.is_symlink():
                    continue
                relative = str(full.relative_to(self.root))
                if self._denied(relative):
                    continue
                found.append(full)
        return found

    # -- operations ----------------------------------------------------------------------

    def list_files(
        self, prefix: str = "", limit: int = MAX_LIST_ENTRIES
    ) -> ListFilesResult | ToolError:
        if prefix:
            resolved = self.resolve(prefix)
            if isinstance(resolved, ToolError):
                return resolved
            if not resolved.exists():
                return not_found(f"No such path: {prefix}")
        limit = max(1, min(limit, MAX_LIST_ENTRIES))
        files = self.iter_files(prefix)
        entries = [
            FileEntry(path=str(f.relative_to(self.root)), size_bytes=f.stat().st_size)
            for f in files[:limit]
        ]
        return ListFilesResult(prefix=prefix, files=entries, truncated=len(files) > limit)

    def read_file(
        self, path: str, start_line: int = 1, end_line: int | None = None
    ) -> ReadFileResult | ToolError:
        resolved = self.resolve(path)
        if isinstance(resolved, ToolError):
            return resolved
        if not resolved.is_file():
            return not_found(f"No such file: {path}")
        if resolved.stat().st_size > MAX_FILE_BYTES:
            return limit_exceeded(
                f"File larger than {MAX_FILE_BYTES // 1024} KB; search it instead."
            )
        try:
            lines = resolved.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            return policy_rejected("Binary file.")
        total = len(lines)
        start = max(1, start_line)
        end = min(total, end_line if end_line is not None else start + MAX_READ_LINES - 1)
        end = min(end, start + MAX_READ_LINES - 1)
        if start > total:
            return invalid_input(f"start_line {start} is past the end of the file ({total} lines).")
        numbered: list[str] = []
        used = 0
        for number in range(start, end + 1):
            text = f"{number}| {lines[number - 1]}"
            used += len(text) + 1
            if used > MAX_READ_BYTES:
                end = number - 1
                break
            numbered.append(text)
        return ReadFileResult(
            path=path,
            start_line=start,
            end_line=end,
            total_lines=total,
            content="\n".join(numbered),
        )

    def search_text(
        self, pattern: str, prefix: str = "", limit: int = MAX_SEARCH_HITS
    ) -> SearchResult | ToolError:
        if not pattern or len(pattern) > MAX_PATTERN_LENGTH:
            return invalid_input(f"Pattern must be 1 to {MAX_PATTERN_LENGTH} characters.")
        try:
            regex = re.compile(pattern)
        except re.error as error:
            return invalid_input(f"Invalid regular expression: {error}")
        if prefix:
            resolved = self.resolve(prefix)
            if isinstance(resolved, ToolError):
                return resolved
            if not resolved.exists():
                return not_found(f"No such path: {prefix}")
        limit = max(1, min(limit, MAX_SEARCH_HITS))
        hits: list[SearchHit] = []
        searched = 0
        truncated = False
        for file in self.iter_files(prefix):
            if searched >= MAX_SEARCH_FILES:
                truncated = True
                break
            if file.stat().st_size > MAX_FILE_BYTES:
                continue
            try:
                text = file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            searched += 1
            for number, line in enumerate(text.splitlines(), start=1):
                if regex.search(line):
                    hits.append(
                        SearchHit(
                            path=str(file.relative_to(self.root)),
                            line=number,
                            text=line.strip()[:MAX_HIT_TEXT],
                        )
                    )
                    if len(hits) >= limit:
                        truncated = True
                        break
            if len(hits) >= limit:
                break
        return SearchResult(
            pattern=pattern, hits=hits, files_searched=searched, truncated=truncated
        )
