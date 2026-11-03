"""Isolated database for intake and agent tests."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_database(tmp_path: Path) -> Iterator[None]:
    from app import settings as settings_module
    from app.intake import repository

    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'intake.db'}"
    os.environ["MOCK_MODEL"] = "1"
    settings_module.get_settings.cache_clear()
    repository.reset_engine()
    yield
    if previous is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = previous
    settings_module.get_settings.cache_clear()
    repository.reset_engine()
