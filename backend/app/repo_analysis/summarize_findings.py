"""Turn detector signals plus one structured-extraction pass into repository findings.

Detector signals win for the fields they cover (highest confidence per field, list values
merged). The extraction pass over an evidence digest fills the remaining fields with the
README as evidence. Every value is validated against the intake record; invalid ones are
dropped. Repository contents never reach the logs: only counts are logged.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict

from pydantic import BaseModel, ConfigDict, Field

from app.inference.structured_extraction import ExtractedField, extract_fields
from app.intake.question_bank import QUESTIONS_BY_FIELD, display_value
from app.intake.record_service import coerce_value
from app.intake.schema import new_record
from app.repo_analysis.inventory import RepositoryInventory
from app.repo_analysis.signal_detectors import Signal, make_snippet

logger = logging.getLogger(__name__)

DIGEST_README_CHARS = 3_000
DIGEST_DOCUMENT_CHARS = 800
DIGEST_MAX_DOCUMENTS = 6
DIGEST_MAX_SIGNALS = 40
MINIMUM_EXTRACTED_CONFIDENCE = 0.5


class RepositoryFinding(BaseModel):
    """One inferred field with the evidence that supports it."""

    model_config = ConfigDict(extra="forbid")

    field: str
    label: str
    value: object
    display_value: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_path: str
    snippet: str
    source: str

    @classmethod
    def build(
        cls,
        *,
        field: str,
        value: object,
        confidence: float,
        evidence_path: str,
        snippet: str,
    ) -> RepositoryFinding:
        spec = QUESTIONS_BY_FIELD.get(field)
        return cls(
            field=field,
            label=spec.label if spec else field,
            value=value,
            display_value=display_value(field, value),
            confidence=round(max(0.0, min(1.0, confidence)), 2),
            evidence_path=evidence_path,
            snippet=snippet,
            source=f"repo:{evidence_path}",
        )


def _is_list_field(field: str) -> bool:
    spec = QUESTIONS_BY_FIELD.get(field)
    return spec is not None and spec.control == "multi"


def _validated_value(field: str, value: object) -> object | None:
    """``value`` coerced for ``field`` if the record accepts it, else ``None``."""
    coerced = coerce_value(field, value)
    if coerced is None:
        return None
    if isinstance(coerced, list) and not coerced:
        return None
    scratch = new_record("validation")
    try:
        scratch.get_field(field)
        scratch.set_field(field, coerced, source="inferred", confidence=0.5, confirmed=False)
    except (ValueError, KeyError, AttributeError):
        return None
    return coerced


def merge_signals(signals: list[Signal]) -> list[RepositoryFinding]:
    """One finding per field: strongest signal wins, list values are merged in order."""
    by_field: dict[str, list[Signal]] = defaultdict(list)
    for signal in signals:
        by_field[signal.field].append(signal)
    findings: list[RepositoryFinding] = []
    for field, group in by_field.items():
        strongest = max(group, key=lambda signal: signal.confidence)
        value: object = strongest.value
        if _is_list_field(field):
            merged: list[object] = []
            for signal in sorted(group, key=lambda signal: -signal.confidence):
                items = signal.value if isinstance(signal.value, list) else [signal.value]
                for item in items:
                    if item not in merged:
                        merged.append(item)
            value = merged
        validated = _validated_value(field, value)
        if validated is None:
            continue
        findings.append(
            RepositoryFinding.build(
                field=field,
                value=validated,
                confidence=strongest.confidence,
                evidence_path=strongest.evidence_path,
                snippet=strongest.snippet,
            )
        )
    return findings


def build_evidence_digest(inventory: RepositoryInventory, signals: list[Signal]) -> str:
    """Compact text the extraction model reads: README, docs, manifests and top signals."""
    parts: list[str] = []
    if inventory.readme_text:
        parts.append(
            f"## README ({inventory.readme_path})\n{inventory.readme_text[:DIGEST_README_CHARS]}"
        )
    for document in inventory.documents[:DIGEST_MAX_DOCUMENTS]:
        parts.append(f"## {document.path}\n{document.text[:DIGEST_DOCUMENT_CHARS]}")
    manifest_lines: list[str] = []
    for entry in inventory.manifest_files()[:4]:
        lines = [line.strip() for line in (entry.text or "").splitlines() if line.strip()]
        manifest_lines.append(f"{entry.path}: " + ", ".join(lines[:40]))
    if manifest_lines:
        parts.append("## Dependencies\n" + "\n".join(manifest_lines))
    languages = ", ".join(f"{name} ({count})" for name, count in inventory.languages.items())
    facts = [
        f"languages: {languages}",
        f"files: {inventory.file_count}",
        f"dockerfile: {'yes' if inventory.has_dockerfile else 'no'}",
        f"infrastructure as code: {', '.join(inventory.iac_files[:5]) or 'none'}",
        f"continuous integration: {', '.join(inventory.ci_files[:5]) or 'none'}",
    ]
    parts.append("## Repository facts\n" + "\n".join(facts))
    top_signals = sorted(signals, key=lambda signal: -signal.confidence)[:DIGEST_MAX_SIGNALS]
    if top_signals:
        lines = [
            f"- {signal.field} = {signal.value!r} ({signal.confidence:.2f}) "
            f"from {signal.evidence_path}: {signal.snippet}"
            for signal in top_signals
        ]
        parts.append("## Code signals\n" + "\n".join(lines))
    return "\n\n".join(parts)


def _first_readme_line(inventory: RepositoryInventory) -> str:
    for line in inventory.readme_text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return make_snippet(stripped)
    return ""


def _evidence_for(extracted: ExtractedField, inventory: RepositoryInventory) -> tuple[str, str]:
    """``(evidence_path, snippet)`` for an extracted field: the doc that mentions it."""
    fallback_path = inventory.readme_path or "README.md"
    evidence = (extracted.evidence or "").strip()
    documents: list[tuple[str, str]] = []
    if inventory.readme_path:
        documents.append((inventory.readme_path, inventory.readme_text))
    documents.extend((document.path, document.text) for document in inventory.documents)
    if not evidence:
        return fallback_path, _first_readme_line(inventory)
    lowered = evidence.lower()
    for path, text in documents:
        for line in text.splitlines():
            if lowered in line.lower():
                return path, make_snippet(line)
    # The extractor may paraphrase ("internal tool"): pick the doc line sharing most words.
    words = set(re.findall(r"[a-z]{4,}", lowered))
    best_score = 0
    best: tuple[str, str] | None = None
    for path, text in documents:
        for line in text.splitlines():
            line_words = set(re.findall(r"[a-z]{4,}", line.lower()))
            score = len(words & line_words)
            if score > best_score:
                best_score = score
                best = (path, make_snippet(line))
    if best is not None:
        return best
    return fallback_path, make_snippet(evidence)


def findings_from_extraction(
    extracted: list[ExtractedField],
    inventory: RepositoryInventory,
    covered_fields: set[str],
) -> list[RepositoryFinding]:
    findings: list[RepositoryFinding] = []
    seen: set[str] = set()
    for item in extracted:
        if item.path in covered_fields or item.path in seen:
            continue
        if item.confidence < MINIMUM_EXTRACTED_CONFIDENCE:
            continue
        validated = _validated_value(item.path, item.value)
        if validated is None:
            continue
        evidence_path, snippet = _evidence_for(item, inventory)
        seen.add(item.path)
        findings.append(
            RepositoryFinding.build(
                field=item.path,
                value=validated,
                confidence=item.confidence,
                evidence_path=evidence_path,
                snippet=snippet,
            )
        )
    return findings


async def summarize_repository(
    inventory: RepositoryInventory, signals: list[Signal]
) -> list[RepositoryFinding]:
    """Detector findings first, then extraction over the digest for the remaining fields."""
    detector_findings = merge_signals(signals)
    covered = {finding.field for finding in detector_findings}
    digest = build_evidence_digest(inventory, signals)
    try:
        extracted = await extract_fields(digest, context="repository")
    except Exception:
        logger.warning("repo_analysis.extraction_failed", exc_info=True)
        extracted = []
    extracted_findings = findings_from_extraction(extracted, inventory, covered)
    findings = detector_findings + extracted_findings
    logger.info(
        "repo_analysis.summarised",
        extra={
            "detector_findings": len(detector_findings),
            "extracted_findings": len(extracted_findings),
            "signals": len(signals),
        },
    )
    return findings
