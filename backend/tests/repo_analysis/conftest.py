"""Shared fixtures: offline model, isolated SQLite database, fixture repositories."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

# Must be set before ``app.settings`` builds the cached Settings object.
os.environ["MOCK_MODEL"] = "1"
os.environ.setdefault("ENVIRONMENT", "test")

from app.settings import get_settings

get_settings.cache_clear()

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "repos"
HR_SCREENING_URL = "https://github.com/intake-fixtures/hr-screening"
LOG_SEARCH_URL = "https://github.com/intake-fixtures/log-search"


@pytest.fixture(scope="session", autouse=True)
def isolated_database(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    from app.intake import intake_store

    database_path = tmp_path_factory.mktemp("db") / "intake-test.db"
    intake_store.reset_engine(f"sqlite:///{database_path}")
    get_settings.cache_clear()
    assert get_settings().mock_model is True
    yield
    intake_store.reset_engine()


@pytest.fixture(scope="session")
def hr_screening_root() -> Path:
    return FIXTURE_ROOT / "hr_screening"


@pytest.fixture(scope="session")
def log_search_root() -> Path:
    return FIXTURE_ROOT / "log_search"


@pytest.fixture(scope="session")
def hr_screening_inventory(hr_screening_root: Path):  # type: ignore[no-untyped-def]
    from app.repo_analysis.inventory import build_inventory

    return build_inventory(hr_screening_root, max_files=20_000)


@pytest.fixture(scope="session")
def log_search_inventory(log_search_root: Path):  # type: ignore[no-untyped-def]
    from app.repo_analysis.inventory import build_inventory

    return build_inventory(log_search_root, max_files=20_000)
