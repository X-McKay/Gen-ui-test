"""Keyword-based extraction used by ``MOCK_MODEL=1`` and as a deterministic fallback.

Rules are intentionally simple and transparent; the live path uses the model.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.inference.structured_extraction import ExtractedField


def _has(text: str, *patterns: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def extract_heuristically(text: str) -> list[ExtractedField]:
    from app.inference.structured_extraction import ExtractedField

    out: list[ExtractedField] = []

    def add(path: str, value: object, confidence: float, evidence: str | None = None) -> None:
        out.append(ExtractedField(path=path, value=value, confidence=confidence, evidence=evidence))

    ai = _has(
        text, r"\bLLM\b", r"language model", r"\bGPT", r"\bmodel\b", r"machine.learning", r"\bAI\b"
    )
    add("ai_system.uses_ai", bool(ai), 0.95 if ai else 0.6, "mentions a model" if ai else None)
    if _has(text, r"\bLLM\b", r"language model", r"\bGPT", r"Claude", r"Gemini", r"generative"):
        add("ai_system.gpai_model_used", True, 0.9, "uses a general-purpose model")
        add("ai_system.model_types", ["llm"], 0.85)
    if _has(text, r"\bAPI\b", r"OpenAI", r"Anthropic", r"Azure", r"Bedrock", r"third.party"):
        add("ai_system.model_source", "third_party_api", 0.85, "third-party API")
    elif _has(text, r"self.host", r"open.weight", r"Llama", r"Mistral", r"vLLM"):
        add("ai_system.model_source", "open_weights", 0.8)
    if _has(text, r"internal", r"our team", r"employees use", r"staff"):
        add("project.target_users", "internal", 0.85, "internal tool")
    elif _has(text, r"customers", r"public", r"members of the public"):
        add("project.target_users", "external", 0.7)
    if _has(text, r"production", r"live for"):
        add("project.lifecycle_stage", "production", 0.7)
    elif _has(text, r"pilot"):
        add("project.lifecycle_stage", "pilot", 0.8)
    elif _has(text, r"proof.of.concept", r"\bPoC\b", r"prototype"):
        add("project.lifecycle_stage", "poc", 0.8)

    hr = _has(
        text,
        r"\bCVs?\b",
        r"résumé",
        r"resume",
        r"candidate",
        r"recruit",
        r"hiring",
        r"job applica",
        r"screening",
    )
    no_personal = _has(
        text,
        r"no personal data",
        r"does not (process|handle|contain) personal",
        r"without personal data",
        r"anonymi[sz]ed",
    )
    personal = hr or _has(
        text,
        r"personal data",
        r"customer data",
        r"employee",
        r"patient",
        r"names",
        r"email address",
    )

    if no_personal:
        add("data.processes_personal_data", False, 0.9, "says no personal data")
    elif personal:
        add("data.processes_personal_data", True, 0.9, "mentions personal data")
    else:
        add("data.processes_personal_data", False, 0.6)

    if hr:
        add("use_case.domains", ["hr_employment"], 0.9, "candidate screening")
        add("data.data_subjects", ["employees"], 0.85, "candidates")
        add("data.pii_categories", ["employment", "contact", "free_text"], 0.8)
        add("use_case.affects_legal_or_significant_effects", True, 0.7, "screening affects hiring")
        add("ai_system.autonomy_level", "recommends", 0.75)
        add("data.special_category_data", [], 0.6)
    elif _has(text, r"credit", r"loan", r"insurance", r"underwrit"):
        add("use_case.domains", ["credit_insurance"], 0.85)
        add("use_case.affects_legal_or_significant_effects", True, 0.7)
    elif _has(text, r"student", r"exam", r"grading", r"school"):
        add("use_case.domains", ["education"], 0.85)
    elif _has(text, r"police", r"law enforcement", r"crime"):
        add("use_case.domains", ["law_enforcement"], 0.85)
    elif _has(text, r"medical", r"patient", r"diagnos", r"clinical"):
        add("use_case.domains", ["medical_or_safety_component"], 0.8)
    else:
        add("use_case.domains", ["other"], 0.9, "no regulated area mentioned")
        add("use_case.affects_legal_or_significant_effects", False, 0.85)
        add("ai_system.autonomy_level", "assistive", 0.8)

    if _has(text, r"\blogs?\b", r"log.search", r"observability", r"incident"):
        add("data.data_sources", ["logs"], 0.85)
    if _has(text, r"chat", r"assistant", r"conversation", r"ask questions"):
        add("use_case.interacts_directly_with_people", True, 0.85, "assistant")
    if _has(text, r"draft", r"summar", r"generate", r"write"):
        add("use_case.generates_synthetic_content", True, 0.85, "generates text")

    biometric = _has(
        text, r"facial recognition", r"face match", r"fingerprint", r"voice.?print", r"biometric"
    )
    add("data.biometric_identification", biometric, 0.9 if biometric else 0.85)
    emotion = _has(text, r"emotion", r"sentiment of (employees|students)", r"mood detection")
    add("use_case.emotion_recognition", emotion, 0.85)
    social = _has(text, r"social scor", r"trustworthiness score", r"citizen score")
    add("use_case.social_scoring", social, 0.85)
    if _has(text, r"fine.?tun", r"train(ed|ing) (a|our|the) model"):
        add("ai_system.fine_tuned_or_trained", True, 0.85)
        if personal and not no_personal:
            add("data.trains_on_personal_data", True, 0.7)
    if _has(
        text,
        r"human (review|in the loop|oversight)",
        r"reviewed by",
        r"recruiter (reads|reviews|decides)",
    ):
        add("ai_system.human_oversight", True, 0.85, "human review")
    return out
