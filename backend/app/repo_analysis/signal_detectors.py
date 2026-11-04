"""Pure detectors that turn a :class:`RepositoryInventory` into field signals.

Every detector is a function ``(inventory) -> list[Signal]``. Values use the exact enum
values of :mod:`app.intake.question_bank`. Confidence rules: direct SDK import 0.9,
dependency in a manifest 0.85, column or identifier name in source 0.8, keyword in a
README or doc 0.6 to 0.75. Snippets are the matching line, trimmed to 160 characters, with
token-looking secrets redacted.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass

from app.repo_analysis.clone_repository import redact_secrets
from app.repo_analysis.inventory import (
    DOCUMENT_EXTENSIONS,
    InventoryFile,
    RepositoryInventory,
)

SNIPPET_CHARS = 160

IMPORT_CONFIDENCE = 0.9
DEPENDENCY_CONFIDENCE = 0.85
IDENTIFIER_CONFIDENCE = 0.8
CONFIG_CONFIDENCE = 0.75
DOCUMENT_CONFIDENCE = 0.6
README_CONFIDENCE = 0.75


@dataclass(frozen=True)
class Signal:
    field: str
    value: object
    confidence: float
    evidence_path: str
    snippet: str
    detector: str


Detector = Callable[[RepositoryInventory], list[Signal]]


# --- helpers -------------------------------------------------------------------------------


def make_snippet(line: str) -> str:
    """One trimmed, redacted line of evidence."""
    collapsed = " ".join(line.split())
    redacted = redact_secrets(collapsed)
    if len(redacted) > SNIPPET_CHARS:
        return redacted[: SNIPPET_CHARS - 1].rstrip() + "…"
    return redacted


def is_document_path(path: str) -> bool:
    lowered = path.lower()
    name = lowered.rsplit("/", 1)[-1]
    if name.startswith("readme"):
        return True
    return any(lowered.endswith(extension) for extension in DOCUMENT_EXTENSIONS)


def iter_lines(entry: InventoryFile) -> Iterator[tuple[int, str]]:
    if entry.text is None:
        return
    for number, line in enumerate(entry.text.splitlines(), start=1):
        if line.strip():
            yield number, line


@dataclass
class _Hit:
    confidence: float
    path: str
    line: str

    def better_than(self, other: _Hit | None) -> bool:
        return other is None or self.confidence > other.confidence


class _Best:
    """Keeps the strongest hit per key; ties keep the first (deterministic order)."""

    def __init__(self) -> None:
        self._hits: dict[str, _Hit] = {}

    def offer(self, key: str, confidence: float, path: str, line: str) -> None:
        hit = _Hit(confidence, path, line)
        if hit.better_than(self._hits.get(key)):
            self._hits[key] = hit

    def items(self) -> list[tuple[str, _Hit]]:
        return list(self._hits.items())

    def get(self, key: str) -> _Hit | None:
        return self._hits.get(key)

    def __bool__(self) -> bool:
        return bool(self._hits)

    def strongest(self) -> _Hit | None:
        if not self._hits:
            return None
        return max(self._hits.values(), key=lambda hit: hit.confidence)


def _signal(
    field: str, value: object, hit: _Hit, detector: str, *, confidence: float | None = None
) -> Signal:
    return Signal(
        field=field,
        value=value,
        confidence=round(confidence if confidence is not None else hit.confidence, 2),
        evidence_path=hit.path,
        snippet=make_snippet(hit.line),
        detector=detector,
    )


_IMPORT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*from\s+([\w.]+)\s+import\b"),
    re.compile(r"^\s*import\s+([\w.]+(?:\s*,\s*[\w.]+)*)\s*(?:as\s+\w+\s*)?(?:#|;|$)"),
    re.compile(r"""require\(\s*["']([^"']+)["']\s*\)"""),
    re.compile(r"""^\s*import\s+.*?\bfrom\s+["']([^"']+)["']"""),
    re.compile(r"""^\s*import\s+["']([^"']+)["']"""),
    re.compile(r"""^\s*(?:import|using)\s+([A-Za-z][\w.]*)\s*;"""),
    re.compile(r"""^\s*"([\w./@-]+)"\s*$"""),  # Go import block lines
)


def imported_modules(line: str) -> list[str]:
    """Module or package specifiers imported on ``line`` (Python, JS/TS, Java/C#, Go)."""
    modules: list[str] = []
    for pattern in _IMPORT_PATTERNS:
        match = pattern.search(line)
        if match:
            modules.extend(part.strip() for part in match.group(1).split(",") if part.strip())
    return list(dict.fromkeys(modules))


_DEPENDENCY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"""^\s*["']?([A-Za-z0-9@][\w./@-]*)(?:\[[^\]]*\])?\s*(?:[=<>!~;\s"':,]|$)"""),
    re.compile(r"""^\s*["']([A-Za-z0-9@][\w./@-]*)(?:\[[^\]]*\])?["']\s*:"""),
)


_QUOTED_KEY = re.compile(r"""["']([A-Za-z0-9@][\w./@-]*)["']\s*:""")


def declared_dependencies(line: str) -> list[str]:
    """Package names a manifest line declares (requirements, pyproject, package.json)."""
    stripped = line.strip()
    if not stripped or stripped.startswith(("#", "//", "-")):
        return []
    names: list[str] = [key.lower() for key in _QUOTED_KEY.findall(stripped)]
    if stripped.startswith(("[", "{", "}")):
        return names
    for pattern in _DEPENDENCY_PATTERNS:
        match = pattern.match(stripped)
        if match:
            names.append(match.group(1).lower())
    return list(dict.fromkeys(names))


def _module_tokens(specifier: str) -> set[str]:
    return {token for token in re.split(r"[._/@:-]", specifier.lower()) if token}


# --- model SDKs ----------------------------------------------------------------------------


@dataclass(frozen=True)
class SdkRule:
    name: str
    dependency_names: tuple[str, ...]
    module_tokens: tuple[str, ...]
    provider: str | None
    model_source: str | None
    model_types: tuple[str, ...]
    general_purpose: bool
    source_confidence: float = 1.0  # multiplier for model_source confidence
    text_pattern: re.Pattern[str] | None = None


SDK_RULES: tuple[SdkRule, ...] = (
    SdkRule(
        "openai",
        ("openai", "langchain-openai", "langchain_openai"),
        ("openai",),
        "openai",
        "third_party_api",
        ("llm",),
        True,
    ),
    SdkRule(
        "anthropic",
        ("anthropic", "@anthropic-ai/sdk", "langchain-anthropic"),
        ("anthropic",),
        "anthropic",
        "third_party_api",
        ("llm",),
        True,
    ),
    SdkRule(
        "google",
        (
            "google-generativeai",
            "google-genai",
            "@google/generative-ai",
            "@google/genai",
            "langchain-google-genai",
            "google-cloud-aiplatform",
        ),
        ("generativeai", "genai", "vertexai"),
        "google",
        "third_party_api",
        ("llm",),
        True,
    ),
    SdkRule(
        "aws_bedrock",
        ("langchain-aws", "@aws-sdk/client-bedrock-runtime"),
        ("bedrockruntime",),
        "aws_bedrock",
        "third_party_api",
        ("llm",),
        True,
        text_pattern=re.compile(r"bedrock[-_]runtime|BedrockRuntime|bedrock\.amazonaws", re.I),
    ),
    SdkRule(
        "mistral",
        ("mistralai", "@mistralai/mistralai", "langchain-mistralai"),
        ("mistralai",),
        "mistral",
        "third_party_api",
        ("llm",),
        True,
    ),
    SdkRule(
        "cohere",
        ("cohere", "cohere-ai", "langchain-cohere"),
        ("cohere",),
        "other",
        "third_party_api",
        ("llm",),
        True,
    ),
    SdkRule(
        "litellm",
        ("litellm",),
        ("litellm",),
        None,
        "third_party_api",
        ("llm",),
        True,
        source_confidence=0.75,
    ),
    SdkRule(
        "langchain",
        ("langchain", "langchain-core", "langchain-community", "langgraph", "llama-index"),
        ("langchain", "langgraph", "llama_index", "llamaindex"),
        None,
        None,
        ("llm",),
        True,
    ),
    SdkRule(
        "vllm",
        ("vllm",),
        ("vllm",),
        "self_hosted",
        "open_weights",
        ("llm",),
        True,
    ),
    SdkRule(
        "transformers",
        ("transformers", "sentence-transformers", "@huggingface/transformers", "diffusers"),
        ("transformers", "diffusers"),
        "self_hosted",
        "open_weights",
        ("llm",),
        True,
        source_confidence=0.85,
    ),
    SdkRule(
        "torch",
        ("torch", "pytorch", "tensorflow", "keras", "jax", "flax"),
        ("torch", "tensorflow", "keras", "jax", "flax"),
        None,
        "in_house",
        (),
        False,
        source_confidence=0.65,
    ),
    SdkRule(
        "sklearn",
        ("scikit-learn", "sklearn", "xgboost", "lightgbm", "catboost", "statsmodels"),
        ("sklearn", "xgboost", "lightgbm", "catboost"),
        None,
        "in_house",
        ("classical_ml",),
        False,
        source_confidence=0.7,
    ),
)

_AZURE_OPENAI = re.compile(r"AzureOpenAI|azure_endpoint|openai\.azure\.com|azure-openai", re.I)


def detect_model_sdks(inventory: RepositoryInventory) -> list[Signal]:
    """Model SDK imports and dependencies → ``ai_system.*`` signals."""
    hits: dict[str, _Best] = {rule.name: _Best() for rule in SDK_RULES}
    azure = _Best()
    manifests = set(inventory.manifests)
    for entry in inventory.text_files():
        is_manifest = entry.path in manifests
        for _, line in iter_lines(entry):
            if _AZURE_OPENAI.search(line):
                azure.offer("azure", IMPORT_CONFIDENCE, entry.path, line)
            if is_manifest:
                names = declared_dependencies(line)
                for rule in SDK_RULES:
                    if any(name in rule.dependency_names for name in names):
                        hits[rule.name].offer("hit", DEPENDENCY_CONFIDENCE, entry.path, line)
                continue
            modules = imported_modules(line)
            tokens: set[str] = set()
            for module in modules:
                tokens |= _module_tokens(module)
            for rule in SDK_RULES:
                matched = bool(modules) and (
                    any(token in tokens for token in rule.module_tokens)
                    or any(module.lower() in rule.dependency_names for module in modules)
                )
                if not matched and rule.text_pattern is not None:
                    matched = bool(rule.text_pattern.search(line))
                if matched:
                    hits[rule.name].offer("hit", IMPORT_CONFIDENCE, entry.path, line)

    signals: list[Signal] = []
    for rule in SDK_RULES:
        hit = hits[rule.name].get("hit")
        if hit is None:
            continue
        detector = f"model_sdks:{rule.name}"
        signals.append(_signal("ai_system.uses_ai", True, hit, detector))
        provider = rule.provider
        if rule.name == "openai" and azure.get("azure") is not None:
            provider = "azure_openai"
        if provider:
            signals.append(_signal("ai_system.model_providers", [provider], hit, detector))
        if rule.model_source:
            signals.append(
                _signal(
                    "ai_system.model_source",
                    rule.model_source,
                    hit,
                    detector,
                    confidence=hit.confidence * rule.source_confidence,
                )
            )
        if rule.general_purpose:
            signals.append(_signal("ai_system.gpai_model_used", True, hit, detector))
        if rule.model_types:
            signals.append(_signal("ai_system.model_types", list(rule.model_types), hit, detector))
    return signals


def count_model_integrations(signals: Iterable[Signal]) -> int:
    return len({signal.detector for signal in signals if signal.detector.startswith("model_sdks:")})


# --- personal data -------------------------------------------------------------------------


@dataclass(frozen=True)
class PiiTerm:
    pattern: re.Pattern[str]
    categories: tuple[str, ...] = ()
    subjects: tuple[str, ...] = ()
    special: str | None = None


def _identifier(expression: str) -> re.Pattern[str]:
    """Match ``expression`` as a whole word or identifier part (``candidate_email`` counts)."""
    return re.compile(rf"(?<![a-z0-9]){expression}(?![a-z0-9])", re.I)


PII_TERMS: tuple[PiiTerm, ...] = (
    PiiTerm(_identifier(r"e[-_]?mail(?:[-_]?address)?"), categories=("contact",)),
    PiiTerm(
        _identifier(r"(?:tele)?phone(?:[-_]?number)?|mobile[-_]?(?:number|phone)"), ("contact",)
    ),
    PiiTerm(
        _identifier(r"full[-_]?name|first[-_]?name|last[-_]?name|surname|given[-_]?name"),
        ("contact",),
    ),
    PiiTerm(
        _identifier(
            r"(?:home|postal|street|mailing|residential|billing|shipping)[-_ ]?address"
            r"|address[-_]?line[-_]?\d?|post[-_]?code|zip[-_]?code"
        ),
        ("contact", "location"),
    ),
    PiiTerm(
        _identifier(
            r"ssn|social[-_ ]?security(?:[-_ ]?number)?|national[-_ ]?id|national[-_ ]?insurance"
            r"|passport(?:[-_ ]?number)?|tax[-_ ]?id|driver'?s?[-_ ]?licen[cs]e"
        ),
        ("identifiers",),
    ),
    PiiTerm(_identifier(r"date[-_ ]?of[-_ ]?birth|birth[-_ ]?date|dob|birthday"), ("identifiers",)),
    PiiTerm(
        _identifier(
            r"salary(?:[-_]?expectation)?|compensation|iban|bank[-_ ]?account|credit[-_ ]?card"
            r"|card[-_ ]?number|payslip|payroll"
        ),
        ("financial",),
    ),
    PiiTerm(
        _identifier(
            r"cvs?|resumes?|r[ée]sum[ée]s?|curriculum[-_ ]?vitae|candidates?|applicants?"
            r"|work[-_ ]?history|employment[-_ ]?history|job[-_ ]?applications?"
            r"|recruit(?:er|ing|ment)s?"
        ),
        ("employment",),
        ("employees",),
    ),
    PiiTerm(
        _identifier(r"employees?|staff[-_ ]?id|personnel|workforce"),
        ("employment",),
        ("employees",),
    ),
    PiiTerm(
        _identifier(r"customers?|account[-_ ]?holders?|subscribers?|shoppers?"), (), ("customers",)
    ),
    PiiTerm(
        _identifier(
            r"students?|pupils?|child(?:ren)?|minors?|parent(?:al)?[-_ ]?consent|guardian"
            r"|under[-_ ]?1[38]"
        ),
        (),
        ("minors",),
    ),
    PiiTerm(
        _identifier(
            r"patients?|medical[-_ ]?records?|diagnos[ie]s|health[-_ ]?(?:condition|record|data)"
            r"|disabilit(?:y|ies)|medications?|prescriptions?"
        ),
        (),
        (),
        "health",
    ),
    PiiTerm(
        _identifier(r"ethnicit(?:y|ies)|ethnic[-_ ]?(?:origin|group)|racial"), (), (), "ethnicity"
    ),
    PiiTerm(
        _identifier(r"religions?|religious[-_ ]?(?:belief|affiliation)s?"), (), (), "religious"
    ),
    PiiTerm(
        _identifier(r"political[-_ ]?(?:opinion|affiliation|party|view)s?"), (), (), "political"
    ),
    PiiTerm(_identifier(r"sexual[-_ ]?orientation"), (), (), "sexual_orientation"),
    PiiTerm(
        _identifier(
            r"criminal[-_ ]?(?:record|history|conviction)s?|convictions?|offen[cs]e[-_ ]?records?"
        ),
        (),
        (),
        "criminal",
    ),
    PiiTerm(
        _identifier(
            r"biometrics?|fingerprints?|face[-_ ]?(?:id|embedding|encoding|match|recognition)"
            r"|voice[-_ ]?prints?|iris[-_ ]?scan|retina[-_ ]?scan"
        ),
        (),
        (),
        "biometric",
    ),
    PiiTerm(
        _identifier(
            r"geo[-_ ]?location|latitude|longitude|gps[-_ ]?(?:coordinates?|position)"
            r"|home[-_ ]?location"
        ),
        ("location",),
    ),
    PiiTerm(
        _identifier(
            r"clickstream|browsing[-_ ]?history|tracking[-_ ]?id|purchase[-_ ]?history"
            r"|usage[-_ ]?patterns?"
        ),
        ("behavioural",),
    ),
    PiiTerm(
        _identifier(
            r"cv[-_ ]?text|raw[-_ ]?text|transcripts?|free[-_ ]?text|chat[-_ ]?history"
            r"|message[-_ ]?body"
        ),
        ("free_text",),
    ),
)  # fmt: skip

_PII_ANY = re.compile("|".join(term.pattern.pattern for term in PII_TERMS), re.I)

NO_PERSONAL_DATA = re.compile(
    r"no personal data|does not (?:process|store|handle|contain|collect) (?:any )?personal"
    r"|without (?:any )?personal data|handles no personal data|anonymi[sz]ed|pseudonymi[sz]ed"
    r"|not personal data",
    re.I,
)


def detect_pii_indicators(inventory: RepositoryInventory) -> list[Signal]:
    """Personal-data field and column names → ``data.*`` signals."""
    personal = _Best()
    categories = _Best()
    subjects = _Best()
    specials = _Best()
    negative = _Best()
    config_files = {*inventory.config_files, *inventory.iac_files, *inventory.ci_files}
    for entry in inventory.text_files():
        document = is_document_path(entry.path)
        if document:
            confidence = DOCUMENT_CONFIDENCE
        elif entry.path in config_files:
            confidence = CONFIG_CONFIDENCE
        else:
            confidence = IDENTIFIER_CONFIDENCE
        for _, line in iter_lines(entry):
            if document and NO_PERSONAL_DATA.search(line):
                negative.offer("negative", 0.7, entry.path, line)
            if not _PII_ANY.search(line):
                continue
            for term in PII_TERMS:
                if not term.pattern.search(line):
                    continue
                personal.offer("personal", confidence, entry.path, line)
                for category in term.categories:
                    categories.offer(category, confidence, entry.path, line)
                for subject in term.subjects:
                    subjects.offer(subject, confidence, entry.path, line)
                if term.special:
                    specials.offer(term.special, confidence, entry.path, line)

    signals: list[Signal] = []
    detector = "pii_indicators"
    personal_hit = personal.get("personal")
    negative_hit = negative.get("negative")
    if personal_hit is not None and (
        negative_hit is None or personal_hit.confidence > negative_hit.confidence
    ):
        signals.append(_signal("data.processes_personal_data", True, personal_hit, detector))
    elif negative_hit is not None:
        signals.append(_signal("data.processes_personal_data", False, negative_hit, detector))
    if personal_hit is None or (
        negative_hit is not None and negative_hit.confidence >= personal_hit.confidence
    ):
        return signals
    for category, hit in categories.items():
        signals.append(_signal("data.pii_categories", [category], hit, detector))
    for subject, hit in subjects.items():
        signals.append(_signal("data.data_subjects", [subject], hit, detector))
    for special, hit in specials.items():
        signals.append(_signal("data.special_category_data", [special], hit, detector))
    return signals


# --- biometrics ----------------------------------------------------------------------------

BIOMETRIC_LIBRARIES: tuple[str, ...] = (
    "face_recognition",
    "face-recognition",
    "deepface",
    "dlib",
    "insightface",
    "facenet",
    "facenet-pytorch",
    "retinaface",
    "mtcnn",
    "resemblyzer",
    "speechbrain",
    "pyannote",
    "pyannote.audio",
    "fingerprint",
)
_BIOMETRIC_TEXT = re.compile(
    r"haarcascade_frontalface|CascadeClassifier\([^)]*face|face_cascade|FaceDetector"
    r"|face[-_ ]?recognition|face[-_ ]?match(?:ing)?|voice[-_ ]?print"
    r"|speaker[-_ ]?(?:verification|identification)"
    r"|fingerprint[-_ ]?(?:scan|match|reader)|iris[-_ ]?recognition",
    re.I,
)


def detect_biometric_indicators(inventory: RepositoryInventory) -> list[Signal]:
    """Face, voice and fingerprint libraries → biometric identification signals."""
    best = _Best()
    manifests = set(inventory.manifests)
    for entry in inventory.text_files():
        is_manifest = entry.path in manifests
        document = is_document_path(entry.path)
        for _, line in iter_lines(entry):
            if is_manifest:
                if any(name in BIOMETRIC_LIBRARIES for name in declared_dependencies(line)):
                    best.offer("biometric", DEPENDENCY_CONFIDENCE, entry.path, line)
                continue
            modules = imported_modules(line)
            tokens: set[str] = set()
            for module in modules:
                tokens |= _module_tokens(module)
            if modules and (
                any(module.lower() in BIOMETRIC_LIBRARIES for module in modules)
                or tokens & {"deepface", "dlib", "insightface", "facenet", "retinaface", "mtcnn"}
                or "face_recognition" in {module.lower() for module in modules}
            ):
                best.offer("biometric", IMPORT_CONFIDENCE, entry.path, line)
            elif _BIOMETRIC_TEXT.search(line):
                confidence = DOCUMENT_CONFIDENCE if document else IDENTIFIER_CONFIDENCE
                best.offer("biometric", confidence, entry.path, line)
    hit = best.get("biometric")
    if hit is None:
        return []
    detector = "biometric_indicators"
    confidence = min(hit.confidence, 0.85)
    return [
        _signal("data.biometric_identification", True, hit, detector, confidence=confidence),
        _signal("data.special_category_data", ["biometric"], hit, detector, confidence=confidence),
        _signal("data.processes_personal_data", True, hit, detector, confidence=confidence),
        _signal("ai_system.uses_ai", True, hit, detector, confidence=confidence),
        _signal("ai_system.model_types", ["vision"], hit, detector, confidence=0.7),
    ]


# --- data sources --------------------------------------------------------------------------

DATABASE_LIBRARIES: frozenset[str] = frozenset(
    {
        "psycopg",
        "psycopg2",
        "psycopg2-binary",
        "asyncpg",
        "sqlalchemy",
        "sqlmodel",
        "pymongo",
        "motor",
        "mysql",
        "mysqlclient",
        "pymysql",
        "mysql-connector-python",
        "sqlite3",
        "aiosqlite",
        "redis",
        "cassandra",
        "snowflake",
        "snowflake-connector-python",
        "pg",
        "mysql2",
        "mongoose",
        "prisma",
        "@prisma/client",
        "knex",
        "sequelize",
        "typeorm",
        "django",
        "peewee",
        "tortoise",
        "pyodbc",
        "oracledb",
        "cx_oracle",
    }
)
_DATABASE_TEXT = re.compile(
    r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|mssql|oracle|jdbc:\w+)://"
    r"|\bDATABASE_URL\b|\bdjango\.db\b|\bcreate_engine\(|\bclient\(\s*['\"]s3['\"]"
    r"|\bresource\(\s*['\"]s3['\"]|\bs3fs\b|\bS3Client\b|\bbigquery\b|\bsnowflake\.connector\b",
    re.I,
)
LOG_LIBRARIES: frozenset[str] = frozenset(
    {
        "elasticsearch",
        "elasticsearch-dsl",
        "opensearch-py",
        "opensearchpy",
        "@elastic/elasticsearch",
        "splunk-sdk",
        "splunklib",
        "datadog",
        "datadog-api-client",
        "loki",
        "python-logging-loki",
        "logstash",
        "grafana-loki",
    }
)
_LOG_TEXT = re.compile(
    r"\belasticsearch\b|\bopensearch\b|\bloki\b|\bsplunk\b|\bdatadog\b|\bcloudwatch[-_ ]?logs?\b"
    r"|\blogstash\b|\bkibana\b|\bfluentd\b|\blog[-_ ]?(?:search|index|lines|records|analytics)\b"
    r"|\bapplication logs\b|\bsystem logs\b",
    re.I,
)
_UPLOAD_TEXT = re.compile(
    r"\bUploadFile\b|\brequest\.files\b|\bmulter\b|\bFileField\b|\bFileUpload\b"
    r"|multipart/form-data|\bupload(?:ed)?[-_ ]?(?:file|cv|document|handler)s?\b"
    r"|@\w+\.(?:post|route)\(\s*['\"][^'\"]*upload",
    re.I,
)
_THIRD_PARTY_TEXT = re.compile(
    r"\b(?:requests|httpx|axios|fetch|urllib\.request|aiohttp)\b[^\n]*https?://([\w.-]+)", re.I
)
_PUBLIC_WEB_LIBRARIES: frozenset[str] = frozenset(
    {"scrapy", "beautifulsoup4", "bs4", "selenium", "newspaper3k", "trafilatura", "crawlee"}
)
_MODEL_API_HOSTS = (
    "openai.com",
    "anthropic.com",
    "googleapis.com",
    "amazonaws.com",
    "mistral.ai",
    "cohere.ai",
    "cohere.com",
    "huggingface.co",
    "localhost",
    "127.0.0.1",
    "example.com",
)


def detect_data_source_clients(inventory: RepositoryInventory) -> list[Signal]:
    """Database, storage, logging, upload and HTTP clients → ``data.data_sources``."""
    best = _Best()
    manifests = set(inventory.manifests)
    for entry in inventory.text_files():
        is_manifest = entry.path in manifests
        document = is_document_path(entry.path)
        code_confidence = DOCUMENT_CONFIDENCE if document else IDENTIFIER_CONFIDENCE
        for _, line in iter_lines(entry):
            if is_manifest:
                names = set(declared_dependencies(line))
                if names & DATABASE_LIBRARIES:
                    best.offer("internal_db", DEPENDENCY_CONFIDENCE, entry.path, line)
                if names & LOG_LIBRARIES:
                    best.offer("logs", DEPENDENCY_CONFIDENCE, entry.path, line)
                if names & _PUBLIC_WEB_LIBRARIES:
                    best.offer("public_web", 0.7, entry.path, line)
                continue
            modules = {module.lower() for module in imported_modules(line)}
            roots = {module.split(".")[0].split("/")[0] for module in modules}
            if modules & DATABASE_LIBRARIES or roots & DATABASE_LIBRARIES:
                best.offer("internal_db", IMPORT_CONFIDENCE, entry.path, line)
            elif _DATABASE_TEXT.search(line):
                best.offer("internal_db", code_confidence, entry.path, line)
            if modules & LOG_LIBRARIES or roots & LOG_LIBRARIES:
                best.offer("logs", IMPORT_CONFIDENCE, entry.path, line)
            elif _LOG_TEXT.search(line):
                best.offer("logs", code_confidence, entry.path, line)
            if roots & _PUBLIC_WEB_LIBRARIES:
                best.offer("public_web", 0.75, entry.path, line)
            if not document and _UPLOAD_TEXT.search(line):
                best.offer("user_upload", 0.7, entry.path, line)
            elif document and re.search(r"\bupload(?:s|ed)?\b", line, re.I):
                best.offer("user_upload", DOCUMENT_CONFIDENCE, entry.path, line)
            third_party = _THIRD_PARTY_TEXT.search(line)
            if third_party and not document:
                host = third_party.group(1).lower()
                if not any(host.endswith(known) for known in _MODEL_API_HOSTS):
                    best.offer("third_party", 0.6, entry.path, line)
    detector = "data_source_clients"
    return [_signal("data.data_sources", [source], hit, detector) for source, hit in best.items()]


# --- deployment ----------------------------------------------------------------------------

_REGION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("uk", re.compile(r"\beu-west-2\b|\buk[-_ ]?(?:south|west)\b|\beurope-west2\b", re.I)),
    (
        "eu",
        re.compile(
            r"\beu-(?:west|central|north|south)-\d\b|\beurope-(?:west|north|central)\d?\b"
            r"|\b(?:west|north|germany|france|sweden|switzerland|norway|italy|poland)(?:west|north|central)?europe\b"
            r"|\beu-central\b",
            re.I,
        ),
    ),
    (
        "us",
        re.compile(
            r"\bus-(?:east|west|central)-?\d\b|\b(?:east|west|central|south|north)us\d?\b"
            r"|\bus-central\d\b|\bus-gov-\w+\b",
            re.I,
        ),
    ),
    (
        "apac",
        re.compile(
            r"\bap-(?:southeast|northeast|south|east)-\d\b|\basia-(?:east|southeast|northeast|south)\d\b"
            r"|\b(?:australia|japan|korea|india|southeast|east)asia\b|\bau-syd\b",
            re.I,
        ),
    ),
)  # fmt: skip


def detect_deployment_signals(inventory: RepositoryInventory) -> list[Signal]:
    """Dockerfiles, IaC and CI → lifecycle stage (≤ 0.7) and deployment regions."""
    signals: list[Signal] = []
    detector = "deployment_signals"
    stage_hit: _Hit | None = None
    stage: str | None = None
    if inventory.iac_files:
        path = inventory.iac_files[0]
        entry = inventory.file(path)
        first_line = _first_line(entry) if entry else path
        stage_hit = _Hit(0.7, path, first_line)
        stage = "production"
    elif inventory.has_dockerfile and inventory.ci_files:
        path = inventory.ci_files[0]
        entry = inventory.file(path)
        stage_hit = _Hit(0.6, path, _first_line(entry) if entry else path)
        stage = "pilot"
    elif inventory.has_dockerfile:
        path = inventory.dockerfiles[0]
        entry = inventory.file(path)
        stage_hit = _Hit(0.5, path, _first_line(entry) if entry else path)
        stage = "pilot"
    if stage_hit is not None and stage is not None:
        signals.append(_signal("project.lifecycle_stage", stage, stage_hit, detector))

    regions = _Best()
    candidates = [*inventory.iac_files, *inventory.ci_files, *inventory.config_files]
    for path in candidates:
        entry = inventory.file(path)
        if entry is None or entry.text is None:
            continue
        for _, line in iter_lines(entry):
            for region, pattern in _REGION_PATTERNS:
                if pattern.search(line):
                    regions.offer(region, 0.7, entry.path, line)
                    break
    for region, hit in regions.items():
        signals.append(_signal("project.deployment_regions", [region], hit, detector))
    return signals


def _first_line(entry: InventoryFile | None) -> str:
    if entry is None or entry.text is None:
        return ""
    for _, line in iter_lines(entry):
        return line
    return ""


# --- domain keywords -----------------------------------------------------------------------

DOMAIN_KEYWORDS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "hr_employment",
        re.compile(
            r"\brecruit(?:er|ing|ment)s?\b|\bcandidates?\b|\bCVs?\b|\br[ée]sum[ée]s?\b|\bhiring\b"
            r"|\bapplicants?\b|\bjob (?:applications?|postings?|seekers?)\b"
            r"|\bemployee (?:performance|monitoring|evaluation)\b"
            r"|\bpromotion decisions?\b|\bworkforce\b|\bHR\b",
            re.I,
        ),
    ),
    (
        "credit_insurance",
        re.compile(
            r"\bcredit(?:worthiness| scor(?:e|ing)| risk| decision)s?\b"
            r"|\bloan (?:application|approval)s?\b"
            r"|\binsurance\b|\bunderwrit(?:e|ing|er)s?\b|\bpremiums?\b",
            re.I,
        ),
    ),
    (
        "education",
        re.compile(
            r"\bstudents?\b|\bexam(?:ination)?s?\b|\bgrading\b|\bschools?\b|\buniversit(?:y|ies)\b"
            r"|\badmissions?\b|\bproctoring\b|\blearners?\b",
            re.I,
        ),
    ),
    (
        "law_enforcement",
        re.compile(
            r"\bpolice\b|\blaw enforcement\b|\bcrim(?:e|inal)s?\b|\boffenders?\b"
            r"|\bpredictive policing\b"
            r"|\bsuspects?\b|\bpolygraph\b",
            re.I,
        ),
    ),
    (
        "migration_border",
        re.compile(
            r"\bvisas?\b|\basylum\b|\bborder (?:control|security)\b|\bimmigration\b|\bmigrants?\b"
            r"|\bresidence permits?\b",
            re.I,
        ),
    ),
    (
        "justice_democratic",
        re.compile(
            r"\bcourts?\b|\bjudicial\b|\bjudges?\b|\belections?\b|\bvoters?\b"
            r"|\blegal (?:rulings?|judgments?)\b"
            r"|\bsentencing\b",
            re.I,
        ),
    ),
    (
        "critical_infrastructure",
        re.compile(
            r"\bpower grid\b|\belectricity (?:grid|network|supply)\b|\bwater (?:supply|treatment)\b"
            r"|\bgas (?:network|supply)\b|\btraffic (?:control|management)\b|\brailway signalling\b"
            r"|\bcritical infrastructure\b|\bsafety component\b",
            re.I,
        ),
    ),
    (
        "medical_or_safety_component",
        re.compile(
            r"\bpatients?\b|\bclinic(?:al|ians?)?\b|\bdiagnos(?:is|es|tic)\b"
            r"|\bmedical (?:device|imaging|records?)\b"
            r"|\bhospitals?\b|\btriage\b|\bradiolog(?:y|ist)\b|\btherap(?:y|ist)\b",
            re.I,
        ),
    ),
    (
        "essential_services",
        re.compile(
            r"\bsocial (?:benefits?|welfare|housing|security benefits?)\b|\bwelfare\b"
            r"|\bemergency (?:services?|calls?|dispatch)\b|\bpublic assistance\b"
            r"|\bbenefit (?:claims?|eligibility)\b|\bunemployment benefits?\b",
            re.I,
        ),
    ),
    (
        "financial_markets",
        re.compile(
            r"\balgorithmic trading\b|\bmarket[- ]making\b|\border book\b"
            r"|\btrading (?:desk|venue|strategy|strategies)\b"
            r"|\b(?:equity|equities|securities|derivatives?|futures|fx)"
            r" (?:trading|orders?|venues?)\b",
            re.I,
        ),
    ),
)  # fmt: skip

_CHAT_LIBRARIES: frozenset[str] = frozenset(
    {
        "chainlit",
        "streamlit",
        "gradio",
        "slack-bolt",
        "slack_bolt",
        "slack-sdk",
        "discord.py",
        "discord",
        "python-telegram-bot",
        "telegram",
        "botbuilder-core",
        "rasa",
        "twilio",
        "@slack/bolt",
        "discord.js",
    }
)
_CHAT_TEXT = re.compile(
    r"\bchat(?:bot|[-_ ]?interface|[-_ ]?window|[-_ ]?ui)s?\b|\bconversational\b"
    r"|\bvirtual assistant\b|\bask(?:s)? (?:questions?|the assistant)\b|\bin plain english\b"
    r"|\bnatural language (?:questions?|interface)\b"
    r"|\bwebsocket\b|@\w+\.(?:post|route|websocket)\(\s*['\"][^'\"]*(?:chat|message|ask)",
    re.I,
)
_GENERATION_TEXT = re.compile(
    r"chat\.completions\.create|messages\.create\(|generate_content\(|litellm\.(?:a?completion)\("
    r"|\.generate\(|ChatCompletion\.create|responses\.create\(|\binvoke_model\(",
)
_GENERATION_DOCUMENT_TEXT = re.compile(
    r"\b(?:drafts?|writes?|generates?|summari[sz]es?|composes?) (?:a |an |the )?"
    r"(?:short |structured |brief )?"
    r"(?:summar(?:y|ies)|explanation|answer|response|reply|draft|text|report|email)s?\b",
    re.I,
)


def detect_domain_keywords(inventory: RepositoryInventory) -> list[Signal]:
    """README and docs keywords → ``use_case.domains`` and interaction hints."""
    signals: list[Signal] = []
    detector = "domain_keywords"
    documents: list[tuple[str, str, float]] = []
    if inventory.readme_path:
        documents.append((inventory.readme_path, inventory.readme_text, README_CONFIDENCE))
    documents.extend((doc.path, doc.text, DOCUMENT_CONFIDENCE) for doc in inventory.documents)

    domains = _Best()
    for path, text, confidence in documents:
        for line in text.splitlines():
            if not line.strip():
                continue
            for domain, pattern in DOMAIN_KEYWORDS:
                if pattern.search(line):
                    domains.offer(domain, confidence, path, line)
    if domains:
        for domain, hit in domains.items():
            signals.append(_signal("use_case.domains", [domain], hit, detector))
    elif inventory.readme_path:
        readme_hit = _Hit(
            DOCUMENT_CONFIDENCE, inventory.readme_path, _first_text_line(inventory.readme_text)
        )
        signals.append(_signal("use_case.domains", ["other"], readme_hit, detector))

    interaction = _Best()
    generation = _Best()
    manifests = set(inventory.manifests)
    for entry in inventory.text_files():
        document = is_document_path(entry.path)
        is_manifest = entry.path in manifests
        for _, line in iter_lines(entry):
            if is_manifest:
                if set(declared_dependencies(line)) & _CHAT_LIBRARIES:
                    interaction.offer("chat", 0.75, entry.path, line)
                continue
            if document:
                if _CHAT_TEXT.search(line):
                    interaction.offer("chat", DOCUMENT_CONFIDENCE, entry.path, line)
                if _GENERATION_DOCUMENT_TEXT.search(line):
                    generation.offer("generation", DOCUMENT_CONFIDENCE, entry.path, line)
                continue
            modules = {module.lower().split(".")[0] for module in imported_modules(line)}
            if modules & _CHAT_LIBRARIES or _CHAT_TEXT.search(line):
                interaction.offer("chat", 0.7, entry.path, line)
            if _GENERATION_TEXT.search(line):
                generation.offer("generation", 0.7, entry.path, line)
    chat_hit = interaction.strongest()
    if chat_hit is not None:
        signals.append(_signal("use_case.interacts_directly_with_people", True, chat_hit, detector))
    generation_hit = generation.strongest()
    if generation_hit is not None:
        signals.append(
            _signal("use_case.generates_synthetic_content", True, generation_hit, detector)
        )
    return signals


def _first_text_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped
    return ""


# --- retention -----------------------------------------------------------------------------

_RETENTION_CONTEXT = re.compile(
    r"\b(?:delet\w*|retain\w*|retention|purg\w*|kept|keep|expire\w*|removed|erased|stored for)\b",
    re.I,
)
_RETENTION_DURATION = re.compile(r"\b(\d+)\s*(day|week|month|year)s?\b", re.I)
_NOT_STORED = re.compile(
    r"\b(?:not|never) (?:stored|retained|persisted|kept)\b|\bno (?:data )?retention\b"
    r"|\bstateless\b",
    re.I,
)


def detect_retention_policy(inventory: RepositoryInventory) -> list[Signal]:
    """Retention statements in docs → ``data.retention_policy``."""
    best = _Best()
    documents: list[tuple[str, str]] = []
    if inventory.readme_path:
        documents.append((inventory.readme_path, inventory.readme_text))
    documents.extend((doc.path, doc.text) for doc in inventory.documents)
    for path, text in documents:
        for line in text.splitlines():
            if not line.strip():
                continue
            if _NOT_STORED.search(line) and re.search(
                r"\b(?:data|records?|cvs?|logs?|prompts?)\b", line, re.I
            ):
                best.offer("not_stored", 0.65, path, line)
                continue
            if not _RETENTION_CONTEXT.search(line):
                continue
            duration = _RETENTION_DURATION.search(line)
            if not duration:
                continue
            amount = int(duration.group(1))
            unit = duration.group(2).lower()
            days = amount * {"day": 1, "week": 7, "month": 30, "year": 365}[unit]
            if days <= 30:
                value = "under_30_days"
            elif days < 365:
                value = "under_1_year"
            else:
                value = "over_1_year"
            best.offer(value, 0.7, path, line)
    hit_items = best.items()
    if not hit_items:
        return []
    value, hit = max(hit_items, key=lambda item: item[1].confidence)
    return [_signal("data.retention_policy", value, hit, "retention_policy")]


# --- registry ------------------------------------------------------------------------------

ALL_DETECTORS: tuple[Detector, ...] = (
    detect_model_sdks,
    detect_pii_indicators,
    detect_biometric_indicators,
    detect_data_source_clients,
    detect_deployment_signals,
    detect_domain_keywords,
    detect_retention_policy,
)


def run_all_detectors(inventory: RepositoryInventory) -> list[Signal]:
    signals: list[Signal] = []
    for detector in ALL_DETECTORS:
        signals.extend(detector(inventory))
    return signals
