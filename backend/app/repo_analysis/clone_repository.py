"""Validate repository URLs and make shallow, read-only clones in a temporary directory.

Security posture:

- https only; the host must be on the allowlist; no credentials in the URL.
- The access token travels in an ``http.extraheader`` git config passed through the
  process environment (``GIT_CONFIG_*``), never in the URL and never on disk.
- Shallow, single-branch, no tags, no submodules, ``GIT_TERMINAL_PROMPT=0``; the git
  process is killed after ``timeout_s`` seconds.
- Repository code is never executed; the size is checked after the clone.
- Every exception message is passed through :func:`redact_secrets` before it propagates.

Outside ``ENVIRONMENT=production`` a handful of fixture URLs resolve to bundled directories
without touching the network (see :data:`FIXTURE_REPOSITORIES`).
"""

from __future__ import annotations

import base64
import ipaddress
import os
import re
import shutil
import tempfile
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from git import Git, GitCommandError

from app.settings import get_settings

FIXTURES_DIRECTORY = Path(__file__).resolve().parents[2] / "fixtures" / "repos"

#: Fixture URLs served from disk when ``MOCK_MODEL=1``. Keys are normalised URLs.
FIXTURE_REPOSITORIES: dict[str, Path] = {
    "https://github.com/intake-fixtures/hr-screening": FIXTURES_DIRECTORY / "hr_screening",
    "https://github.com/intake-fixtures/log-search": FIXTURES_DIRECTORY / "log_search",
}

BLOCKED_HOSTS: frozenset[str] = frozenset({"localhost", "localhost.localdomain", "0.0.0.0"})

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Provider token formats.
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{6,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{6,}\b"),
    re.compile(r"\bglpat-[A-Za-z0-9_-]{6,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{6,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    # Authorization headers and credential-looking assignments.
    re.compile(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9+/=_\-.]{8,}"),
    re.compile(
        r"(?i)\b([A-Za-z0-9_.-]*(?:token|secret|password|passwd|api[_-]?key|access[_-]?key)"
        r"[A-Za-z0-9_.-]*)(\s*[=:]\s*)(?!\*\*\*)[^\s,;'\"]+"
    ),
    # Credentials embedded in URLs.
    re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^/\s@]+@"),
)

REDACTED = "***"


class RepositoryUrlError(ValueError):
    """The URL is not acceptable. The message is safe to show to the user."""


class RepositoryCloneError(RuntimeError):
    """Cloning failed. The message is redacted and safe to show to the user."""


class RepositoryTooLargeError(RepositoryCloneError):
    """The clone exceeded the configured size cap."""


@dataclass(frozen=True)
class ParsedRepository:
    url: str
    host: str
    owner: str
    name: str

    @property
    def display_name(self) -> str:
        return f"{self.owner}/{self.name}"


@dataclass(frozen=True)
class ClonedRepository:
    url: str
    path: Path
    size_bytes: int
    from_fixture: bool = False


def redact_secrets(text: str, extra_secrets: Sequence[str] = ()) -> str:
    """Replace token-looking substrings (and any ``extra_secrets``) with ``***``."""
    redacted = text
    for secret in extra_secrets:
        if secret:
            redacted = redacted.replace(secret, REDACTED)
    for pattern in _SECRET_PATTERNS:
        if pattern.groups == 2:
            redacted = pattern.sub(
                lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}", redacted
            )
        elif pattern.groups == 1:
            redacted = pattern.sub(lambda match: f"{match.group(1)}{REDACTED}@", redacted)
        else:
            redacted = pattern.sub(REDACTED, redacted)
    return redacted


def _host_allowed(host: str, allowed_hosts: Sequence[str]) -> bool:
    for allowed in allowed_hosts:
        candidate = allowed.strip().lower()
        if not candidate:
            continue
        if host == candidate or host.endswith("." + candidate):
            return True
    return False


def _is_ip_address(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    return True


def validate_repository_url(url: str, allowed_hosts: Sequence[str]) -> ParsedRepository:
    """Parse and check ``url``; raise :class:`RepositoryUrlError` with a user-facing message."""
    candidate = (url or "").strip()
    if not candidate:
        raise RepositoryUrlError("Enter the repository URL.")
    allowed_display = ", ".join(allowed_hosts)
    if re.match(r"^[\w.-]+@[\w.-]+:", candidate):
        raise RepositoryUrlError(
            "SSH URLs are not supported. Use an https URL such as https://github.com/org/repo."
        )
    parts = urlsplit(candidate)
    scheme = parts.scheme.lower()
    if scheme != "https":
        if scheme in {"", "file", "ssh", "git", "git+ssh", "http"}:
            raise RepositoryUrlError(
                "Only https repository URLs are supported, for example https://github.com/org/repo."
            )
        raise RepositoryUrlError(f"Unsupported URL scheme '{parts.scheme}'. Use https.")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise RepositoryUrlError(
            "Remove credentials from the URL. Paste an access token in the token field instead."
        )
    host = (parts.hostname or "").lower().rstrip(".")
    if not host:
        raise RepositoryUrlError("The URL has no host name.")
    if host in BLOCKED_HOSTS or host.endswith(".localhost") or _is_ip_address(host):
        raise RepositoryUrlError(f"Host {host} is not allowed. Allowed: {allowed_display}")
    if parts.port not in (None, 443):
        raise RepositoryUrlError("Custom ports are not supported.")
    if not _host_allowed(host, allowed_hosts):
        raise RepositoryUrlError(f"Host {host} is not allowed. Allowed: {allowed_display}")
    segments = [segment for segment in parts.path.split("/") if segment]
    if len(segments) < 2:
        raise RepositoryUrlError(
            "The URL must point at a repository, for example https://github.com/org/repo."
        )
    if any(segment in {".", ".."} for segment in segments):
        raise RepositoryUrlError("The URL path is not valid.")
    name = segments[-1]
    name = name.removesuffix(".git")
    if not name:
        raise RepositoryUrlError("The URL must point at a repository.")
    owner = "/".join(segments[:-1])
    normalised = f"https://{host}/{owner}/{name}"
    return ParsedRepository(url=normalised, host=host, owner=owner, name=name)


def authorization_header(host: str, token: str) -> str:
    """The ``Authorization`` header value each forge expects for a personal access token."""
    lowered = host.lower()
    if lowered == "github.com" or lowered.endswith(".github.com"):
        encoded = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        return f"Basic {encoded}"
    if lowered == "gitlab.com" or lowered.endswith(".gitlab.com"):
        encoded = base64.b64encode(f"oauth2:{token}".encode()).decode()
        return f"Basic {encoded}"
    if lowered == "dev.azure.com" or lowered.endswith(".visualstudio.com"):
        encoded = base64.b64encode(f":{token}".encode()).decode()
        return f"Basic {encoded}"
    return f"Bearer {token}"


def clone_environment(host: str, token: str | None) -> dict[str, str]:
    """Environment for the git process: no prompts, no credential helpers, header-based auth."""
    environment: dict[str, str] = {
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "/bin/true",
        "GIT_SSH_COMMAND": "/bin/false",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_LFS_SKIP_SMUDGE": "1",
    }
    config: list[tuple[str, str]] = [("credential.helper", "")]
    if token:
        config.append(("http.extraheader", f"Authorization: {authorization_header(host, token)}"))
    environment["GIT_CONFIG_COUNT"] = str(len(config))
    for index, (key, value) in enumerate(config):
        environment[f"GIT_CONFIG_KEY_{index}"] = key
        environment[f"GIT_CONFIG_VALUE_{index}"] = value
    return environment


def directory_size(root: Path, *, limit_bytes: int | None = None) -> int:
    """Total size of regular files under ``root`` (``.git`` excluded); stops early past the cap."""
    total = 0
    for current, directories, files in os.walk(root):
        directories[:] = [name for name in directories if name != ".git"]
        for name in files:
            path = Path(current) / name
            if path.is_symlink():
                continue
            try:
                total += path.stat().st_size
            except OSError:
                continue
            if limit_bytes is not None and total > limit_bytes:
                return total
    return total


def _fixture_for(url: str) -> Path | None:
    # Fixture repositories are test data: served outside production regardless of the model.
    if get_settings().is_production:
        return None
    normalised = url.rstrip("/").removesuffix(".git")
    fixture = FIXTURE_REPOSITORIES.get(normalised)
    if fixture is None or not fixture.is_dir():
        return None
    return fixture


def _copy_fixture(fixture: Path, destination: Path) -> None:
    shutil.copytree(fixture, destination, dirs_exist_ok=True, symlinks=False)


def clone_repository(
    url: str,
    token: str | None,
    *,
    timeout_s: int,
    max_size_mb: int,
    destination: Path,
) -> ClonedRepository:
    """Shallow-clone ``url`` into ``destination`` (which must be empty or absent)."""
    parts = urlsplit(url)
    if parts.scheme.lower() != "https":
        raise RepositoryUrlError("Only https repository URLs can be cloned.")
    if "@" in parts.netloc:
        raise RepositoryUrlError("Remove credentials from the URL.")
    host = (parts.hostname or "").lower()
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    limit_bytes = max_size_mb * 1024 * 1024
    secrets = [token] if token else []

    fixture = _fixture_for(url)
    if fixture is not None:
        _copy_fixture(fixture, destination)
        size = directory_size(destination, limit_bytes=limit_bytes)
        if size > limit_bytes:
            raise RepositoryTooLargeError(f"Repository is larger than the {max_size_mb} MB limit.")
        return ClonedRepository(url=url, path=destination, size_bytes=size, from_fixture=True)

    git_command = Git(str(destination.parent))
    try:
        git_command.clone(
            "--depth",
            "1",
            "--single-branch",
            "--no-tags",
            "--no-recurse-submodules",
            "--",
            url,
            str(destination),
            env=clone_environment(host, token),
            kill_after_timeout=float(timeout_s),
        )
    except GitCommandError as error:
        detail = redact_secrets(str(error.stderr or error), secrets).strip()
        if "Timeout" in detail or "did not complete" in detail:
            raise RepositoryCloneError(
                f"Cloning timed out after {timeout_s} seconds. Try a smaller repository."
            ) from None
        if "Authentication failed" in detail or "could not read Username" in detail:
            raise RepositoryCloneError(
                "Authentication failed. Check the access token has read access."
            ) from None
        if "not found" in detail.lower() or "does not exist" in detail.lower():
            raise RepositoryCloneError(
                "Repository not found. Check the URL, or provide an access token for a "
                "private repository."
            ) from None
        raise RepositoryCloneError(f"Cloning failed: {_last_line(detail)}") from None
    except Exception as error:
        raise RepositoryCloneError(
            f"Cloning failed: {redact_secrets(str(error), secrets)}"
        ) from None

    size = directory_size(destination, limit_bytes=limit_bytes)
    if size > limit_bytes:
        raise RepositoryTooLargeError(f"Repository is larger than the {max_size_mb} MB limit.")
    return ClonedRepository(url=url, path=destination, size_bytes=size)


def _last_line(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "unknown error"
    last = lines[-1]
    return last.removeprefix("stderr:").strip().strip("'").removeprefix("fatal:").strip()


def remove_clone(path: Path) -> None:
    """Delete a clone directory, ignoring files git made read-only."""

    def on_error(_function: object, failed_path: str, _exc_info: object) -> None:
        try:
            os.chmod(failed_path, 0o700)
            if os.path.isdir(failed_path):
                os.rmdir(failed_path)
            else:
                os.unlink(failed_path)
        except OSError:
            pass

    shutil.rmtree(path, onexc=on_error)


@contextmanager
def temporary_clone(
    url: str,
    token: str | None,
    *,
    timeout_s: int,
    max_size_mb: int,
) -> Iterator[ClonedRepository]:
    """Clone into a fresh temporary directory and always remove it afterwards."""
    workspace = Path(tempfile.mkdtemp(prefix="intake-repo-"))
    try:
        yield clone_repository(
            url,
            token,
            timeout_s=timeout_s,
            max_size_mb=max_size_mb,
            destination=workspace / "repo",
        )
    finally:
        remove_clone(workspace)
