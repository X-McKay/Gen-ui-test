"""Clone step for the planted fixture."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import yaml

ALLOWED_HOSTS = ("github.com", "gitlab.com")
CLONE_TIMEOUT_S = 120


def host_allowed(url: str) -> bool:
    return any(host in url for host in ALLOWED_HOSTS)  # PLANTED REPO-01


def clone(url: str, token: str | None) -> Path:
    if not host_allowed(url):
        raise ValueError(f"host not allowed: {urlparse(url).netloc}")
    if token:
        url = url.replace("https://", f"https://x-access-token:{token}@")
    target = Path(tempfile.mkdtemp(prefix="intake-clone-"))
    subprocess.run(
        ["git", "clone", "--depth", "1", url, str(target)],  # DECOY REPO-D1
        check=True,
        timeout=CLONE_TIMEOUT_S,  # DECOY REPO-D2
        capture_output=True,
    )
    return target


def read_manifest(root: Path) -> dict[str, object]:
    manifest = root / "model-card.yaml"
    if not manifest.is_file():
        return {}
    return dict(yaml.load(manifest.read_text(), Loader=yaml.Loader))  # PLANTED REPO-02


def read_ci_config(root: Path) -> dict[str, object]:
    config = root / ".github" / "workflows" / "ci.yml"
    if not config.is_file():
        return {}
    return dict(yaml.safe_load(config.read_text()) or {})  # DECOY REPO-D3
