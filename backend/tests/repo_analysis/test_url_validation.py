from __future__ import annotations

import pytest

from app.repo_analysis.clone_repository import RepositoryUrlError, validate_repository_url

ALLOWED = ["github.com", "gitlab.com", "dev.azure.com"]


@pytest.mark.parametrize(
    ("url", "expected_url", "host", "owner", "name"),
    [
        (
            "https://github.com/acme/widgets",
            "https://github.com/acme/widgets",
            "github.com",
            "acme",
            "widgets",
        ),
        (
            "https://github.com/acme/widgets.git",
            "https://github.com/acme/widgets",
            "github.com",
            "acme",
            "widgets",
        ),
        (
            "https://GitHub.com/acme/widgets/",
            "https://github.com/acme/widgets",
            "github.com",
            "acme",
            "widgets",
        ),
        (
            "https://gitlab.com/group/subgroup/project",
            "https://gitlab.com/group/subgroup/project",
            "gitlab.com",
            "group/subgroup",
            "project",
        ),
        (
            "https://internal.gitlab.com/team/repo",
            "https://internal.gitlab.com/team/repo",
            "internal.gitlab.com",
            "team",
            "repo",
        ),
        (
            "https://dev.azure.com/org/project/_git/repo",
            "https://dev.azure.com/org/project/_git/repo",
            "dev.azure.com",
            "org/project/_git",
            "repo",
        ),
        (
            "  https://github.com/acme/widgets?tab=readme  ",
            "https://github.com/acme/widgets",
            "github.com",
            "acme",
            "widgets",
        ),
    ],
)
def test_allowed_urls(url: str, expected_url: str, host: str, owner: str, name: str) -> None:
    parsed = validate_repository_url(url, ALLOWED)
    assert parsed.url == expected_url
    assert parsed.host == host
    assert parsed.owner == owner
    assert parsed.name == name
    assert parsed.display_name == f"{owner}/{name}"


@pytest.mark.parametrize(
    ("url", "message_fragment"),
    [
        ("https://example.com/acme/widgets", "Host example.com is not allowed"),
        ("https://github.com.evil.example/acme/widgets", "not allowed"),
        ("https://notgithub.com/acme/widgets", "Host notgithub.com is not allowed"),
        ("https://user:ghp_secret@github.com/acme/widgets", "Remove credentials"),
        ("https://token@github.com/acme/widgets", "Remove credentials"),
        ("git@github.com:acme/widgets.git", "SSH URLs are not supported"),
        ("ssh://git@github.com/acme/widgets.git", "Only https"),
        ("file:///home/al/repos/widgets", "Only https"),
        ("http://github.com/acme/widgets", "Only https"),
        ("https://localhost/acme/widgets", "Host localhost is not allowed"),
        ("https://127.0.0.1/acme/widgets", "not allowed"),
        ("https://[::1]/acme/widgets", "not allowed"),
        ("https://github.com:8443/acme/widgets", "Custom ports"),
        ("https://github.com/acme", "must point at a repository"),
        ("https://github.com/", "must point at a repository"),
        ("github.com/acme/widgets", "Only https"),
        ("", "Enter the repository URL"),
        ("ftp://github.com/acme/widgets", "Unsupported URL scheme"),
    ],
)
def test_rejected_urls(url: str, message_fragment: str) -> None:
    with pytest.raises(RepositoryUrlError) as excinfo:
        validate_repository_url(url, ALLOWED)
    assert message_fragment in str(excinfo.value)


def test_disallowed_host_message_lists_allowed_hosts() -> None:
    with pytest.raises(RepositoryUrlError) as excinfo:
        validate_repository_url("https://example.com/acme/widgets", ALLOWED)
    assert str(excinfo.value) == (
        "Host example.com is not allowed. Allowed: github.com, gitlab.com, dev.azure.com"
    )


def test_credentials_are_not_echoed_in_the_message() -> None:
    with pytest.raises(RepositoryUrlError) as excinfo:
        validate_repository_url("https://user:ghp_FAKE123456@github.com/acme/widgets", ALLOWED)
    assert "ghp_FAKE123456" not in str(excinfo.value)
