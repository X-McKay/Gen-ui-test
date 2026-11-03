from __future__ import annotations

from pathlib import Path

from app.repo_analysis.inventory import (
    MAX_FILE_BYTES,
    README_EXCERPT_CHARS,
    RepositoryInventory,
    build_inventory,
)


def test_hr_screening_inventory(hr_screening_inventory: RepositoryInventory) -> None:
    inventory = hr_screening_inventory
    assert inventory.file_count == 16
    assert inventory.truncated is False
    assert inventory.languages["Python"] == 9
    assert inventory.primary_language == "Python"
    assert inventory.manifests == ["requirements.txt"]
    assert inventory.has_dockerfile is True
    assert inventory.dockerfiles == ["Dockerfile"]
    assert inventory.iac_files == ["infra/terraform/main.tf"]
    assert inventory.ci_files == [".github/workflows/ci.yml"]
    assert inventory.config_files == [".env.example"]
    assert inventory.readme_path == "README.md"
    assert inventory.readme_text.startswith("# Candidate Summary Assistant")
    assert [document.path for document in inventory.documents] == ["docs/retention.md"]
    assert "requirements.txt" not in [document.path for document in inventory.documents]


def test_log_search_inventory(log_search_inventory: RepositoryInventory) -> None:
    inventory = log_search_inventory
    assert inventory.file_count == 7
    assert inventory.manifests == ["requirements.txt"]
    assert inventory.has_dockerfile is True
    assert inventory.iac_files == []
    assert inventory.readme_path == "README.md"
    assert [document.path for document in inventory.documents] == ["docs/privacy.md"]


def test_text_files_have_contents(hr_screening_inventory: RepositoryInventory) -> None:
    candidate = hr_screening_inventory.file("src/models/candidate.py")
    assert candidate is not None and candidate.text is not None
    assert "salary_expectation" in candidate.text
    assert candidate.extension == ".py"
    assert candidate.name == "candidate.py"


def test_max_files_limit_truncates(hr_screening_root: Path) -> None:
    inventory = build_inventory(hr_screening_root, max_files=3)
    assert inventory.file_count == 3
    assert inventory.truncated is True
    assert len(inventory.files) == 3


def test_skips_binaries_vendored_directories_and_oversized_files(tmp_path: Path) -> None:
    (tmp_path / "node_modules" / "lib").mkdir(parents=True)
    (tmp_path / "node_modules" / "lib" / "index.js").write_text("module.exports = 1;\n")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("[core]\n")
    (tmp_path / "vendor").mkdir()
    (tmp_path / "vendor" / "dep.py").write_text("import openai\n")
    (tmp_path / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
    (tmp_path / "blob.dat").write_bytes(b"\x00\x01\x02binary")
    (tmp_path / "huge.txt").write_text("x" * (MAX_FILE_BYTES + 1))
    (tmp_path / "README.md").write_text("# Demo\n" + "words " * 2000)
    (tmp_path / "app.py").write_text("print('hi')\n")

    inventory = build_inventory(tmp_path, max_files=100)
    paths = [entry.path for entry in inventory.files]
    assert "node_modules/lib/index.js" not in paths
    assert ".git/config" not in paths
    assert "vendor/dep.py" not in paths
    assert inventory.file_count == 5
    assert inventory.file("logo.png") is not None
    assert inventory.file("logo.png").text is None  # type: ignore[union-attr]
    assert inventory.file("blob.dat").text is None  # type: ignore[union-attr]
    assert inventory.file("huge.txt").text is None  # type: ignore[union-attr]
    assert inventory.skipped_binary_count == 3
    assert inventory.scanned_file_count == 2
    assert len(inventory.readme_text) == README_EXCERPT_CHARS


def test_walk_is_deterministic(hr_screening_root: Path) -> None:
    first = [entry.path for entry in build_inventory(hr_screening_root, max_files=100).files]
    second = [entry.path for entry in build_inventory(hr_screening_root, max_files=100).files]
    assert first == second
    assert first[0] == ".env.example"  # root files sorted, then sorted subdirectories


def test_kubernetes_manifest_detected_by_content(tmp_path: Path) -> None:
    (tmp_path / "deployment.yaml").write_text(
        "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: api\n"
    )
    (tmp_path / "docker-compose.yml").write_text("services:\n  api:\n    image: api\n")
    inventory = build_inventory(tmp_path, max_files=10)
    assert inventory.iac_files == ["deployment.yaml"]
    assert inventory.config_files == ["docker-compose.yml"]
