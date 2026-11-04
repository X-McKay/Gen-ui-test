"""Repository risk assessment: fact lanes in parallel, facts merged into an intake record,
then the deterministic rules engine (EU AI Act, frameworks, inherent and residual risk).

The model never rates risk. Each lane agent records facts with evidence; the record is built
with ``source="repo:<file>"`` and nothing confirmed, so the residual risk shown is the risk
*before* an owner confirms any control; the report also shows what it would be if the
claimed controls were confirmed, and lists the questions the repository could not answer.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from google.adk.models.base_llm import BaseLlm
from pydantic import BaseModel, ConfigDict, Field

from app.governance.classify import reclassify
from app.intake.gap_analysis import open_gaps
from app.intake.question_bank import QUESTIONS_BY_FIELD
from app.intake.record_service import coerce_value
from app.intake.schema import Assessment, IntakeRecord, RiskTier, new_record
from risk_review.agents.fact_finder.factory import available_fact_lanes, build_fact_finder
from risk_review.agents.fact_finder.tools.record_facts import LANE_KEY
from risk_review.agents.fact_finder.tools.record_facts import OUTPUT_KEY as FACTS_KEY
from risk_review.agents.fact_finder.types import Fact, FactsOutput
from risk_review.observability.trace import RunMetrics
from risk_review.runtime.manifest import Manifest, git_commit
from risk_review.settings import RiskReviewSettings
from risk_review.workflows.review import Totals, compute_totals_from_metrics, run_step_with_retry


class LaneFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lane: str
    status: str
    metrics: RunMetrics
    facts: list[Fact] = Field(default_factory=list)
    files_examined: list[str] = Field(default_factory=list)
    notes: str | None = None
    error: str | None = None


class MergedFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    value: object
    confidence: float
    basis: str
    lane: str
    evidence_file: str
    evidence_line: int
    evidence_quote: str
    conflicts: list[str] = Field(default_factory=list, description="Other lanes' values")


class AssessmentReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_id: str
    created_at: str
    repository: str
    git_commit: str
    lanes_requested: list[str]
    manifests: dict[str, Manifest]
    lanes: list[LaneFacts]
    facts: list[MergedFact]
    rejected_facts: list[str] = Field(default_factory=list)
    assessment: Assessment
    residual_if_confirmed: RiskTier
    open_questions: list[str] = Field(description="Required fields the repository did not settle")
    totals: Totals


def _fact_message(lane: str, repository_root: Path) -> str:
    return (
        f"Establish the facts of lane `{lane}` for the repository at the tool root "
        f"({repository_root.name}). Follow the lane skill: documents first, then code, and "
        "call record_facts with grounded facts."
    )


# The lane whose skill owns a field wins a disagreement, whatever the confidences: the
# controls lane searched for controls, the data lane read the schema. Other lanes' values are
# kept as conflicts. Fields not listed here go to the most confident lane.
FIELD_OWNERS: dict[str, str] = {
    **dict.fromkeys(
        (
            "project.name",
            "project.description",
            "project.lifecycle_stage",
            "project.target_users",
            "project.deployment_regions",
            "use_case.domains",
            "use_case.purpose",
            "use_case.interacts_directly_with_people",
            "use_case.generates_synthetic_content",
            "use_case.affects_legal_or_significant_effects",
            "use_case.emotion_recognition",
            "use_case.social_scoring",
            "ai_system.autonomy_level",
            "ai_system.human_oversight",
        ),
        "purpose-and-users",
    ),
    **dict.fromkeys(
        (
            "ai_system.uses_ai",
            "ai_system.model_types",
            "ai_system.model_providers",
            "ai_system.model_source",
            "ai_system.gpai_model_used",
            "ai_system.fine_tuned_or_trained",
        ),
        "ai-usage",
    ),
    **dict.fromkeys(
        (
            "data.processes_personal_data",
            "data.pii_categories",
            "data.special_category_data",
            "data.biometric_identification",
            "data.data_subjects",
            "data.data_sources",
            "data.trains_on_personal_data",
            "data.retention_policy",
        ),
        "data-and-privacy",
    ),
    "project.third_party_services": "third-party-services",
    "data.cross_border_transfer": "third-party-services",
    "controls.in_place": "controls-in-code",
}


def merge_facts(lanes: list[LaneFacts]) -> list[MergedFact]:
    """One value per field: the owning lane wins, else the highest confidence; the other
    values are kept as conflicts."""
    by_field: dict[str, list[tuple[Fact, str]]] = {}
    for lane_result in lanes:
        for fact in lane_result.facts:
            by_field.setdefault(fact.field, []).append((fact, lane_result.lane))
    merged: list[MergedFact] = []
    for field, candidates in by_field.items():
        owner = FIELD_OWNERS.get(field)
        candidates.sort(key=lambda item: (item[1] == owner, item[0].confidence), reverse=True)
        best, lane_name = candidates[0]
        conflicts = [
            f"{other_lane}: {other.value!r} ({other.confidence:.2f})"
            for other, other_lane in candidates[1:]
            if other.value != best.value
        ]
        merged.append(
            MergedFact(
                field=field,
                value=best.value,
                confidence=best.confidence,
                basis=best.basis,
                lane=lane_name,
                evidence_file=best.evidence[0].file,
                evidence_line=best.evidence[0].line,
                evidence_quote=best.evidence[0].quote,
                conflicts=conflicts,
            )
        )
    order = {field: index for index, field in enumerate(QUESTIONS_BY_FIELD)}
    merged.sort(key=lambda fact: order.get(fact.field, len(order)))
    return merged


def build_record(facts: list[MergedFact], *, confirmed: bool) -> tuple[IntakeRecord, list[str]]:
    record = new_record("assessment")
    rejected: list[str] = []
    for fact in facts:
        try:
            record.set_field(
                fact.field,
                coerce_value(fact.field, fact.value),
                source="user" if confirmed else f"repo:{fact.evidence_file}",
                confidence=fact.confidence,
                confirmed=confirmed,
            )
        except (KeyError, ValueError) as error:
            rejected.append(f"{fact.field}: {str(error).splitlines()[0][:120]}")
    return reclassify(record), rejected


async def run_assessment(
    *,
    repository_root: Path,
    repository_label: str,
    lanes: list[str] | None,
    settings: RiskReviewSettings,
    trace_path: Path | None,
    model: BaseLlm | None = None,
) -> AssessmentReport:
    started = datetime.now(UTC)
    report_id = started.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    lane_names = lanes or available_fact_lanes()
    semaphore = asyncio.Semaphore(settings.concurrency)
    manifests: dict[str, Manifest] = {}

    async def one(lane: str) -> LaneFacts:
        built = build_fact_finder(lane=lane, repository_root=repository_root, model=model)
        manifests.setdefault(built.spec.name, built.manifest)
        async with semaphore:
            result = await run_step_with_retry(
                built,
                run_id=f"{report_id}-{lane}",
                user_message=_fact_message(lane, repository_root),
                initial_state={LANE_KEY: lane},
                output_key=FACTS_KEY,
                output_model=FactsOutput,
                timeout_s=settings.step_timeout_s,
                trace_path=trace_path,
            )
        output = result.output
        return LaneFacts(
            lane=lane,
            status=output.status if output else result.metrics.outcome,
            metrics=result.metrics,
            facts=output.facts if output else [],
            files_examined=output.files_examined if output else [],
            notes=output.notes if output else None,
            error=result.error,
        )

    lane_results = list(await asyncio.gather(*(one(lane) for lane in lane_names)))
    facts = merge_facts(lane_results)
    record, rejected = build_record(facts, confirmed=False)
    confirmed_record, _ = build_record(facts, confirmed=True)
    return AssessmentReport(
        report_id=report_id,
        created_at=started.isoformat(timespec="seconds"),
        repository=repository_label,
        git_commit=git_commit(repository_root),
        lanes_requested=lane_names,
        manifests=manifests,
        lanes=lane_results,
        facts=facts,
        rejected_facts=rejected,
        assessment=record.assessment,
        residual_if_confirmed=confirmed_record.assessment.residual_risk.tier,
        open_questions=[spec.field for spec in open_gaps(record)],
        totals=compute_totals_from_metrics([lane.metrics for lane in lane_results], started),
    )


def report_as_dict(report: AssessmentReport) -> dict[str, Any]:
    return report.model_dump(mode="json")
