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
from app.settings import Settings, get_settings

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
        "True whenever an LLM or other foundation model is used (GPT, Claude, Gemini, Llama, "
        "Mistral, Qwen); false for a classical model (regression, boosting, forecasting) and "
        "for a single-task model such as speech-to-text (Whisper), OCR or a translation engine."
    ),
    "ai_system.model_source": (
        "third_party_api = a hosted provider API (OpenAI, Anthropic, Azure, Bedrock, Gemini, a "
        "model vendor); open_weights = a published model you run yourself ('self-hosted', "
        "'open-weights', Llama, Mistral, Qwen are always open_weights, never in_house); "
        "in_house = a model your own team trained from scratch."
    ),
    "ai_system.autonomy_level": (
        "Always record it when the text says who acts on the output. assistive = produces "
        "material a person uses, edits or publishes (drafts, summaries, transcripts, captions, "
        "translations, generated audio, a suggested default the user can change); nothing is "
        "decided. recommends = proposes a decision, score, ranking or flag about a case that a "
        "person accepts or rejects; decides = acts or decides without a person reviewing that "
        "case (automatic blocking, payment, approval, gate opening, placing orders), even if "
        "someone can override afterwards."
    ),
    "ai_system.human_oversight": "True when a person reviews or can override outputs.",
    "project.target_users": (
        "Who operates or uses the system, not who it is about. internal = your own staff only "
        "(underwriters, analysts, your legal team); external = customers, clients or partners "
        "who log in or are known, including staff of a client or partner organisation (teachers "
        "at partner schools, caseworkers at a client authority); public = anyone, "
        "including visitors, applicants and consumers who can simply sign up for an account."
    ),
    "project.lifecycle_stage": "pilot and production are stated; otherwise leave it out.",
    "data.processes_personal_data": (
        "CVs, customer records, employee data, names, contact details, account data, device or "
        "browser identifiers and IP addresses all count."
    ),
    "data.special_category_data": (
        "Always record it when personal data is processed. List every category the data "
        "contains: health records, symptoms, radiology or patient data = health; face, voice or "
        "fingerprint data used to identify, verify or analyse a person (face match, voice login, "
        "facial-expression analysis) = biometric; also ethnicity, political, religious, "
        "sexual_orientation, criminal (investigation and conviction data). A recording that is "
        "only transcribed, captioned or used as a sample for speech synthesis is not biometric; "
        "a toy, shop or fitness tool has no health data unless health data is named, and mood or "
        "sentiment inferred from survey text or messages is not health data. Record [] "
        "when an ordinary business tool clearly has none."
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
        "recruiting, evaluating, promoting, assigning shifts or tasks to, or monitoring workers "
        "(an expense tool using HR tables or a bot answering staff questions about HR policy is "
        "other); credit_insurance = creditworthiness, credit scoring, loan decisions, and the "
        "pricing or risk assessment of life or health insurance (fraud detection, motor or "
        "property claims handling, payments and a bank's support chatbot are other); "
        "essential_services = eligibility for public benefits, housing, utilities (a council FAQ "
        "bot or a shop's refunds are other); critical_infrastructure = safety components that "
        "operate energy, water or transport networks (a company's own IT security, network "
        "monitoring, SOC tooling, building turnstiles and login pages are other); "
        "medical_or_safety_component = diagnosis, triage, a medical device or a safety function. "
        "A fraud, payments or claims model is other even at a bank or insurer. When in doubt, "
        "record ['other']."
    ),
    "use_case.affects_legal_or_significant_effects": (
        "True when outputs influence hiring, shifts or pay, credit, insurance pricing or claim "
        "payouts, access to benefits, grades, visas, legal status or similar decisions about a "
        "person, even with a human in the loop. Answering questions, small customer-service "
        "outcomes (refunds, order status), building access for staff, drafting content, "
        "blocking a network address, flagging a transaction or routing work to a reviewer are "
        "not significant effects."
    ),
    "use_case.interacts_directly_with_people": (
        "True when people converse with the system itself (chat, voice, assistant). A form, an "
        "upload, an app in which the output appears (a roster, an offer, a score) or an internal "
        "report is not direct interaction."
    ),
    "use_case.generates_synthetic_content": (
        "True when it produces text, images, audio or video shown to people: summaries of logs "
        "or claims, drafted messages, answers, explanations, posts, voice-overs, and the "
        "comments or replies an agent writes after acting; a tool that summarises log lines "
        "or search results generates content. A score, a ranking, a flag, a verbatim "
        "transcript of speech or a yes/no suggestion alone is not content."
    ),
    "use_case.emotion_recognition": (
        "True only when the system infers emotions, mood, attention or intentions of people."
    ),
    "use_case.social_scoring": (
        "True for a trustworthiness or behaviour score built from data gathered in unrelated "
        "contexts (social-media activity, payment history, complaints, lifestyle) that leads "
        "to worse treatment somewhere else (renting, services, prices), even when used for one "
        "purpose (EU AI Act Art. 5(1)(c)). A job-fit, credit or quality score built only from "
        "data relevant to that decision is NOT social scoring: record false."
    ),
    "use_case.manipulative_or_subliminal": "True only for deliberate deception or subliminal cues.",
    "use_case.untargeted_facial_scraping": (
        "True only when facial images are collected indiscriminately from the internet or CCTV "
        "to build or grow a face database. Matching faces against an existing watch list or "
        "verifying a known person is not scraping: record false."
    ),
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


def extraction_tool_schema(only: frozenset[str] | None = None) -> dict[str, Any]:
    """OpenAI-style tool definition with one property per askable field (or per field in
    ``only``, for the completion pass)."""
    properties: dict[str, Any] = {}
    for spec in QUESTION_BANK:
        if only is not None and spec.field not in only:
            continue
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
    + ". Then fill every other field the text supports, in particular model_source, "
    "autonomy_level, human_oversight, target_users, data_subjects, special_category_data, "
    "biometric_identification, generates_synthetic_content, interacts_directly_with_people "
    "and controls.in_place; the owner is asked a question for every field you leave out, so "
    "a named provider, a stated reviewer or a stated login must be recorded, not skipped"
    ". When a description of an ordinary business tool clearly implies that a sensitive "
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
# A full extraction returns 18 to 30 fields; fewer means the model stopped early.
ABBREVIATED_FIELD_COUNT = 14
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
        "log in with",
        "logged in",
        "logged-in",
        "sign in",
        "signed in",
        "sso",
        "authenticat",
        "authoris",
        "authoriz",
        "role-based",
        "roles",
        "named account",
        "permission",
        "mutual tls",
        "mtls",
        "restricted to",
        "limited to",
        "access control",
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
    "pre_release_evaluation": (
        "evaluat",
        "red team",
        "red-team",
        "tested",
        "benchmark",
        "eval",
        "validat",
    ),
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
        "automated",
        "label",
    ),
}


# An Annex III domain or a significant effect asserted from a description must name the thing
# it is about. These words are checked in the evidence quote (already required to be in the
# text), not in the whole text, so an insurer's chatbot is not credit_insurance just because the
# text says "insurance" somewhere. Without them the value stays but needs confirmation.
DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "hr_employment": (
        "recruit",
        "hiring",
        "hire",
        "candidate",
        "applicant",
        "cv",
        "promot",
        "terminat",
        "dismiss",
        "shift",
        "roster",
        "task",
        "performance",
        "productivity",
        "worker",
        "employee",
        "staff",
    ),
    "credit_insurance": (
        "creditworth",
        "credit scor",
        "credit decision",
        "credit risk",
        "loan",
        "mortgage",
        "lending",
        "premium",
        "underwrit",
        "insurance pricing",
        "insurance risk",
        "life insurance",
        "health insurance",
    ),
    "education": (
        "student",
        "pupil",
        "exam",
        "grade",
        "grading",
        "admission",
        "proctor",
        "school",
        "learner",
    ),
    "law_enforcement": (
        "police",
        "law enforcement",
        "officer",
        "crime",
        "criminal",
        "suspect",
        "offender",
    ),
    "migration_border": (
        "visa",
        "asylum",
        "border",
        "immigration",
        "migration",
        "residence permit",
    ),
    "justice_democratic": (
        "court",
        "judicial",
        "judge",
        "tribunal",
        "election",
        "referend",
        "voter",
    ),
    "critical_infrastructure": (
        "grid",
        "substation",
        "electricity",
        "power network",
        "power plant",
        "water",
        "gas",
        "heating",
        "rail",
        "traffic",
        "road",
        "pipeline",
        "critical infrastructure",
        "safety component",
    ),
    "essential_services": (
        "benefit",
        "welfare",
        "social assistance",
        "housing",
        "eligib",
        "utility",
        "emergency",
        "public service",
        "healthcare access",
    ),
    "medical_or_safety_component": (
        "diagnos",
        "triage",
        "medical device",
        "patient",
        "clinical",
        "ce-mark",
        "ce mark",
        "safety component",
        "safety function",
        "symptom",
        "treatment",
    ),
}
EFFECT_KEYWORDS: tuple[str, ...] = (
    "hire",
    "hiring",
    "recruit",
    "candidate",
    "shortlist",
    "promot",
    "terminat",
    "dismiss",
    "shift",
    "roster",
    "pay",
    "wage",
    "salary",
    "credit",
    "loan",
    "mortgage",
    "insurance",
    "premium",
    "claim",
    "settle",
    "benefit",
    "welfare",
    "housing",
    "eligib",
    "grade",
    "exam",
    "admission",
    "visa",
    "asylum",
    "legal",
    "court",
    "sentenc",
    "diagnos",
    "treatment",
    "triage",
    "patient",
    "fine",
    "penalt",
    "deny",
    "denied",
    "refus",
    "reject",
    "block",
    "access to",
    "contract",
    "price",
    "decision about",
    "decisions about",
)


def vocabulary_supported(path: str, value: object, evidence: str | None) -> bool:
    """True when the evidence quote names what an Annex III domain or a significant effect is
    about; a bare label such as "insurance" or "infrastructure" is not enough."""
    haystack = _normalise_text(evidence or "")
    if path == "use_case.domains" and isinstance(value, list):
        return all(
            str(domain) == "other"
            or any(word in haystack for word in DOMAIN_KEYWORDS.get(str(domain), ()))
            for domain in value
        )
    if path == "use_case.affects_legal_or_significant_effects" and value is True:
        return any(word in haystack for word in EFFECT_KEYWORDS)
    return True


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


def reconcile_fields(fields: list[ExtractedField]) -> list[ExtractedField]:
    """Definitional consistency between fields, applied after grounding.

    Biometric identification is, by definition, processing of biometric special-category data
    (GDPR Art. 4(14), 9(1)); a model that records the first and omits the second has left a
    fact out, so it is added at the identification's confidence.
    """
    by_path = {field.path: field for field in fields}
    identification = by_path.get("data.biometric_identification")
    if identification is None or identification.value is not True:
        return fields
    special = by_path.get("data.special_category_data")
    if special is None:
        return [
            *fields,
            ExtractedField(
                path="data.special_category_data",
                value=["biometric"],
                confidence=identification.confidence,
                evidence=identification.evidence,
            ),
        ]
    if isinstance(special.value, list) and "biometric" not in special.value:
        return [
            field
            if field.path != "data.special_category_data"
            else field.model_copy(update={"value": [*special.value, "biometric"]})
            for field in fields
        ]
    return fields


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
            if not vocabulary_supported(field.path, field.value, field.evidence):
                field = field.model_copy(
                    update={"confidence": min(field.confidence, UNGROUNDED_CONFIDENCE)}
                )
            grounded.append(field)
        elif field.path in DROP_WHEN_UNGROUNDED:
            logger.debug("inference.extraction.dropped_ungrounded", extra={"field": field.path})
        else:
            grounded.append(
                field.model_copy(
                    update={"confidence": min(field.confidence, UNGROUNDED_CONFIDENCE)}
                )
            )
    return reconcile_fields(grounded)


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
    user_content = text if not context else f"Source: {context}\n\n{text}"
    started = time.perf_counter()
    first = await _call_extraction(settings, user_content, only=None)
    fields = list(first.fields)
    prompt_tokens = first.prompt_tokens
    completion_tokens = first.completion_tokens
    if len(fields) < ABBREVIATED_FIELD_COUNT:
        # The model sometimes stops after the first group of fields although the text goes on
        # to name a provider, a reviewer or a login. One completion pass asks for the rest.
        recorded = {field.path for field in fields}
        remaining = frozenset(spec.field for spec in QUESTION_BANK) - recorded
        follow_up = (
            f"{user_content}\n\nAlready recorded: {', '.join(sorted(recorded)) or 'nothing'}. "
            "Record the remaining fields the text supports; leave out the others."
        )
        second = await _call_extraction(settings, follow_up, only=remaining)
        fields.extend(field for field in second.fields if field.path not in recorded)
        prompt_tokens = _add(prompt_tokens, second.prompt_tokens)
        completion_tokens = _add(completion_tokens, second.completion_tokens)
        logger.info(
            "inference.extraction.completion_pass",
            extra={"first_pass_fields": len(recorded), "added_fields": len(fields) - len(recorded)},
        )
    return ExtractionResult(
        fields=ground_fields(fields, text),
        latency_ms=int((time.perf_counter() - started) * 1000),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


def _add(left: int | None, right: int | None) -> int | None:
    if left is None:
        return right
    return left if right is None else left + right


async def _call_extraction(
    settings: Settings, user_content: str, *, only: frozenset[str] | None
) -> ExtractionResult:
    import litellm

    started = time.perf_counter()
    response = await litellm.acompletion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        tools=[extraction_tool_schema(only)],
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
        fields=fields,
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens if isinstance(prompt_tokens, int) else None,
        completion_tokens=completion_tokens if isinstance(completion_tokens, int) else None,
    )
