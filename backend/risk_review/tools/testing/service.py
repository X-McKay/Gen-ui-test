"""Runs a pytest selection in the backend with a timeout and truncated output."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from risk_review.tools.common.errors import ToolError, invalid_input

MAX_OUTPUT_CHARS = 4000
KEYWORD_PATTERN = re.compile(r"^[A-Za-z0-9_\-\[\]\. :/]+$")


class TestRunResult(BaseModel):
    ok: Literal[True] = True
    keyword: str
    exit_code: int
    passed: int
    failed: int
    errors: int
    timed_out: bool
    output_tail: str


class TestRunner:
    def __init__(self, backend_dir: Path, timeout_s: int = 180) -> None:
        self.backend_dir = backend_dir
        self.timeout_s = timeout_s

    def run(self, keyword: str) -> TestRunResult | ToolError:
        keyword = keyword.strip()
        if not keyword or len(keyword) > 120 or not KEYWORD_PATTERN.match(keyword):
            return invalid_input("keyword must be a short pytest -k expression or test path.")
        command = [
            "uv",
            "run",
            "pytest",
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
            "-k",
            keyword,
        ]
        timed_out = False
        try:
            completed = subprocess.run(
                command,
                cwd=self.backend_dir,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                check=False,
            )
            output, exit_code = completed.stdout + completed.stderr, completed.returncode
        except subprocess.TimeoutExpired as error:
            timed_out = True
            output = (
                (error.stdout or b"").decode(errors="replace")
                if isinstance(error.stdout, bytes)
                else str(error.stdout or "")
            )
            exit_code = -1
        counts = {"passed": 0, "failed": 0, "error": 0}
        for amount, word in re.findall(r"(\d+) (passed|failed|error)", output):
            counts[word] = int(amount)
        return TestRunResult(
            keyword=keyword,
            exit_code=exit_code,
            passed=counts["passed"],
            failed=counts["failed"],
            errors=counts["error"],
            timed_out=timed_out,
            output_tail=output[-MAX_OUTPUT_CHARS:],
        )
