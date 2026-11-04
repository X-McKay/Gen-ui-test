"""Question bank: what can be asked, how, in which order, and what must be confirmed.

This is data, not prompt text. The agent never decides what is required; it only
phrases and lays out the specs returned by :mod:`app.intake.gap_analysis`.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.intake.schema import (
    AutonomyLevel,
    ControlKind,
    DataSubject,
    Domain,
    IntakeRecord,
    LifecycleStage,
    ModelSource,
    RiskTier,
    SpecialCategory,
    TargetUsers,
)

Control = Literal["choice", "multi", "yes_no", "text"]


class Section(StrEnum):
    PROJECT = "project"
    AI_SYSTEM = "ai_system"
    DATA = "data"
    USE_CASE = "use_case"
    CONTROLS = "controls"


SECTION_LABELS: dict[Section, str] = {
    Section.PROJECT: "Project",
    Section.AI_SYSTEM: "AI system",
    Section.DATA: "Data",
    Section.USE_CASE: "Use case",
    Section.CONTROLS: "Controls",
}


class Option(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    label: str
    description: str | None = None


class Gate(BaseModel):
    """A question is asked only when ``field`` holds one of ``values``."""

    model_config = ConfigDict(extra="forbid")

    field: str
    values: list[object]


class QuestionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str = Field(description="Dotted path, e.g. 'data.processes_personal_data'")
    section: Section
    label: str = Field(description="Short noun phrase for chips and the review page")
    prompt: str = Field(description="The question as shown to the user, ≤ 75 characters per line")
    control: Control
    options: list[Option] = Field(default_factory=list)
    required: bool = True
    must_confirm: bool = False
    is_gate: bool = False
    gate: Gate | None = None
    why_asked: str | None = Field(default=None, description="One line shown on sensitive questions")
    sensitive: bool = False
    placeholder: str | None = None
    priority: int = Field(default=100, description="Lower is asked earlier")


def _opts(*pairs: tuple[str, str]) -> list[Option]:
    return [Option(value=value, label=label) for value, label in pairs]


ANNEX_III_DOMAINS: frozenset[Domain] = frozenset(
    {
        Domain.HR_EMPLOYMENT,
        Domain.CREDIT_INSURANCE,
        Domain.EDUCATION,
        Domain.LAW_ENFORCEMENT,
        Domain.MIGRATION_BORDER,
        Domain.JUSTICE_DEMOCRATIC,
        Domain.CRITICAL_INFRASTRUCTURE,
        Domain.ESSENTIAL_SERVICES,
        Domain.MEDICAL_OR_SAFETY_COMPONENT,
    }
)

USES_AI = Gate(field="ai_system.uses_ai", values=[True])
PERSONAL_DATA = Gate(field="data.processes_personal_data", values=[True])

QUESTION_BANK: list[QuestionSpec] = [
    # --- Gates: these choose the classification branch and are asked first ----------------
    QuestionSpec(
        field="ai_system.uses_ai",
        section=Section.AI_SYSTEM,
        label="Uses AI",
        prompt="Does the project use a machine-learning or generative model?",
        control="yes_no",
        is_gate=True,
        priority=0,
    ),
    QuestionSpec(
        field="data.processes_personal_data",
        section=Section.DATA,
        label="Personal data",
        prompt="Does it process personal data about identifiable people?",
        control="yes_no",
        is_gate=True,
        priority=1,
        why_asked="Personal data brings GDPR into scope.",
    ),
    QuestionSpec(
        field="use_case.domains",
        section=Section.USE_CASE,
        label="Domains",
        prompt="Which areas does the project operate in?",
        control="multi",
        options=_opts(
            (Domain.HR_EMPLOYMENT, "HR and employment"),
            (Domain.CREDIT_INSURANCE, "Credit or insurance"),
            (Domain.EDUCATION, "Education"),
            (Domain.LAW_ENFORCEMENT, "Law enforcement"),
            (Domain.MIGRATION_BORDER, "Migration and border"),
            (Domain.JUSTICE_DEMOCRATIC, "Justice or democratic processes"),
            (Domain.CRITICAL_INFRASTRUCTURE, "Critical infrastructure"),
            (Domain.MEDICAL_OR_SAFETY_COMPONENT, "Medical or safety component"),
            (Domain.ESSENTIAL_SERVICES, "Essential services"),
            (Domain.OTHER, "None of these"),
        ),
        is_gate=True,
        must_confirm=True,
        priority=2,
        why_asked="Several of these areas are high-risk under EU AI Act Annex III.",
        sensitive=True,
    ),
    QuestionSpec(
        field="use_case.affects_legal_or_significant_effects",
        section=Section.USE_CASE,
        label="Significant effects",
        prompt="Can its output affect someone's legal rights, job, credit or access to services?",
        control="yes_no",
        is_gate=True,
        priority=3,
        why_asked="Significant effects on people raise the risk tier.",
        sensitive=True,
    ),
    # --- Project --------------------------------------------------------------------------
    QuestionSpec(
        field="project.name",
        section=Section.PROJECT,
        label="Project name",
        prompt="What is the project called?",
        control="text",
        placeholder="Candidate summary assistant",
        priority=10,
    ),
    QuestionSpec(
        field="project.owner",
        section=Section.PROJECT,
        label="Owner",
        prompt="Who owns the project?",
        control="text",
        placeholder="Name or team alias",
        priority=11,
    ),
    QuestionSpec(
        field="project.lifecycle_stage",
        section=Section.PROJECT,
        label="Lifecycle stage",
        prompt="Where is the project in its lifecycle?",
        control="choice",
        options=_opts(
            (LifecycleStage.IDEA, "Idea"),
            (LifecycleStage.POC, "Proof of concept"),
            (LifecycleStage.PILOT, "Pilot"),
            (LifecycleStage.PRODUCTION, "Production"),
        ),
        priority=12,
    ),
    QuestionSpec(
        field="project.target_users",
        section=Section.PROJECT,
        label="Target users",
        prompt="Who will use it?",
        control="choice",
        options=_opts(
            (TargetUsers.INTERNAL, "Internal staff"),
            (TargetUsers.EXTERNAL, "External partners or customers"),
            (TargetUsers.PUBLIC, "The general public"),
        ),
        priority=13,
    ),
    QuestionSpec(
        field="project.description",
        section=Section.PROJECT,
        label="Description",
        prompt="Describe the project in a sentence or two.",
        control="text",
        required=False,
        priority=14,
    ),
    QuestionSpec(
        field="project.team",
        section=Section.PROJECT,
        label="Team",
        prompt="Which team builds it?",
        control="text",
        required=False,
        priority=15,
    ),
    QuestionSpec(
        field="project.business_unit",
        section=Section.PROJECT,
        label="Business unit",
        prompt="Which business unit does it belong to?",
        control="text",
        required=False,
        priority=16,
    ),
    QuestionSpec(
        field="project.deployment_regions",
        section=Section.PROJECT,
        label="Deployment regions",
        prompt="Where will it be deployed?",
        control="multi",
        options=_opts(
            ("eu", "European Union"),
            ("uk", "United Kingdom"),
            ("us", "United States"),
            ("apac", "Asia-Pacific"),
            ("global", "Global"),
        ),
        required=False,
        priority=17,
    ),
    QuestionSpec(
        field="project.third_party_services",
        section=Section.PROJECT,
        label="Third-party services",
        prompt="Which external services or software does it depend on at run time?",
        control="text",
        required=False,
        placeholder="e.g. OpenAI API, AWS S3, Postgres (RDS)",
        priority=18,
    ),
    # --- AI system ------------------------------------------------------------------------
    QuestionSpec(
        field="ai_system.model_source",
        section=Section.AI_SYSTEM,
        label="Model source",
        prompt="Where does the model come from?",
        control="choice",
        options=_opts(
            (ModelSource.THIRD_PARTY_API, "Third-party API"),
            (ModelSource.OPEN_WEIGHTS, "Open weights, self-hosted"),
            (ModelSource.IN_HOUSE, "Trained in house"),
        ),
        gate=USES_AI,
        priority=20,
    ),
    QuestionSpec(
        field="ai_system.autonomy_level",
        section=Section.AI_SYSTEM,
        label="Autonomy",
        prompt="How much does the system decide on its own?",
        control="choice",
        options=_opts(
            (AutonomyLevel.ASSISTIVE, "Assists a person"),
            (AutonomyLevel.RECOMMENDS, "Recommends, a person decides"),
            (AutonomyLevel.DECIDES, "Decides without review"),
        ),
        gate=USES_AI,
        priority=21,
        why_asked="Automated decisions need stronger oversight.",
    ),
    QuestionSpec(
        field="ai_system.human_oversight",
        section=Section.AI_SYSTEM,
        label="Human oversight",
        prompt="Can a person review or override its outputs?",
        control="yes_no",
        gate=USES_AI,
        priority=22,
    ),
    QuestionSpec(
        field="ai_system.gpai_model_used",
        section=Section.AI_SYSTEM,
        label="General-purpose model",
        prompt="Is a general-purpose model (for example an LLM) part of it?",
        control="yes_no",
        gate=USES_AI,
        priority=23,
    ),
    QuestionSpec(
        field="ai_system.fine_tuned_or_trained",
        section=Section.AI_SYSTEM,
        label="Fine-tuned or trained",
        prompt="Do you fine-tune or train the model yourselves?",
        control="yes_no",
        gate=USES_AI,
        required=False,
        priority=24,
    ),
    QuestionSpec(
        field="ai_system.model_types",
        section=Section.AI_SYSTEM,
        label="Model types",
        prompt="What kind of models are involved?",
        control="multi",
        options=_opts(
            ("llm", "Large language model"),
            ("vision", "Computer vision"),
            ("speech", "Speech or audio"),
            ("classical_ml", "Classical ML (scoring, forecasting)"),
            ("recommender", "Recommender"),
            ("other", "Other"),
        ),
        gate=USES_AI,
        required=False,
        priority=25,
    ),
    QuestionSpec(
        field="ai_system.model_providers",
        section=Section.AI_SYSTEM,
        label="Model providers",
        prompt="Which model providers are used?",
        control="multi",
        options=_opts(
            ("openai", "OpenAI"),
            ("anthropic", "Anthropic"),
            ("google", "Google"),
            ("aws_bedrock", "AWS Bedrock"),
            ("azure_openai", "Azure OpenAI"),
            ("mistral", "Mistral"),
            ("meta", "Meta (Llama)"),
            ("self_hosted", "Self-hosted"),
            ("other", "Other"),
        ),
        gate=USES_AI,
        required=False,
        priority=26,
    ),
    # --- Data -----------------------------------------------------------------------------
    QuestionSpec(
        field="data.special_category_data",
        section=Section.DATA,
        label="Special-category data",
        prompt="Does it handle any special-category data?",
        control="multi",
        options=_opts(
            (SpecialCategory.HEALTH, "Health"),
            (SpecialCategory.BIOMETRIC, "Biometric"),
            (SpecialCategory.ETHNICITY, "Ethnicity"),
            (SpecialCategory.POLITICAL, "Political opinions"),
            (SpecialCategory.RELIGIOUS, "Religious beliefs"),
            (SpecialCategory.SEXUAL_ORIENTATION, "Sexual orientation"),
            (SpecialCategory.CRIMINAL, "Criminal records"),
        ),
        gate=PERSONAL_DATA,
        must_confirm=True,
        sensitive=True,
        why_asked="Special-category data needs a DPIA and changes the risk tier.",
        priority=30,
    ),
    QuestionSpec(
        field="data.data_subjects",
        section=Section.DATA,
        label="Data subjects",
        prompt="Whose data is it?",
        control="multi",
        options=_opts(
            (DataSubject.EMPLOYEES, "Employees or candidates"),
            (DataSubject.CUSTOMERS, "Customers"),
            (DataSubject.PUBLIC, "Members of the public"),
            (DataSubject.MINORS, "Minors"),
        ),
        gate=PERSONAL_DATA,
        must_confirm=True,
        sensitive=True,
        why_asked="Data about minors raises the risk tier.",
        priority=31,
    ),
    QuestionSpec(
        field="data.biometric_identification",
        section=Section.DATA,
        label="Biometric identification",
        prompt="Does it identify people from biometric data such as faces or voices?",
        control="yes_no",
        gate=PERSONAL_DATA,
        must_confirm=True,
        sensitive=True,
        why_asked="Biometric identification changes the EU AI Act tier.",
        priority=32,
    ),
    QuestionSpec(
        field="data.pii_categories",
        section=Section.DATA,
        label="Personal data categories",
        prompt="Which kinds of personal data does it process?",
        control="multi",
        options=_opts(
            ("contact", "Names and contact details"),
            ("identifiers", "IDs and account numbers"),
            ("financial", "Financial"),
            ("employment", "Employment and education history"),
            ("location", "Location"),
            ("behavioural", "Behavioural or usage"),
            ("free_text", "Free text that may contain anything"),
        ),
        gate=PERSONAL_DATA,
        required=False,
        priority=33,
    ),
    QuestionSpec(
        field="data.trains_on_personal_data",
        section=Section.DATA,
        label="Trains on personal data",
        prompt="Is personal data used to train or fine-tune a model?",
        control="yes_no",
        gate=PERSONAL_DATA,
        priority=34,
    ),
    QuestionSpec(
        field="data.cross_border_transfer",
        section=Section.DATA,
        label="Cross-border transfer",
        prompt="Does personal data leave the region it was collected in?",
        control="yes_no",
        gate=PERSONAL_DATA,
        required=False,
        priority=35,
    ),
    QuestionSpec(
        field="data.retention_policy",
        section=Section.DATA,
        label="Retention policy",
        prompt="How long is personal data kept?",
        control="choice",
        options=_opts(
            ("not_stored", "Not stored"),
            ("under_30_days", "Under 30 days"),
            ("under_1_year", "Under a year"),
            ("over_1_year", "A year or longer"),
            ("undefined", "No policy yet"),
        ),
        gate=PERSONAL_DATA,
        required=False,
        priority=36,
    ),
    QuestionSpec(
        field="data.data_sources",
        section=Section.DATA,
        label="Data sources",
        prompt="Where does the data come from?",
        control="multi",
        options=_opts(
            ("internal_db", "Internal databases"),
            ("user_upload", "User uploads"),
            ("third_party", "Third-party providers"),
            ("public_web", "Public web"),
            ("logs", "System logs"),
        ),
        required=False,
        priority=37,
    ),
    # --- Use case -------------------------------------------------------------------------
    QuestionSpec(
        field="use_case.purpose",
        section=Section.USE_CASE,
        label="Purpose",
        prompt="In one line, what is it for?",
        control="text",
        required=False,
        priority=40,
    ),
    QuestionSpec(
        field="use_case.interacts_directly_with_people",
        section=Section.USE_CASE,
        label="Interacts with people",
        prompt="Do people interact with the AI directly, for example through chat?",
        control="yes_no",
        gate=USES_AI,
        priority=41,
        why_asked="Direct interaction carries a transparency obligation.",
    ),
    QuestionSpec(
        field="use_case.generates_synthetic_content",
        section=Section.USE_CASE,
        label="Generates content",
        prompt="Does it generate text, images, audio or video shown to people?",
        control="yes_no",
        gate=USES_AI,
        priority=42,
    ),
    QuestionSpec(
        field="use_case.emotion_recognition",
        section=Section.USE_CASE,
        label="Emotion recognition",
        prompt="Does it infer emotions or intentions from people?",
        control="yes_no",
        gate=USES_AI,
        must_confirm=True,
        sensitive=True,
        why_asked="Emotion recognition at work or school is prohibited.",
        priority=43,
    ),
    QuestionSpec(
        field="use_case.social_scoring",
        section=Section.USE_CASE,
        label="Social scoring",
        prompt="Does it score people on behaviour or traits to decide their treatment?",
        control="yes_no",
        gate=USES_AI,
        must_confirm=True,
        sensitive=True,
        why_asked="Social scoring is a prohibited practice.",
        priority=44,
    ),
    QuestionSpec(
        field="use_case.remote_biometric_id_public_spaces",
        section=Section.USE_CASE,
        label="Remote biometric ID",
        prompt="Does it identify people remotely in public spaces?",
        control="yes_no",
        gate=Gate(field="data.biometric_identification", values=[True]),
        must_confirm=True,
        sensitive=True,
        why_asked="Remote biometric identification in public is tightly restricted.",
        priority=45,
    ),
    QuestionSpec(
        field="use_case.manipulative_or_subliminal",
        section=Section.USE_CASE,
        label="Manipulative techniques",
        prompt="Does it use subliminal or manipulative techniques to steer behaviour?",
        control="yes_no",
        gate=USES_AI,
        must_confirm=True,
        sensitive=True,
        required=False,
        why_asked="Manipulative techniques are a prohibited practice.",
        priority=46,
    ),
    QuestionSpec(
        field="use_case.untargeted_facial_scraping",
        section=Section.USE_CASE,
        label="Facial-image scraping",
        prompt="Does it collect facial images from the web or CCTV at scale?",
        control="yes_no",
        gate=Gate(field="data.biometric_identification", values=[True]),
        must_confirm=True,
        sensitive=True,
        required=False,
        why_asked="Untargeted facial scraping is a prohibited practice.",
        priority=47,
    ),
    # --- Controls: one question, asked only when the inherent risk is medium or above. It
    # must be confirmed because only confirmed controls lower the residual risk -------------
    QuestionSpec(
        field="controls.in_place",
        section=Section.CONTROLS,
        label="Controls in place",
        prompt="Which of these controls are in place today? (Not plans.)",
        control="multi",
        options=[
            Option(
                value=ControlKind.GUARDRAILS,
                label="Input and output guardrails",
                description="Prompt-injection and content filters on inputs and outputs",
            ),
            Option(
                value=ControlKind.ACCESS_CONTROLS,
                label="Access controls",
                description="Authentication and authorisation restrict who can use it",
            ),
            Option(
                value=ControlKind.PII_MINIMISATION,
                label="Personal data minimisation",
                description="Personal data is redacted or minimised before the model",
            ),
            Option(
                value=ControlKind.ABUSE_MONITORING,
                label="Abuse monitoring",
                description="Rate limits, logging and misuse monitoring",
            ),
            Option(
                value=ControlKind.PRE_RELEASE_EVALUATION,
                label="Evaluation and red-teaming",
                description="Evaluated or red-teamed before release, with ongoing checks",
            ),
            Option(
                value=ControlKind.VENDOR_DATA_PROTECTIONS,
                label="Vendor data protections",
                description="The provider contract bars training on your data",
            ),
            Option(
                value=ControlKind.INCIDENT_RESPONSE,
                label="Incident response",
                description="Rollback or kill switch and an incident process",
            ),
            Option(
                value=ControlKind.USER_DISCLOSURE,
                label="User disclosure",
                description="People are told they interact with AI or see AI content",
            ),
            Option(value=ControlKind.NONE, label="None of these yet"),
        ],
        must_confirm=True,
        why_asked="Confirmed controls lower the residual risk; plans do not.",
        priority=50,
    ),
]

QUESTIONS_BY_FIELD: dict[str, QuestionSpec] = {spec.field: spec for spec in QUESTION_BANK}

# Fields whose inferred value must be confirmed by the user however confident the model is.
MUST_CONFIRM_FIELDS: frozenset[str] = frozenset(
    spec.field for spec in QUESTION_BANK if spec.must_confirm
)

# Fields that are only "must confirm" when they hold a particular value.
ConditionalMustConfirm = Callable[[IntakeRecord], bool]


def minors_present(record: IntakeRecord) -> bool:
    value = record.value_of("data.data_subjects")
    return isinstance(value, list) and DataSubject.MINORS in value


def annex_iii_domain_present(record: IntakeRecord) -> bool:
    value = record.value_of("use_case.domains")
    return isinstance(value, list) and any(domain in ANNEX_III_DOMAINS for domain in value)


CONDITIONAL_MUST_CONFIRM: dict[str, ConditionalMustConfirm] = {
    "data.data_subjects": minors_present,
    "use_case.domains": annex_iii_domain_present,
}


# Questions whose gate is computed rather than read from one field. Controls are only worth
# asking when the inherent risk is medium or above; a low-risk tool skips the section.
ConditionalGate = Callable[[IntakeRecord], bool]

CONTROL_GATE_TIERS: frozenset[RiskTier] = frozenset(
    {RiskTier.MEDIUM, RiskTier.HIGH, RiskTier.CRITICAL}
)


def inherent_risk_at_least_medium(record: IntakeRecord) -> bool:
    return record.assessment.inherent_risk.tier in CONTROL_GATE_TIERS


CONDITIONAL_GATES: dict[str, ConditionalGate] = {
    spec.field: inherent_risk_at_least_medium
    for spec in QUESTION_BANK
    if spec.section is Section.CONTROLS
}


def spec_for(field: str) -> QuestionSpec:
    return QUESTIONS_BY_FIELD[field]


def display_value(field: str, value: object) -> str:
    """Human label for a stored value, used by chips, findings and the PDF."""
    if value is None:
        return "—"
    if value == "unknown":
        return "Not sure"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    spec = QUESTIONS_BY_FIELD.get(field)
    labels = {option.value: option.label for option in spec.options} if spec else {}
    if isinstance(value, list):
        if not value:
            return "None"
        return ", ".join(labels.get(str(item), str(item)) for item in value)
    return labels.get(str(value), str(value))
