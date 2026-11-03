"""Walk a cloned repository and collect what the detectors need.

Pure and synchronous: the only I/O is reading files. Nothing in the repository is executed
or imported. Binary files are skipped by extension, by size and by a NUL-byte sniff; text
is decoded as UTF-8 with errors ignored and capped at :data:`MAX_FILE_BYTES` per file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

MAX_FILE_BYTES = 200_000
README_EXCERPT_CHARS = 4_000
DOCUMENT_EXCERPT_CHARS = 2_000
MAX_DOCUMENTS = 25
DEFAULT_TEXT_BUDGET_BYTES = 48 * 1024 * 1024

SKIPPED_DIRECTORIES: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        "vendor",
        "dist",
        "build",
        "out",
        "target",
        ".next",
        ".nuxt",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".idea",
        ".terraform",
        "site-packages",
        "bower_components",
        ".cache",
        "coverage",
    }
)

BINARY_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".svgz", ".tiff", ".psd",
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt",
        ".zip", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".tar", ".jar", ".war",
        ".whl", ".egg", ".so", ".dll", ".dylib", ".exe", ".bin", ".o", ".a", ".lib",
        ".pyc", ".pyo", ".class", ".wasm",
        ".woff", ".woff2", ".ttf", ".otf", ".eot",
        ".mp3", ".mp4", ".wav", ".ogg", ".flac", ".mov", ".avi", ".mkv", ".webm",
        ".parquet", ".arrow", ".feather", ".npy", ".npz", ".pkl", ".pickle", ".joblib",
        ".pt", ".pth", ".onnx", ".safetensors", ".h5", ".hdf5", ".ckpt", ".tflite", ".pb",
        ".sqlite", ".db", ".lock",
    }
)  # fmt: skip

LANGUAGE_BY_EXTENSION: dict[str, str] = {
    ".py": "Python",
    ".pyi": "Python",
    ".ipynb": "Jupyter",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".scala": "Scala",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".fs": "F#",
    ".swift": "Swift",
    ".m": "Objective-C",
    ".c": "C",
    ".h": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".hpp": "C++",
    ".r": "R",
    ".jl": "Julia",
    ".sh": "Shell",
    ".bash": "Shell",
    ".ps1": "PowerShell",
    ".sql": "SQL",
    ".tf": "Terraform",
    ".hcl": "Terraform",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".toml": "TOML",
    ".md": "Markdown",
    ".rst": "reStructuredText",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "CSS",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".proto": "Protobuf",
    ".dockerfile": "Dockerfile",
}

MANIFEST_NAMES: frozenset[str] = frozenset(
    {
        "requirements.txt",
        "requirements-dev.txt",
        "requirements.in",
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "pipfile",
        "poetry.lock",
        "uv.lock",
        "environment.yml",
        "environment.yaml",
        "conda.yml",
        "package.json",
        "go.mod",
        "cargo.toml",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "gemfile",
        "composer.json",
        "mix.exs",
        "pubspec.yaml",
    }
)

CONFIG_NAMES: frozenset[str] = frozenset(
    {
        ".env.example",
        ".env.sample",
        ".env.template",
        "settings.py",
        "config.py",
        "config.yaml",
        "config.yml",
        "config.json",
        "config.toml",
        "app.yaml",
        "app.json",
        "serverless.yml",
        "serverless.yaml",
        "docker-compose.yml",
        "docker-compose.yaml",
        "compose.yml",
        "compose.yaml",
        "procfile",
        "makefile",
    }
)
CONFIG_EXTENSIONS: frozenset[str] = frozenset({".ini", ".cfg", ".conf", ".properties", ".env"})

CI_MARKERS: tuple[str, ...] = (
    ".github/workflows/",
    ".gitlab-ci.yml",
    "azure-pipelines.yml",
    "azure-pipelines.yaml",
    ".circleci/config.yml",
    "jenkinsfile",
    "bitbucket-pipelines.yml",
    ".travis.yml",
    "cloudbuild.yaml",
    ".drone.yml",
)

DOCUMENT_EXTENSIONS: frozenset[str] = frozenset({".md", ".rst", ".txt", ".adoc"})


@dataclass(frozen=True)
class InventoryFile:
    """One file in the repository. ``text`` is ``None`` for binaries and oversized files."""

    path: str
    size_bytes: int
    extension: str
    text: str | None = None

    @property
    def name(self) -> str:
        return PurePosixPath(self.path).name

    @property
    def is_text(self) -> bool:
        return self.text is not None


@dataclass(frozen=True)
class DocumentExcerpt:
    path: str
    text: str


@dataclass
class RepositoryInventory:
    root: Path
    file_count: int = 0
    scanned_file_count: int = 0
    skipped_binary_count: int = 0
    truncated: bool = False
    total_size_bytes: int = 0
    languages: dict[str, int] = field(default_factory=dict)
    extensions: dict[str, int] = field(default_factory=dict)
    manifests: list[str] = field(default_factory=list)
    has_dockerfile: bool = False
    dockerfiles: list[str] = field(default_factory=list)
    iac_files: list[str] = field(default_factory=list)
    ci_files: list[str] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)
    readme_path: str | None = None
    readme_text: str = ""
    documents: list[DocumentExcerpt] = field(default_factory=list)
    files: list[InventoryFile] = field(default_factory=list)

    def text_files(self) -> list[InventoryFile]:
        return [entry for entry in self.files if entry.text is not None]

    def file(self, path: str) -> InventoryFile | None:
        for entry in self.files:
            if entry.path == path:
                return entry
        return None

    def manifest_files(self) -> list[InventoryFile]:
        return [entry for entry in self.files if entry.path in self.manifests and entry.is_text]

    @property
    def primary_language(self) -> str | None:
        if not self.languages:
            return None
        return max(self.languages.items(), key=lambda item: item[1])[0]


def _is_dockerfile(name: str) -> bool:
    lowered = name.lower()
    return (
        lowered == "dockerfile"
        or lowered.startswith("dockerfile.")
        or lowered.endswith(".dockerfile")
    )


def _is_infrastructure(path: str, name: str, text: str | None) -> bool:
    lowered = path.lower()
    lowered_name = name.lower()
    if lowered_name.endswith((".tf", ".tf.json", ".hcl", ".bicep")):
        return True
    if lowered_name in {"chart.yaml", "values.yaml", "serverless.yml", "serverless.yaml"}:
        return True
    if lowered_name.startswith("pulumi.") or "cloudformation" in lowered:
        return True
    deployment_parts = ("/k8s/", "/kubernetes/", "/helm/", "/manifests/", "/deploy/")
    if any(part in lowered for part in deployment_parts) and lowered_name.endswith(
        (".yaml", ".yml", ".json")
    ):
        return True
    if lowered_name.endswith((".yaml", ".yml")) and text:
        head = text[:4000]
        if "apiVersion:" in head and "kind:" in head:
            return True
    return False


def _is_ci(path: str) -> bool:
    lowered = path.lower()
    return any(marker in lowered or lowered.endswith(marker) for marker in CI_MARKERS)


def _is_config(path: str, name: str) -> bool:
    lowered_name = name.lower()
    if lowered_name in CONFIG_NAMES or lowered_name.startswith(".env."):
        return True
    extension = PurePosixPath(lowered_name).suffix
    return extension in CONFIG_EXTENSIONS


def _looks_binary(sample: bytes) -> bool:
    return b"\x00" in sample


def _read_text(path: Path, size_bytes: int, max_file_bytes: int) -> str | None:
    if size_bytes > max_file_bytes:
        return None
    try:
        with path.open("rb") as handle:
            data = handle.read(max_file_bytes)
    except OSError:
        return None
    if _looks_binary(data[:4096]):
        return None
    return data.decode("utf-8", errors="ignore")


def _is_readme(relative_path: str) -> bool:
    lowered = relative_path.lower()
    return lowered in {"readme.md", "readme.rst", "readme.txt", "readme"} or (
        lowered.startswith("readme.") and "/" not in lowered
    )


def _is_document(relative_path: str, extension: str) -> bool:
    lowered = relative_path.lower()
    if extension not in DOCUMENT_EXTENSIONS or lowered.rsplit("/", 1)[-1] in MANIFEST_NAMES:
        return False
    return lowered.startswith(("docs/", "doc/", "documentation/")) or "/" not in lowered


def build_inventory(
    root: Path,
    *,
    max_files: int,
    max_file_bytes: int = MAX_FILE_BYTES,
    text_budget_bytes: int = DEFAULT_TEXT_BUDGET_BYTES,
) -> RepositoryInventory:
    """Walk ``root`` and build a :class:`RepositoryInventory`. Deterministic order."""
    root = Path(root)
    inventory = RepositoryInventory(root=root)
    text_budget = text_budget_bytes
    readme_candidates: list[tuple[str, str]] = []

    for current, directories, names in os.walk(root, followlinks=False):
        directories[:] = sorted(
            name
            for name in directories
            if name not in SKIPPED_DIRECTORIES and not (Path(current) / name).is_symlink()
        )
        for name in sorted(names):
            if inventory.file_count >= max_files:
                inventory.truncated = True
                break
            absolute = Path(current) / name
            if absolute.is_symlink():
                continue
            try:
                stat = absolute.stat()
            except OSError:
                continue
            if not absolute.is_file():
                continue
            relative = absolute.relative_to(root).as_posix()
            extension = PurePosixPath(name).suffix.lower()
            if _is_dockerfile(name):
                extension = ".dockerfile"
            inventory.file_count += 1
            inventory.total_size_bytes += stat.st_size
            inventory.extensions[extension] = inventory.extensions.get(extension, 0) + 1
            language = LANGUAGE_BY_EXTENSION.get(extension)
            if language:
                inventory.languages[language] = inventory.languages.get(language, 0) + 1

            text: str | None = None
            if extension in BINARY_EXTENSIONS:
                inventory.skipped_binary_count += 1
            elif text_budget > 0:
                text = _read_text(absolute, stat.st_size, min(max_file_bytes, text_budget))
                if text is None:
                    inventory.skipped_binary_count += 1
                else:
                    text_budget -= len(text)
                    inventory.scanned_file_count += 1
            entry = InventoryFile(
                path=relative, size_bytes=stat.st_size, extension=extension, text=text
            )
            inventory.files.append(entry)
            _classify(inventory, entry, readme_candidates)
        if inventory.truncated:
            break

    if readme_candidates:
        readme_candidates.sort(key=lambda item: (item[0].count("/"), len(item[0])))
        inventory.readme_path, readme_text = readme_candidates[0]
        inventory.readme_text = readme_text[:README_EXCERPT_CHARS]
    inventory.documents = inventory.documents[:MAX_DOCUMENTS]
    return inventory


def _classify(
    inventory: RepositoryInventory,
    entry: InventoryFile,
    readme_candidates: list[tuple[str, str]],
) -> None:
    name = entry.name
    lowered_name = name.lower()
    if lowered_name in MANIFEST_NAMES:
        inventory.manifests.append(entry.path)
    if _is_dockerfile(name):
        inventory.has_dockerfile = True
        inventory.dockerfiles.append(entry.path)
    if _is_infrastructure(entry.path, name, entry.text):
        inventory.iac_files.append(entry.path)
    if _is_ci(entry.path):
        inventory.ci_files.append(entry.path)
    if _is_config(entry.path, name):
        inventory.config_files.append(entry.path)
    if entry.text is None:
        return
    if _is_readme(entry.path):
        readme_candidates.append((entry.path, entry.text))
    elif _is_document(entry.path, entry.extension) and len(inventory.documents) < MAX_DOCUMENTS:
        inventory.documents.append(
            DocumentExcerpt(path=entry.path, text=entry.text[:DOCUMENT_EXCERPT_CHARS])
        )
