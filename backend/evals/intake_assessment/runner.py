"""Run a suite on the configured model, aggregate, gate against the baseline, promote."""

from __future__ import annotations

import asyncio
import statistics
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path

from google.adk.models.base_llm import BaseLlm
from pydantic import BaseModel, ConfigDict, Field

from app.inference.structured_extraction import ExtractedField, extract_fields_detailed
from app.settings import get_settings
from evals.intake_assessment.cases import (
    BACKEND_DIR,
    EVALS_DIR,
    AssessmentCase,
    load_suite,
    suite_digest,
)
from evals.intake_assessment.scoring import CaseScore, score_case
from evals.risk_review.evaluators.operational import percentile
from risk_review.settings import get_review_settings
from risk_review.workflows.assess import run_assessment

BASELINES_DIR = EVALS_DIR / "baselines"
EXPERIMENTS_DIR = EVALS_DIR / "experiments"
CONCURRENCY = 3


class Thresholds(BaseModel):
    """Hard gates block a release outright; quality and operational gates are compared with
    the accepted baseline numbers as well (a drop larger than ``regression_allowed`` blocks)."""

    model_config = ConfigDict(extra="forbid")

    # Hard
    control_false_positives_max: int = 0
    invalid_field_rate_max: float = 0.02
    # Quality (fractions)
    risk_false_positive_case_rate_max: float = 0.1
    risk_missed_case_rate_max: float = 0.1
    under_estimate_rate_max: float = 0.05
    field_accuracy_min: float = 0.85
    inherent_exact_min: float = 0.8
    residual_exact_min: float = 0.8
    pass_rate_min: float = 0.7
    regression_allowed: float = 0.1
    # Operational
    p95_latency_s_max: float = 30.0
    p95_prompt_tokens_max: int = 8000


class Baseline(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suite: str
    thresholds: Thresholds = Field(default_factory=Thresholds)
    accepted: dict[str, float] = Field(default_factory=dict)
    accepted_from: str | None = None


class CaseSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    tags: list[str]
    runs: int
    pass_rate: float
    field_accuracy: float
    risk_false_positives: int
    control_false_positives: int
    risks_missed: int
    unsupported: int
    inherent_exact_rate: float
    residual_exact_rate: float
    worst_fields: list[str]


class SuiteSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cases: int
    runs: int
    pass_rate: float
    field_accuracy: float
    confident_accuracy: float
    risk_false_positives: int
    risk_false_positive_case_rate: float
    control_false_positives: int
    control_false_positive_case_rate: float
    risks_missed: int
    risk_missed_case_rate: float
    risks_unanswered: int
    risk_unanswered_case_rate: float
    unsupported: int
    invalid_field_rate: float
    inherent_exact_rate: float
    inherent_under_rate: float
    residual_exact_rate: float
    residual_under_rate: float
    under_estimate_rate: float
    latency_p50_s: float
    latency_p95_s: float
    prompt_tokens_mean: float
    prompt_tokens_p95: float
    completion_tokens_mean: float


class GateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    kind: str
    passed: bool
    detail: str


class Experiment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment_id: str
    suite: str
    suite_digest: str
    created_at: str
    git_commit: str
    model_id: str
    repeats: int
    scores: list[CaseScore]
    cases: list[CaseSummary]
    summary: SuiteSummary
    gates: list[GateResult]
    release_ok: bool


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return out.stdout.strip()


async def run_case(case: AssessmentCase, *, model: BaseLlm | None = None) -> CaseScore:
    """A description goes through the product's extraction; a repository through the
    fact-finder agents. Both end as a list of extracted fields scored the same way."""
    if case.repository is not None:
        report = await run_assessment(
            repository_root=BACKEND_DIR / case.repository,
            repository_label=case.repository,
            lanes=None,
            settings=get_review_settings(),
            trace_path=None,
            model=model,
        )
        fields = [
            ExtractedField(
                path=fact.field,
                value=fact.value,
                confidence=fact.confidence,
                evidence=fact.evidence_quote,
            )
            for fact in report.facts
        ]
        return score_case(
            case,
            fields,
            latency_ms=report.totals.duration_ms,
            prompt_tokens=report.totals.input_tokens,
            completion_tokens=report.totals.output_tokens,
        )
    assert case.description is not None
    result = await extract_fields_detailed(case.description, context="project description")
    return score_case(
        case,
        result.fields,
        latency_ms=result.latency_ms,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def summarise_case(case: AssessmentCase, runs: list[CaseScore]) -> CaseSummary:
    expected = sum(r.expected_count for r in runs)
    worst = sorted(
        {
            f"{f.field}: {f.outcome}{' ' + f.direction if f.direction != 'same' else ''}"
            for r in runs
            for f in r.fields
            if f.outcome in {"wrong", "missing", "unsupported", "unlisted"}
        }
    )
    return CaseSummary(
        case_id=case.id,
        tags=case.tags,
        runs=len(runs),
        pass_rate=_mean([float(r.passed) for r in runs]),
        field_accuracy=(sum(r.correct_count for r in runs) / expected) if expected else 1.0,
        risk_false_positives=sum(r.risk_false_positives for r in runs),
        control_false_positives=sum(r.control_false_positives for r in runs),
        risks_missed=sum(r.risks_missed for r in runs),
        unsupported=sum(r.unsupported for r in runs),
        inherent_exact_rate=_mean([float(r.inherent.relation == "exact") for r in runs]),
        residual_exact_rate=_mean([float(r.residual.relation == "exact") for r in runs]),
        worst_fields=worst[:8],
    )


def summarise_suite(scores: list[CaseScore]) -> SuiteSummary:
    expected = sum(s.expected_count for s in scores)
    predicted_fields = sum(len(s.fields) for s in scores) + sum(
        len(s.invalid_fields) for s in scores
    )
    latencies = [s.latency_ms / 1000 for s in scores]
    prompt = [float(s.prompt_tokens) for s in scores if s.prompt_tokens is not None]
    completion = [float(s.completion_tokens) for s in scores if s.completion_tokens is not None]
    n = len(scores) or 1
    under = sum(
        1 for s in scores if s.inherent.relation == "under" or s.residual.relation == "under"
    )
    return SuiteSummary(
        cases=len({s.case_id for s in scores}),
        runs=len(scores),
        pass_rate=_mean([float(s.passed) for s in scores]),
        field_accuracy=(sum(s.correct_count for s in scores) / expected) if expected else 1.0,
        confident_accuracy=(sum(s.confident_correct_count for s in scores) / expected)
        if expected
        else 1.0,
        risk_false_positives=sum(s.risk_false_positives for s in scores),
        risk_false_positive_case_rate=sum(1 for s in scores if s.risk_false_positives) / n,
        control_false_positives=sum(s.control_false_positives for s in scores),
        control_false_positive_case_rate=sum(1 for s in scores if s.control_false_positives) / n,
        risks_missed=sum(s.risks_missed for s in scores),
        risk_missed_case_rate=sum(1 for s in scores if s.risks_missed) / n,
        risks_unanswered=sum(s.risks_unanswered for s in scores),
        risk_unanswered_case_rate=sum(1 for s in scores if s.risks_unanswered) / n,
        unsupported=sum(s.unsupported for s in scores),
        invalid_field_rate=(sum(len(s.invalid_fields) for s in scores) / predicted_fields)
        if predicted_fields
        else 0.0,
        inherent_exact_rate=_mean([float(s.inherent.relation == "exact") for s in scores]),
        inherent_under_rate=_mean([float(s.inherent.relation == "under") for s in scores]),
        residual_exact_rate=_mean([float(s.residual.relation == "exact") for s in scores]),
        residual_under_rate=_mean([float(s.residual.relation == "under") for s in scores]),
        under_estimate_rate=under / n,
        latency_p50_s=percentile(latencies, 0.5),
        latency_p95_s=percentile(latencies, 0.95),
        prompt_tokens_mean=_mean(prompt),
        prompt_tokens_p95=percentile(prompt, 0.95),
        completion_tokens_mean=_mean(completion),
    )


def evaluate_gates(summary: SuiteSummary, baseline: Baseline) -> list[GateResult]:
    t = baseline.thresholds
    gates: list[GateResult] = []

    def gate(name: str, kind: str, passed: bool, detail: str) -> None:
        gates.append(GateResult(name=name, kind=kind, passed=passed, detail=detail))

    def at_most(name: str, kind: str, value: float, limit: float) -> None:
        gate(name, kind, value <= limit, f"{value:.3f} ≤ {limit:.3f}")

    def at_least(name: str, kind: str, value: float, limit: float) -> None:
        gate(name, kind, value >= limit, f"{value:.3f} ≥ {limit:.3f}")

    at_most(
        "control_false_positives",
        "hard",
        summary.control_false_positives,
        t.control_false_positives_max,
    )
    at_most("invalid_field_rate", "hard", summary.invalid_field_rate, t.invalid_field_rate_max)
    at_most(
        "risk_false_positive_case_rate",
        "quality",
        summary.risk_false_positive_case_rate,
        t.risk_false_positive_case_rate_max,
    )
    at_most(
        "risk_missed_case_rate",
        "quality",
        summary.risk_missed_case_rate,
        t.risk_missed_case_rate_max,
    )
    at_most(
        "under_estimate_rate", "quality", summary.under_estimate_rate, t.under_estimate_rate_max
    )
    at_least("field_accuracy", "quality", summary.field_accuracy, t.field_accuracy_min)
    at_least("inherent_exact_rate", "quality", summary.inherent_exact_rate, t.inherent_exact_min)
    at_least("residual_exact_rate", "quality", summary.residual_exact_rate, t.residual_exact_min)
    at_least("pass_rate", "quality", summary.pass_rate, t.pass_rate_min)
    at_most("latency_p95_s", "operational", summary.latency_p95_s, t.p95_latency_s_max)
    at_most("prompt_tokens_p95", "operational", summary.prompt_tokens_p95, t.p95_prompt_tokens_max)

    for metric in ("pass_rate", "field_accuracy", "inherent_exact_rate", "residual_exact_rate"):
        accepted = baseline.accepted.get(metric)
        if accepted is None:
            continue
        value = float(getattr(summary, metric))
        gate(
            f"{metric}_vs_baseline",
            "regression",
            value >= accepted - t.regression_allowed,
            f"{value:.3f} vs accepted {accepted:.3f} (allowed drop {t.regression_allowed:.2f})",
        )
    return gates


def load_baseline(suite: str) -> Baseline:
    path = BASELINES_DIR / f"{suite}.json"
    if not path.is_file():
        return Baseline(suite=suite)
    return Baseline.model_validate_json(path.read_text())


def promote_baseline(experiment: Experiment) -> Path:
    if not experiment.release_ok:
        raise ValueError("refusing to promote a blocked experiment")
    baseline = load_baseline(experiment.suite)
    baseline.accepted = {
        "pass_rate": round(experiment.summary.pass_rate, 4),
        "field_accuracy": round(experiment.summary.field_accuracy, 4),
        "inherent_exact_rate": round(experiment.summary.inherent_exact_rate, 4),
        "residual_exact_rate": round(experiment.summary.residual_exact_rate, 4),
        "risk_false_positive_case_rate": round(experiment.summary.risk_false_positive_case_rate, 4),
        "latency_p95_s": round(experiment.summary.latency_p95_s, 2),
        "prompt_tokens_p95": round(experiment.summary.prompt_tokens_p95, 0),
    }
    baseline.accepted_from = experiment.experiment_id
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    path = BASELINES_DIR / f"{experiment.suite}.json"
    path.write_text(baseline.model_dump_json(indent=2) + "\n")
    return path


async def run_suite(
    suite: str,
    *,
    repeats: int = 1,
    case_ids: list[str] | None = None,
    out_dir: Path | None = None,
    concurrency: int = CONCURRENCY,
    model: BaseLlm | None = None,
) -> Experiment:
    cases = load_suite(suite)
    if case_ids:
        cases = [case for case in cases if case.id in set(case_ids)]
    semaphore = asyncio.Semaphore(concurrency)

    async def one(case: AssessmentCase) -> CaseScore:
        async with semaphore:
            return await run_case(case, model=model)

    scores = await asyncio.gather(*(one(case) for case in cases for _ in range(repeats)))
    by_case = {case.id: [s for s in scores if s.case_id == case.id] for case in cases}
    summary = summarise_suite(list(scores))
    baseline = load_baseline(suite)
    gates = evaluate_gates(summary, baseline)
    experiment = Experiment(
        experiment_id=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6],
        suite=suite,
        suite_digest=suite_digest(cases),
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        git_commit=_git_commit(),
        model_id="mock" if get_settings().mock_model else get_settings().model_id,
        repeats=repeats,
        scores=list(scores),
        cases=[summarise_case(case, by_case[case.id]) for case in cases],
        summary=summary,
        gates=gates,
        release_ok=all(g.passed for g in gates),
    )
    target = (out_dir or EXPERIMENTS_DIR) / experiment.experiment_id
    target.mkdir(parents=True, exist_ok=True)
    (target / "results.json").write_text(experiment.model_dump_json(indent=2))
    (target / "summary.md").write_text(render_experiment(experiment))
    return experiment


def render_experiment(e: Experiment) -> str:
    s = e.summary
    status = "OK" if e.release_ok else "BLOCKED"
    rows: list[tuple[str, str]] = [
        ("Pass rate (no false positive, no missed risk, both tiers exact)", f"{s.pass_rate:.2f}"),
        ("Field accuracy (expected facts recorded correctly)", f"{s.field_accuracy:.2f}"),
        (
            "Confident accuracy (correct at ≥ 0.8, no question needed)",
            f"{s.confident_accuracy:.2f}",
        ),
        (
            "Risk false positives (share of runs affected)",
            f"{s.risk_false_positives} ({s.risk_false_positive_case_rate:.2f})",
        ),
        (
            "Control false positives (share of runs affected)",
            f"{s.control_false_positives} ({s.control_false_positive_case_rate:.2f})",
        ),
        (
            "Missed risks (share of runs affected)",
            f"{s.risks_missed} ({s.risk_missed_case_rate:.2f})",
        ),
        ("Unsupported confident values", str(s.unsupported)),
        ("Invalid field rate", f"{s.invalid_field_rate:.3f}"),
        (
            "Inherent tier exact / under",
            f"{s.inherent_exact_rate:.2f} / {s.inherent_under_rate:.2f}",
        ),
        (
            "Residual tier exact / under",
            f"{s.residual_exact_rate:.2f} / {s.residual_under_rate:.2f}",
        ),
        ("Latency p50 / p95", f"{s.latency_p50_s:.1f} s / {s.latency_p95_s:.1f} s"),
        ("Prompt tokens mean / p95", f"{s.prompt_tokens_mean:.0f} / {s.prompt_tokens_p95:.0f}"),
        ("Completion tokens mean", f"{s.completion_tokens_mean:.0f}"),
    ]
    lines = [
        f"# Intake assessment eval `{e.suite}` — {e.experiment_id}",
        "",
        f"Model `{e.model_id}`, commit `{e.git_commit}`, {s.cases} cases x {e.repeats} run(s), "
        f"dataset `{e.suite_digest}`. Release: **{status}**.",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        *(f"| {name} | {value} |" for name, value in rows),
        "",
        "## Gates",
        "",
        "| Gate | Kind | Result | Detail |",
        "| --- | --- | --- | --- |",
        *(
            f"| {g.name} | {g.kind} | {'pass' if g.passed else 'FAIL'} | {g.detail} |"
            for g in e.gates
        ),
        "",
        "## Cases",
        "",
        "| Case | Pass | Acc | Risk FP | Ctrl FP | Missed | Inh | Res | Worst fields |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for c in e.cases:
        worst = "; ".join(c.worst_fields) or "—"
        lines.append(
            f"| {c.case_id} | {c.pass_rate:.2f} | {c.field_accuracy:.2f} "
            f"| {c.risk_false_positives} | {c.control_false_positives} | {c.risks_missed} "
            f"| {c.inherent_exact_rate:.2f} | {c.residual_exact_rate:.2f} | {worst} |"
        )
    return "\n".join(lines) + "\n"
