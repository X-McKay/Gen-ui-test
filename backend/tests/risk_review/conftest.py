"""Fixtures: a tiny repository tree and the repository root."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPOSITORY_ROOT / "backend"


@pytest.fixture
def repository_root() -> Path:
    return REPOSITORY_ROOT


@pytest.fixture
def tiny_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "backend" / "app").mkdir(parents=True)
    (root / "node_modules" / "pkg").mkdir(parents=True)
    (root / "backend" / "app" / "api.py").write_text(
        "import logging\n"
        "logger = logging.getLogger(__name__)\n"
        "\n"
        "def create(description: str) -> None:\n"
        '    logger.info("intake.create description=%s", description)\n'
        "    return None\n",
        encoding="utf-8",
    )
    (root / "backend" / "app" / "safe.py").write_text(
        "def ok() -> int:\n    return 1\n", encoding="utf-8"
    )
    (root / ".env").write_text("OPENAI_API_KEY=sk-SENTINELSECRET1234567890\n", encoding="utf-8")
    (root / "backend" / "intake.db").write_bytes(b"\x00\x01binary")
    (root / "node_modules" / "pkg" / "index.js").write_text("module.exports = 1\n")
    (root / "image.png").write_bytes(b"\x89PNG\r\n")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n")
    os.symlink(outside, root / "backend" / "link.txt")
    return root
