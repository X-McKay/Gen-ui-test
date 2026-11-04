from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import pytest
from git import GitCommandError

from app.repo_analysis import clone_repository as clone_module
from app.repo_analysis.clone_repository import (
    FIXTURE_REPOSITORIES,
    RepositoryCloneError,
    RepositoryTooLargeError,
    RepositoryUrlError,
    authorization_header,
    clone_environment,
    clone_repository,
    redact_secrets,
    temporary_clone,
)

HR_SCREENING_URL = "https://github.com/intake-fixtures/hr-screening"
LOG_SEARCH_URL = "https://github.com/intake-fixtures/log-search"


@pytest.mark.parametrize(
    ("text", "forbidden", "kept"),
    [
        ("token ghp_FAKE123456 leaked", "ghp_FAKE123456", "token"),
        ("github_pat_11ABCDEF_xyz987 in log", "github_pat_11ABCDEF_xyz987", "in log"),
        ("glpat-abcdef123456 here", "glpat-abcdef123456", "here"),
        ("key AKIAIOSFODNN7EXAMPLE used", "AKIAIOSFODNN7EXAMPLE", "used"),
        ("OPENAI_API_KEY=sk-FAKE000000000000", "sk-FAKE000000000000", "OPENAI_API_KEY="),
        ("Authorization: Bearer abcdefghijklmnop", "abcdefghijklmnop", "Authorization:"),
        ("Authorization: Basic dXNlcjpwYXNz", "dXNlcjpwYXNz", "Authorization:"),
        ("https://user:hunter2@github.com/acme/widgets", "hunter2", "github.com/acme/widgets"),
        ("password: correct-horse", "correct-horse", "password:"),
        ("ATS_EXPORT_TOKEN=ghp_FAKE123  # comment", "ghp_FAKE123", "# comment"),
    ],
)
def test_redact_secrets(text: str, forbidden: str, kept: str) -> None:
    redacted = redact_secrets(text)
    assert forbidden not in redacted
    assert kept in redacted
    assert "***" in redacted


def test_redact_secrets_removes_known_token() -> None:
    assert redact_secrets("failed for weird-token-format", ["weird-token-format"]) == (
        "failed for ***"
    )


def test_redact_secrets_leaves_plain_text_alone() -> None:
    text = "fatal: repository 'https://github.com/acme/missing/' not found"
    assert redact_secrets(text) == text


@pytest.mark.parametrize(
    ("host", "prefix", "decoded"),
    [
        ("github.com", "Basic ", "x-access-token:tok"),
        ("gitlab.com", "Basic ", "oauth2:tok"),
        ("dev.azure.com", "Basic ", ":tok"),
    ],
)
def test_authorization_header_basic_variants(host: str, prefix: str, decoded: str) -> None:
    header = authorization_header(host, "tok")
    assert header.startswith(prefix)
    assert base64.b64decode(header[len(prefix) :]).decode() == decoded


def test_authorization_header_bearer_for_other_hosts() -> None:
    assert authorization_header("git.example.org", "tok") == "Bearer tok"


def test_clone_environment_disables_prompts_and_injects_header() -> None:
    environment = clone_environment("github.com", "tok")
    assert environment["GIT_TERMINAL_PROMPT"] == "0"
    keys = {
        environment[f"GIT_CONFIG_KEY_{i}"]: environment[f"GIT_CONFIG_VALUE_{i}"] for i in range(2)
    }
    assert keys["credential.helper"] == ""
    assert keys["http.extraheader"].startswith("Authorization: Basic ")
    assert "tok" not in keys["http.extraheader"]  # base64-encoded, never raw


def test_clone_environment_without_token_has_no_header() -> None:
    environment = clone_environment("github.com", None)
    assert environment["GIT_CONFIG_COUNT"] == "1"
    assert "http.extraheader" not in environment.values()


def test_fixture_mapping_points_at_bundled_repositories() -> None:
    assert FIXTURE_REPOSITORIES[HR_SCREENING_URL].is_dir()
    assert FIXTURE_REPOSITORIES[LOG_SEARCH_URL].is_dir()
    for url, directory in FIXTURE_REPOSITORIES.items():
        assert url.startswith("https://github.com/intake-fixtures/")
        assert (directory / "README.md").is_file(), url


def test_mock_mode_clone_copies_fixture_without_network(tmp_path: Path) -> None:
    cloned = clone_repository(
        HR_SCREENING_URL, None, timeout_s=5, max_size_mb=10, destination=tmp_path / "repo"
    )
    assert cloned.from_fixture is True
    assert (cloned.path / "README.md").is_file()
    assert (cloned.path / "src" / "models" / "candidate.py").is_file()
    assert cloned.size_bytes > 0


def test_mock_mode_clone_accepts_git_suffix(tmp_path: Path) -> None:
    cloned = clone_repository(
        LOG_SEARCH_URL + ".git", None, timeout_s=5, max_size_mb=10, destination=tmp_path / "repo"
    )
    assert cloned.from_fixture is True
    assert (cloned.path / "docs" / "privacy.md").is_file()


def test_temporary_clone_cleans_up() -> None:
    with temporary_clone(HR_SCREENING_URL, None, timeout_s=5, max_size_mb=10) as cloned:
        workspace = cloned.path.parent
        assert cloned.path.is_dir()
    assert not workspace.exists()


def test_temporary_clone_cleans_up_on_error() -> None:
    workspace: Path | None = None
    with (
        pytest.raises(RuntimeError, match="boom"),
        temporary_clone(HR_SCREENING_URL, None, timeout_s=5, max_size_mb=10) as cloned,
    ):
        workspace = cloned.path.parent
        raise RuntimeError("boom")
    assert workspace is not None
    assert not workspace.exists()


def test_size_cap_is_enforced(tmp_path: Path) -> None:
    with pytest.raises(RepositoryTooLargeError, match="0 MB limit"):
        clone_repository(
            HR_SCREENING_URL, None, timeout_s=5, max_size_mb=0, destination=tmp_path / "repo"
        )


@pytest.mark.parametrize("url", ["file:///tmp/repo", "http://github.com/a/b", "ssh://git@x/a/b"])
def test_clone_rejects_non_https(url: str, tmp_path: Path) -> None:
    with pytest.raises(RepositoryUrlError):
        clone_repository(url, None, timeout_s=5, max_size_mb=10, destination=tmp_path / "repo")


def test_clone_rejects_credentials_in_url(tmp_path: Path) -> None:
    with pytest.raises(RepositoryUrlError):
        clone_repository(
            "https://x:y@github.com/a/b", None, timeout_s=5, max_size_mb=10, destination=tmp_path
        )


class _FakeGit:
    """Stands in for ``git.Git`` so the non-mock path can be exercised offline."""

    calls: list[tuple[tuple[str, ...], dict[str, Any]]] = []
    failure: Exception | None = None

    def __init__(self, working_dir: str) -> None:
        self.working_dir = working_dir

    def clone(self, *args: str, **kwargs: Any) -> str:
        type(self).calls.append((args, kwargs))
        if type(self).failure is not None:
            raise type(self).failure
        destination = Path(args[-1])
        destination.mkdir(parents=True)
        (destination / "README.md").write_text("# cloned\n")
        return ""


@pytest.fixture
def fake_git(monkeypatch: pytest.MonkeyPatch) -> type[_FakeGit]:
    _FakeGit.calls = []
    _FakeGit.failure = None
    monkeypatch.setattr(clone_module, "Git", _FakeGit)
    return _FakeGit


def test_real_clone_path_uses_safe_options(fake_git: type[_FakeGit], tmp_path: Path) -> None:
    cloned = clone_repository(
        "https://github.com/acme/widgets",
        "ghp_FAKE123456",
        timeout_s=42,
        max_size_mb=10,
        destination=tmp_path / "repo",
    )
    assert cloned.from_fixture is False
    assert (cloned.path / "README.md").is_file()
    (args, kwargs) = fake_git.calls[0]
    assert "--depth" in args and "1" in args
    assert "--single-branch" in args
    assert "--no-tags" in args
    assert "--no-recurse-submodules" in args
    assert args[args.index("--") + 1] == "https://github.com/acme/widgets"
    assert "ghp_FAKE123456" not in " ".join(args)
    assert kwargs["kill_after_timeout"] == 42.0
    environment = kwargs["env"]
    assert environment["GIT_TERMINAL_PROMPT"] == "0"
    header_values = [
        value for key, value in environment.items() if key.startswith("GIT_CONFIG_VALUE")
    ]
    assert any(value.startswith("Authorization: Basic ") for value in header_values)


def test_clone_timeout_is_reported_without_secrets(
    fake_git: type[_FakeGit], tmp_path: Path
) -> None:
    fake_git.failure = GitCommandError(
        ["git", "clone"], 128, stderr="Timeout: the command did not complete in 42 secs."
    )
    with pytest.raises(RepositoryCloneError, match="timed out after 42 seconds"):
        clone_repository(
            "https://github.com/acme/widgets",
            "ghp_FAKE123456",
            timeout_s=42,
            max_size_mb=10,
            destination=tmp_path / "repo",
        )


def test_clone_failure_messages_are_redacted(fake_git: type[_FakeGit], tmp_path: Path) -> None:
    fake_git.failure = GitCommandError(
        ["git", "clone"],
        128,
        stderr="fatal: unable to access with token ghp_FAKE123456 and Bearer abcdefghijklmnop",
    )
    with pytest.raises(RepositoryCloneError) as excinfo:
        clone_repository(
            "https://github.com/acme/widgets",
            "ghp_FAKE123456",
            timeout_s=42,
            max_size_mb=10,
            destination=tmp_path / "repo",
        )
    message = str(excinfo.value)
    assert "ghp_FAKE123456" not in message
    assert "abcdefghijklmnop" not in message
    assert message.startswith("Cloning failed")


def test_clone_not_found_message(fake_git: type[_FakeGit], tmp_path: Path) -> None:
    fake_git.failure = GitCommandError(
        ["git", "clone"], 128, stderr="fatal: repository 'https://github.com/a/b/' not found"
    )
    with pytest.raises(RepositoryCloneError, match="Repository not found"):
        clone_repository(
            "https://github.com/a/b", None, timeout_s=5, max_size_mb=10, destination=tmp_path / "r"
        )
