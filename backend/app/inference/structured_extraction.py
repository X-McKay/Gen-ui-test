"""Structured extraction of intake facts from free text, via tool calling.

The tool schema is generated from the question bank (which is generated from the Pydantic
model), so both providers run the same contract. No provider-specific JSON mode is used.
``MOCK_MODEL=1`` routes to the keyword extractor instead.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.inference.model_factory import completion_kwargs
from app.intake.heuristic_extractor import extract_heuristically
from app.intake.question_bank import QUESTION_BANK, QuestionSpec
from app.settings import get_settings

logger = logging.getLogger(__name__)

EXTRACTION_TOOL_NAME = "record_intake_facts"


class ExtractedField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    value: object
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str | None = Field(default=None, description="Short quote that supports the value")


# Guidance for fields the model tends to get wrong. Keeps the legal meaning tight.
FIELD_HINTS: dict[str, str] = {
    "ai_system.uses_ai": (
        "True for any machine-learning or statistical model as well as generative models: "
        "logistic regression, scorecards, gradient boosting, forecasting, classifiers and LLM "
        "APIs all count ('a logistic-regression scorecard ... no LLM is used' is still true). "
        "False only when the text says the logic is fixed rules with no model at all."
    ),
    "ai_system.gpai_model_used": (
        "True whenever an LLM or other foundation model is used; false for a classical model "
        "(regression, boosting, forecasting) when no LLM is mentioned."
    ),
    "ai_system.model_source": (
        "third_party_api = a hosted provider API (OpenAI, Anthropic, Azure, Bedrock, Gemini, a "
        "model vendor); open_weights = a published model you run yourself ('self-hosted', "
        "'open-weights', Llama, Mistral, Qwen are always open_weights, never in_house); "
        "in_house = a model your own team trained from scratch."
    ),
    "ai_system.autonomy_level": (
        "Always record it when the text says who acts on the output. assistive = drafts or "
        "informs, a person does the work; recommends = suggests, scores or ranks, a person "
        "decides each case; decides = acts or decides without a person reviewing that case "
        "(automatic blocking, approval, gate opening), even if someone can override afterwards."
    ),
    "ai_system.human_oversight": "True when a person reviews or can override outputs.",
    "project.target_users": (
        "Who operates or uses the system, not who it is about. internal = staff only; "
        "external = customers, clients or partners who log in or are known; public = anyone, "
        "including visitors and applicants without an account."
    ),
    "project.lifecycle_stage": "pilot and production are stated; otherwise leave it out.",
    "data.processes_personal_data": (
        "CVs, customer records, employee data, names, contact details, account data, device or "
        "browser identifiers and IP addresses all count."
    ),
    "data.special_category_data": (
        "Always record it when personal data is processed. List every category the data "
        "contains: health records, symptoms, radiology or patient data = health; faces, voices, "
        "fingerprints or facial expressions = biometric; also ethnicity, political, religious, "
        "sexual_orientation, criminal. Record [] when an ordinary business tool clearly has none."
    ),
    "data.biometric_identification": (
        "True only when biometric data (face, fingerprint, voice) is used to identify or verify "
        "who a person is (face match at a gate, voice login). Webcam emotion or attention "
        "detection is NOT identification: record false there; a device fingerprint is not "
        "biometric."
    ),
    "data.data_subjects": (
        "Always record it when personal data is processed. Candidates and staff are employees; "
        "patients and customers are customers; applicants, visitors and residents are public; "
        "include minors whenever the people are under 18 (pupils aged 12 to 16, schoolchildren)."
    ),
    "use_case.domains": (
        "Record a regulated domain only when the system's output makes or supports that kind "
        "of decision about a person; the company's industry does not matter. hr_employment = "
        "recruiting, evaluating, promoting, assigning or monitoring workers (an expense tool "
        "using HR tables is other); credit_insurance = creditworthiness, credit scoring, loan "
        "or insurance decisions (a bank's support chatbot or balance assistant is other); "
        "essential_services = eligibility for public benefits, housing, utilities (a council FAQ "
        "bot or a shop's refunds are other); critical_infrastructure = safety components that "
        "operate energy, water or transport systems (building turnstiles and login pages are "
        "other); medical_or_safety_component = diagnosis, triage or a safety function. When in "
        "doubt, record ['other']."
    ),
    "use_case.affects_legal_or_significant_effects": (
        "True when outputs influence hiring, credit, insurance, access to benefits, education, "
        "legal status or similar decisions about a person, even with a human in the loop. "
        "Answering questions, small customer-service outcomes (refunds, order status), building "
        "access for staff and drafting content are not significant effects."
    ),
    "use_case.interacts_directly_with_people": (
        "True when people converse with the system itself (chat, voice, assistant). A form, an "
        "upload or an internal report is not direct interaction."
    ),
    "use_case.generates_synthetic_content": (
        "True when it produces text, images, audio or video shown to people: summaries of logs "
        "or claims, drafted messages, answers, explanations, posts. A score, a ranking, a flag "
        "or a yes/no suggestion alone is not content."
    ),
    "use_case.emotion_recognition": (
        "True only when the system infers emotions, mood, attention or intentions of people."
    ),
    "use_case.social_scoring": (
        "Only true for scoring people's trustworthiness or social behaviour across unrelated "
        "contexts leading to detrimental treatment (EU AI Act Art. 5(1)(c)). A job-fit, credit "
        "or quality score for one stated purpose is NOT social scoring: record false."
    ),
    "use_case.manipulative_or_subliminal": "True only for deliberate deception or subliminal cues.",
    "controls.in_place": (
        "Include a control only when the text explicitly says it is in place today; being an "
        "internal tool or having a known user group is NOT a control. guardrails = prompt-"
        "injection or content filters on the model's inputs/outputs (a CAPTCHA or a login is "
        "not a guardrail); access_controls = only when login, SSO, roles, authentication or "
        "mutual TLS are stated ('internal use', 'recruiters use it' do not count); "
        "pii_minimisation = redaction or minimisation before the model; abuse_monitoring = rate "
        "limits, misuse monitoring; pre_release_evaluation = evaluation, red-teaming or ongoing "
        "checks of the model; vendor_data_protections = provider may not train on the data; "
        "incident_response = kill switch, rollback; user_disclosure = people are told it is AI. "
        "A plan, intention, roadmap item or recommendation is not a control. Use 'none' only "
        "when the text says there are no controls; otherwise leave the field out."
    ),
}

GATE_FIELDS = (
    "ai_system.uses_ai",
    "data.processes_personal_data",
    "use_case.domains",
    "use_case.affects_legal_or_significant_effects",
    "project.target_users",
    "ai_system.gpai_model_used",
    "ai_system.autonomy_level",
    "data.data_subjects",
    "data.special_category_data",
    "data.biometric_identification",
    "use_case.emotion_recognition",
    "use_case.social_scoring",
)


def _value_schema(spec: QuestionSpec) -> dict[str, Any]:
    if spec.control == "yes_no":
        return {"type": "boolean"}
    if spec.control == "choice":
        return {"type": "string", "enum": [option.value for option in spec.options]}
    if spec.control == "multi":
        return {
            "type": "array",
            "items": {"type": "string", "enum": [o.value for o in spec.options]},
        }
    return {"type": "string", "maxLength": 500}


def extraction_tool_schema() -> dict[str, Any]:
    """OpenAI-style tool definition with one property per askable field."""
    properties: dict[str, Any] = {}
    for spec in QUESTION_BANK:
        hint = FIELD_HINTS.get(spec.field)
        properties[spec.field.replace(".", "__")] = {
            "type": "object",
            "description": f"{spec.prompt} {hint}" if hint else spec.prompt,
            "properties": {
                "value": _value_schema(spec),
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": "How sure you are, 0 to 1. Use ≥ 0.8 only when the text says so.",  # noqa: E501
                },
                "evidence": {"type": "string", "description": "Short quote from the text"},
            },
            "required": ["value", "confidence"],
        }
    return {
        "type": "function",
        "function": {
            "name": EXTRACTION_TOOL_NAME,
            "description": (
                "Record every intake fact that the text supports. Leave out fields the text "
                "says nothing about. A clear description of an unrelated system is evidence "
                "that sensitive practices are absent: record those as false with confidence ≥ 0.8."
            ),
            "parameters": {
                "type": "object",
                "properties": properties,
                "additionalProperties": False,
            },
        },
    }


SYSTEM_PROMPT = (
    "You extract facts for an AI governance intake. Read the project description and call "
    f"{EXTRACTION_TOOL_NAME} exactly once with every field the text supports. Always try to "
    "fill these gate fields first, because they decide the classification: "
    + ", ".join(GATE_FIELDS)
    + ". When a description of an ordinary business tool clearly implies that a sensitive "
    "practice is absent (biometrics, emotion recognition, social scoring, manipulation), "
    "record it as false with confidence 0.85. Controls (guardrails, access control, monitoring, "
    "evaluation, vendor terms, rollback, disclosure) count only when the text says they exist "
    "today; a plan or intention is not a control, so leave that field out. Never invent "
    "details; use confidence below 0.8 for guesses. Do not reply with prose."
)


def parse_tool_arguments(arguments: str | dict[str, Any]) -> list[ExtractedField]:
    data: dict[str, Any] = json.loads(arguments) if isinstance(arguments, str) else arguments
    specs = {spec.field.replace(".", "__"): spec for spec in QUESTION_BANK}
    fields: list[ExtractedField] = []
    for key, raw in data.items():
        spec = specs.get(key)
        if spec is None or not isinstance(raw, dict) or raw.get("value") is None:
            continue
        try:
            confidence = float(raw.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        evidence = raw.get("evidence")
        fields.append(
            ExtractedField(
                path=spec.field,
                value=raw["value"],
                confidence=max(0.0, min(1.0, confidence)),
                evidence=str(evidence)[:200] if evidence else None,
            )
        )
    return [field for field in fields if not _is_junk(field.value)]


class ExtractionResult(BaseModel):
    """Extracted fields plus the cost of getting them (for evals and metrics; no text)."""

    model_config = ConfigDict(extra="forbid")

    fields: list[ExtractedField]
    latency_ms: int = 0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


JUNK_VALUES: frozenset[str] = frozenset({"", "undefined", "null", "none", "n/a"})


def _is_junk(value: object) -> bool:
    """A placeholder the model emitted instead of leaving the field out."""
    return isinstance(value, str) and value.strip().lower() in JUNK_VALUES


# Values that raise the assessed risk. The model must quote the text for them; a value whose
# evidence is not in the text is an inference, so it is capped below the confidence at which
# the product would accept it without asking, or dropped where a wrong value is costly.
RISK_RAISING_BOOLEANS: frozenset[str] = frozenset(
    {
        "data.biometric_identification",
        "data.trains_on_personal_data",
        "data.cross_border_transfer",
        "use_case.affects_legal_or_significant_effects",
        "use_case.emotion_recognition",
        "use_case.social_scoring",
        "use_case.remote_biometric_id_public_spaces",
        "use_case.manipulative_or_subliminal",
        "use_case.untargeted_facial_scraping",
    }
)
DROP_WHEN_UNGROUNDED: frozenset[str] = frozenset({"controls.in_place", "use_case.domains"})
UNGROUNDED_CONFIDENCE = 0.6
_SPACES = re.compile(r"\s+")


def _normalise_text(text: str) -> str:
    return _SPACES.sub(" ", text).strip().lower()


def evidence_in_text(evidence: str | None, text: str) -> bool:
    """True when every fragment of the quote (split on ellipses) appears in the text."""
    if not evidence:
        return False
    haystack = _normalise_text(text)
    fragments = [_normalise_text(part) for part in re.split(r"\.\.\.|…", evidence) if part.strip()]
    return bool(fragments) and all(len(f) >= 4 and f in haystack for f in fragments)


# A control counts only when the description names it. Evidence quotes for the list are too
# coarse to check per element, so each element needs one of its words somewhere in the text.
CONTROL_KEYWORDS: dict[str, tuple[str, ...]] = {
    "guardrails": ("guardrail", "filter", "prompt-injection", "prompt injection", "moderation"),
    "access_controls": (
        "login",
        "log in",
        "logged",
        "sso",
        "authenticat",
        "authoris",
        "authoriz",
        "role-based",
        "permission",
        "mutual tls",
        "mtls",
        "restricted to",
        "access control",
        "can read",
        "only the",
    ),
    "pii_minimisation": ("redact", "minimis", "minimiz", "pseudonym", "anonymi", "mask", "strip"),
    "abuse_monitoring": (
        "rate limit",
        "rate-limit",
        "throttl",
        "monitor",
        "abuse",
        "misuse",
        "quota",
    ),
    "pre_release_evaluation": ("evaluat", "red team", "red-team", "tested", "benchmark", "eval"),
    "vendor_data_protections": (
        "train on",
        "training on",
        "trained on",
        "processing agreement",
        "dpa",
        "retention",
        "retained",
    ),
    "incident_response": (
        "kill switch",
        "rollback",
        "roll back",
        "incident",
        "runbook",
        "feature flag",
    ),
    "user_disclosure": (
        "disclos",
        "banner",
        "told",
        "labelled",
        "labeled",
        "an ai",
        "ai-generated",
        "notice",
        "says it is",
    ),
}


def supported_controls(value: object, text: str) -> list[str]:
    """The listed controls whose vocabulary appears in the text (``none`` always passes)."""
    if not isinstance(value, list):
        return []
    haystack = _normalise_text(text)
    kept: list[str] = []
    for item in value:
        name = str(item)
        words = CONTROL_KEYWORDS.get(name)
        if words is None or any(word in haystack for word in words):
            kept.append(name)
    return kept


def _raises_risk(field: ExtractedField) -> bool:
    if field.path in RISK_RAISING_BOOLEANS:
        return field.value is True
    if field.path == "use_case.domains" and isinstance(field.value, list):
        return any(str(v) != "other" for v in field.value)
    if field.path == "controls.in_place" and isinstance(field.value, list):
        return any(str(v) != "none" for v in field.value)
    if field.path == "data.special_category_data":
        return isinstance(field.value, list) and bool(field.value)
    return False


def ground_fields(fields: list[ExtractedField], text: str) -> list[ExtractedField]:
    """Keep stated facts as they are; demote or drop risk-raising inferences."""
    grounded: list[ExtractedField] = []
    for field in fields:
        if field.path == "controls.in_place" and isinstance(field.value, list):
            kept = supported_controls(field.value, text)
            if len(kept) < len(field.value):
                logger.debug("inference.extraction.dropped_controls", extra={"field": field.path})
            if not kept:
                continue
            field = field.model_copy(update={"value": kept})
        if not _raises_risk(field) or evidence_in_text(field.evidence, text):
            grounded.append(field)
        elif field.path in DROP_WHEN_UNGROUNDED:
            logger.debug("inference.extraction.dropped_ungrounded", extra={"field": field.path})
        else:
            grounded.append(
                field.model_copy(
                    update={"confidence": min(field.confidence, UNGROUNDED_CONFIDENCE)}
                )
            )
    return grounded


async def extract_fields(text: str, *, context: str | None = None) -> list[ExtractedField]:
    """Extract intake facts from ``text``. ``context`` names the source (description, repo)."""
    return (await extract_fields_detailed(text, context=context)).fields


async def extract_fields_detailed(text: str, *, context: str | None = None) -> ExtractionResult:
    """Like :func:`extract_fields`, also returning latency and token usage."""
    settings = get_settings()
    if settings.mock_model:
        started = time.perf_counter()
        heuristic = extract_heuristically(text)
        return ExtractionResult(
            fields=heuristic, latency_ms=int((time.perf_counter() - started) * 1000)
        )
    import litellm

    user_content = text if not context else f"Source: {context}\n\n{text}"
    started = time.perf_counter()
    response = await litellm.acompletion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        tools=[extraction_tool_schema()],
        tool_choice={"type": "function", "function": {"name": EXTRACTION_TOOL_NAME}},
        temperature=0,
        max_tokens=6000,
        # Extraction needs no chain of thought; vLLM/Qwen honour this and other servers drop it.
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        **completion_kwargs(settings),
    )
    message = response.choices[0].message
    usage = getattr(response, "usage", None)
    latency_ms = int((time.perf_counter() - started) * 1000)
    prompt_tokens = getattr(usage, "prompt_tokens", None)
    completion_tokens = getattr(usage, "completion_tokens", None)
    logger.info(
        "inference.extraction",
        extra={
            "latency_ms": latency_ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "tool_calls": [call.function.name for call in (message.tool_calls or [])],
        },
    )
    fields: list[ExtractedField] = []
    for call in message.tool_calls or []:
        if call.function.name != EXTRACTION_TOOL_NAME:
            continue
        try:
            fields.extend(parse_tool_arguments(call.function.arguments))
        except json.JSONDecodeError:
            logger.warning("inference.extraction.invalid_json")
    return ExtractionResult(
        fields=ground_fields(fields, text),
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens if isinstance(prompt_tokens, int) else None,
        completion_tokens=completion_tokens if isinstance(completion_tokens, int) else None,
    )
