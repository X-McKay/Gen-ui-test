"""IntakeRecord: the single source of truth for the intake data model.

Every leaf value is wrapped in :class:`FieldMeta` so that confidence, provenance and
confirmation travel with the value. ``"unknown"`` is a legal value for every field and is
distinct from ``False`` and from ``None`` (not yet captured).

``schema/intake.schema.json`` and the frontend TypeScript types are generated from this
module (``make export-schema``); CI fails when they are stale.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = "1.0.0"

UNKNOWN: Literal["unknown"] = "unknown"
Unknown = Literal["unknown"]

SOURCE_PATTERN = r"^(user|inferred|repo:.+)$"


class FieldMeta[T](BaseModel):
    """A stored value with confidence, provenance and confirmation."""

    model_config = ConfigDict(extra="forbid")

    value: T | Unknown | None = None
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = 0.0
    source: Annotated[str, Field(pattern=SOURCE_PATTERN)] = "inferred"
    confirmed: bool = False

    @property
    def is_set(self) -> bool:
        """True when a value (including ``unknown``) has been captured."""
        return self.value is not None

    @property
    def is_unknown(self) -> bool:
        return self.value == UNKNOWN


# --- Enumerations -------------------------------------------------------------------------


class IntakeMode(StrEnum):
    NEW = "new"
    EXISTING = "existing"


class IntakeStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SUBMITTED = "submitted"
    ESCALATED = "escalated"


class LifecycleStage(StrEnum):
    IDEA = "idea"
    POC = "poc"
    PILOT = "pilot"
    PRODUCTION = "production"


class TargetUsers(StrEnum):
    INTERNAL = "internal"
    EXTERNAL = "external"
    PUBLIC = "public"


class ModelSource(StrEnum):
    THIRD_PARTY_API = "third_party_api"
    OPEN_WEIGHTS = "open_weights"
    IN_HOUSE = "in_house"


class AutonomyLevel(StrEnum):
    ASSISTIVE = "assistive"
    RECOMMENDS = "recommends"
    DECIDES = "decides"


class SpecialCategory(StrEnum):
    HEALTH = "health"
    BIOMETRIC = "biometric"
    ETHNICITY = "ethnicity"
    POLITICAL = "political"
    RELIGIOUS = "religious"
    SEXUAL_ORIENTATION = "sexual_orientation"
    CRIMINAL = "criminal"


class DataSubject(StrEnum):
    EMPLOYEES = "employees"
    CUSTOMERS = "customers"
    PUBLIC = "public"
    MINORS = "minors"


class Domain(StrEnum):
    HR_EMPLOYMENT = "hr_employment"
    CREDIT_INSURANCE = "credit_insurance"
    EDUCATION = "education"
    LAW_ENFORCEMENT = "law_enforcement"
    MIGRATION_BORDER = "migration_border"
    JUSTICE_DEMOCRATIC = "justice_democratic"
    CRITICAL_INFRASTRUCTURE = "critical_infrastructure"
    MEDICAL_OR_SAFETY_COMPONENT = "medical_or_safety_component"
    ESSENTIAL_SERVICES = "essential_services"
    OTHER = "other"


class EuAiActClassification(StrEnum):
    PROHIBITED = "prohibited"
    HIGH_RISK = "high_risk"
    LIMITED_TRANSPARENCY = "limited_transparency"
    MINIMAL = "minimal"


class RiskTier(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# --- Sections -----------------------------------------------------------------------------


class Meta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intake_id: str
    schema_version: str = SCHEMA_VERSION
    mode: IntakeMode = IntakeMode.NEW
    status: IntakeStatus = IntakeStatus.IN_PROGRESS
    repo_url: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    submitted_at: datetime | None = None
    question_count: int = 0
    analysis_progress: str | None = None


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: FieldMeta[str] = Field(default_factory=FieldMeta[str])
    description: FieldMeta[str] = Field(default_factory=FieldMeta[str])
    owner: FieldMeta[str] = Field(default_factory=FieldMeta[str])
    team: FieldMeta[str] = Field(default_factory=FieldMeta[str])
    business_unit: FieldMeta[str] = Field(default_factory=FieldMeta[str])
    lifecycle_stage: FieldMeta[LifecycleStage] = Field(default_factory=FieldMeta[LifecycleStage])
    target_users: FieldMeta[TargetUsers] = Field(default_factory=FieldMeta[TargetUsers])
    deployment_regions: FieldMeta[list[str]] = Field(default_factory=FieldMeta[list[str]])


class AiSystem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uses_ai: FieldMeta[bool] = Field(default_factory=FieldMeta[bool])
    model_types: FieldMeta[list[str]] = Field(default_factory=FieldMeta[list[str]])
    model_source: FieldMeta[ModelSource] = Field(default_factory=FieldMeta[ModelSource])
    model_providers: FieldMeta[list[str]] = Field(default_factory=FieldMeta[list[str]])
    gpai_model_used: FieldMeta[bool] = Field(default_factory=FieldMeta[bool])
    fine_tuned_or_trained: FieldMeta[bool] = Field(default_factory=FieldMeta[bool])
    autonomy_level: FieldMeta[AutonomyLevel] = Field(default_factory=FieldMeta[AutonomyLevel])
    human_oversight: FieldMeta[bool] = Field(default_factory=FieldMeta[bool])


class Data(BaseModel):
    model_config = ConfigDict(extra="forbid")

    processes_personal_data: FieldMeta[bool] = Field(default_factory=FieldMeta[bool])
    pii_categories: FieldMeta[list[str]] = Field(default_factory=FieldMeta[list[str]])
    special_category_data: FieldMeta[list[SpecialCategory]] = Field(
        default_factory=FieldMeta[list[SpecialCategory]]
    )
    biometric_identification: FieldMeta[bool] = Field(default_factory=FieldMeta[bool])
    data_subjects: FieldMeta[list[DataSubject]] = Field(
        default_factory=FieldMeta[list[DataSubject]]
    )
    data_sources: FieldMeta[list[str]] = Field(default_factory=FieldMeta[list[str]])
    trains_on_personal_data: FieldMeta[bool] = Field(default_factory=FieldMeta[bool])
    retention_policy: FieldMeta[str] = Field(default_factory=FieldMeta[str])
    cross_border_transfer: FieldMeta[bool] = Field(default_factory=FieldMeta[bool])


class UseCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domains: FieldMeta[list[Domain]] = Field(default_factory=FieldMeta[list[Domain]])
    purpose: FieldMeta[str] = Field(default_factory=FieldMeta[str])
    affects_legal_or_significant_effects: FieldMeta[bool] = Field(default_factory=FieldMeta[bool])
    interacts_directly_with_people: FieldMeta[bool] = Field(default_factory=FieldMeta[bool])
    generates_synthetic_content: FieldMeta[bool] = Field(default_factory=FieldMeta[bool])
    emotion_recognition: FieldMeta[bool] = Field(default_factory=FieldMeta[bool])
    social_scoring: FieldMeta[bool] = Field(default_factory=FieldMeta[bool])
    remote_biometric_id_public_spaces: FieldMeta[bool] = Field(default_factory=FieldMeta[bool])
    # Not in the original question list; needed for Art. 5(1)(a) and 5(1)(e).
    manipulative_or_subliminal: FieldMeta[bool] = Field(default_factory=FieldMeta[bool])
    untargeted_facial_scraping: FieldMeta[bool] = Field(default_factory=FieldMeta[bool])


# --- Assessment (derived, never asked, never edited) ----------------------------------------


class RationaleEntry(BaseModel):
    """Why a classification was reached, linked to the answer that drove it."""

    model_config = ConfigDict(extra="forbid")

    field: str = Field(description="Dotted path of the field that triggered the rule")
    value: object = Field(description="The value that triggered the rule")
    article: str = Field(description="Citation, e.g. 'EU AI Act Art. 6(2), Annex III 4'")
    text: str = Field(description="Plain-language explanation")
    effect: str = Field(description="Classification effect, e.g. 'high_risk'")


class Obligation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    framework: str
    text: str
    reference: str | None = None
    role: Literal["provider", "deployer", "both"] | None = None


class EuAiActAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: EuAiActClassification = EuAiActClassification.MINIMAL
    annex_iii_categories: list[str] = Field(default_factory=list)
    rationale: list[RationaleEntry] = Field(default_factory=list)


class Assessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eu_ai_act: EuAiActAssessment = Field(default_factory=EuAiActAssessment)
    overall_risk_tier: RiskTier = RiskTier.LOW
    applicable_frameworks: list[str] = Field(default_factory=list)
    obligations: list[Obligation] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(
        default_factory=list, description="Dotted paths of fields left 'unknown'"
    )


# --- Record ---------------------------------------------------------------------------------

SECTION_NAMES: tuple[str, ...] = ("project", "ai_system", "data", "use_case")


class IntakeRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: Meta
    project: Project = Field(default_factory=Project)
    ai_system: AiSystem = Field(default_factory=AiSystem)
    data: Data = Field(default_factory=Data)
    use_case: UseCase = Field(default_factory=UseCase)
    assessment: Assessment = Field(default_factory=Assessment)

    @field_validator("meta")
    @classmethod
    def _touch(cls, meta: Meta) -> Meta:
        return meta

    # -- field access by dotted path ---------------------------------------------------------

    def get_field(self, path: str) -> FieldMeta[object]:
        """Return the :class:`FieldMeta` at ``section.field``."""
        section_name, _, field_name = path.partition(".")
        if section_name not in SECTION_NAMES or not field_name:
            raise KeyError(path)
        section = getattr(self, section_name)
        if field_name not in type(section).model_fields:
            raise KeyError(path)
        field: FieldMeta[object] = getattr(section, field_name)
        return field

    def set_field(
        self,
        path: str,
        value: object,
        *,
        source: str,
        confidence: float,
        confirmed: bool,
    ) -> FieldMeta[object]:
        """Replace the field at ``path``. Validates the value against the field type."""
        section_name, _, field_name = path.partition(".")
        section = getattr(self, section_name)
        annotation = type(section).model_fields[field_name].annotation
        if annotation is None:  # pragma: no cover - every field is annotated
            raise KeyError(path)
        new_field = annotation.model_validate(
            {"value": value, "source": source, "confidence": confidence, "confirmed": confirmed}
        )
        setattr(section, field_name, new_field)
        self.meta.updated_at = datetime.now(UTC)
        return new_field  # type: ignore[no-any-return]

    def iter_fields(self) -> list[tuple[str, FieldMeta[object]]]:
        """All ``(path, field)`` pairs in section order."""
        pairs: list[tuple[str, FieldMeta[object]]] = []
        for section_name in SECTION_NAMES:
            section = getattr(self, section_name)
            for field_name in type(section).model_fields:
                pairs.append((f"{section_name}.{field_name}", getattr(section, field_name)))
        return pairs

    def value_of(self, path: str) -> object:
        """Shortcut for ``get_field(path).value``."""
        return self.get_field(path).value


def field_paths() -> list[str]:
    """Every dotted field path of the askable sections, in declaration order."""
    paths: list[str] = []
    for section_name in SECTION_NAMES:
        section_type = IntakeRecord.model_fields[section_name].annotation
        assert section_type is not None
        paths.extend(f"{section_name}.{name}" for name in section_type.model_fields)
    return paths


def new_record(intake_id: str, mode: IntakeMode = IntakeMode.NEW) -> IntakeRecord:
    return IntakeRecord(meta=Meta(intake_id=intake_id, mode=mode))
