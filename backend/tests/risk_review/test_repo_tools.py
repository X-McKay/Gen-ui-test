"""Repository toolset: path policy, bounds and search (risk scenarios RR-01, RR-02)."""

from __future__ import annotations

from pathlib import Path

from risk_review.tools.common.errors import ToolError
from risk_review.tools.repo.service import MAX_READ_LINES, RepoService
from risk_review.tools.repo.types import ListFilesResult, ReadFileResult, SearchResult


def test_list_files_skips_ignored_directories_and_secret_files(tiny_repo: Path) -> None:
    result = RepoService(tiny_repo).list_files()
    assert isinstance(result, ListFilesResult)
    paths = [entry.path for entry in result.files]
    assert "backend/app/api.py" in paths
    assert "backend/app/safe.py" in paths
    assert not any(p.startswith("node_modules") for p in paths)
    assert ".env" not in paths
    assert "backend/intake.db" not in paths
    assert "image.png" not in paths
    assert "backend/link.txt" not in paths  # symlink


def test_read_file_numbers_lines_and_reports_total(tiny_repo: Path) -> None:
    result = RepoService(tiny_repo).read_file("backend/app/api.py", 4, 5)
    assert isinstance(result, ReadFileResult)
    assert result.start_line == 4 and result.end_line == 5 and result.total_lines == 6
    assert result.content.splitlines()[0].startswith("4| def create(")


def test_read_file_caps_lines(tmp_path: Path) -> None:
    root = tmp_path / "r"
    root.mkdir()
    (root / "big.py").write_text("\n".join(f"line {i}" for i in range(1, 1001)))
    result = RepoService(root).read_file("big.py")
    assert isinstance(result, ReadFileResult)
    assert result.end_line == MAX_READ_LINES and result.total_lines == 1000


def test_secret_and_traversal_paths_are_refused(tiny_repo: Path) -> None:
    service = RepoService(tiny_repo)
    for path in (".env", "backend/intake.db", "../outside.txt", "backend/../../outside.txt"):
        result = service.read_file(path)
        assert isinstance(result, ToolError), path
        assert result.kind == "policy_rejected"
    absolute = service.read_file(str(tiny_repo / "backend" / "app" / "api.py"))
    assert isinstance(absolute, ToolError) and absolute.kind == "invalid_input"


def test_symlink_outside_root_is_refused(tiny_repo: Path) -> None:
    result = RepoService(tiny_repo).read_file("backend/link.txt")
    assert isinstance(result, ToolError) and result.kind == "policy_rejected"


def test_ignored_directory_cannot_be_read_directly(tiny_repo: Path) -> None:
    result = RepoService(tiny_repo).read_file("node_modules/pkg/index.js")
    assert isinstance(result, ToolError) and result.kind == "policy_rejected"


def test_search_text_returns_hits_and_never_searches_secrets(tiny_repo: Path) -> None:
    result = RepoService(tiny_repo).search_text(r"SENTINELSECRET|logger\.info")
    assert isinstance(result, SearchResult)
    assert [(h.path, h.line) for h in result.hits] == [("backend/app/api.py", 5)]
    assert result.files_searched == 2


def test_search_text_validates_pattern(tiny_repo: Path) -> None:
    service = RepoService(tiny_repo)
    bad = service.search_text("(")
    assert isinstance(bad, ToolError) and bad.kind == "invalid_input"
    empty = service.search_text("")
    assert isinstance(empty, ToolError)


def test_search_limit_marks_truncation(tmp_path: Path) -> None:
    root = tmp_path / "r"
    root.mkdir()
    (root / "many.py").write_text("\n".join("hit" for _ in range(100)))
    result = RepoService(root).search_text("hit", limit=5)
    assert isinstance(result, SearchResult)
    assert len(result.hits) == 5 and result.truncated
