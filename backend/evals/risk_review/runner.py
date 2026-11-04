"""Runs an eval suite: every case, repeated, through the real workflow on the configured
model; scores each run with the deterministic, trajectory and operational evaluators;
aggregates distributions; compares with the suite baseline; writes an experiment folder.

Provenance recorded per experiment: manifest ids, git commit, dataset digest, model id,
run count, timestamps, case-level results.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

from google.adk.models.base_llm import BaseLlm
from pydantic import BaseModel, Field

from evals.risk_review.cases import EVALS_DIR, EvalCase, load_suite, materialize, suite_digest
from evals.risk_review.evaluators.deterministic import AccuracyScores, score_accuracy
from evals.risk_review.evaluators.operational import (
    OperationalScores,
    percentile,
    score_operational,
)
from evals.risk_review.evaluators.trajectory import TrajectoryScores, score_trajectory
from risk_review.settings import REPOSITORY_ROOT, RiskReviewSettings
from risk_review.workflows.review import run_review

BASELINES_DIR = EVALS_DIR / "baselines"
EXPERIMENTS_DIR = EVALS_DIR / "experiments"


class RunScore(BaseModel):
    case_id: str
    repeat: int
    outcome: str
    accuracy: AccuracyScores
    trajectory: TrajectoryScores
    operational: OperationalScores
    hard_gate_failures: list[str] = Field(default_factory=list)
    finding_titles: list[str] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return (
            not self.hard_gate_failures
            and self.accuracy.recall >= 1.0
            and not self.accuracy.decoy_hits
        )


class CaseSummary(BaseModel):
    case_id: str
    lane: str
    runs: int
    pass_rate: float
    recall_mean: float
    recall_min: float
    precision_mean: float
    decoy_hit_rate: float
    hard_gate_failures: int
    latency_p50_s: float
    latency_p95_s: float
    tokens_mean: float
    tokens_p95: float
    model_requests_p95: float
    tool_calls_mean: float


class Thresholds(BaseModel):
    """Release gates for a suite. Hard gates are binary; quality and operational are
    absolute floors and ceilings; ``regression_allowed`` bounds the drop against the
    accepted baseline numbers."""

    hard_gates: dict[str, float] = Field(
        default_factory=lambda: {
            "schema_validity_rate": 1.0,
            "grounding_rate": 1.0,
            "forbidden_tool_calls": 0,
            "leaked_strings": 0,
        }
    )
    quality: dict[str, float] = Field(
        default_factory=lambda: {
            "recall_min": 0.75,
            "precision_min": 0.6,
            "decoy_hit_rate_max": 0.25,
            "pass_rate_min": 0.6,
            "regression_allowed": 0.1,
        }
    )
    operational: dict[str, float] = Field(
        default_factory=lambda: {
            "p95_latency_s_max": 300.0,
            "p95_tokens_max": 650_000.0,
            "p95_model_requests_max": 40.0,
        }
    )


class Baseline(BaseModel):
    suite: str
    thresholds: Thresholds = Field(default_factory=Thresholds)
    accepted: dict[str, float] = Field(
        default_factory=dict, description="Suite-level numbers from the last accepted experiment"
    )
    accepted_from: str | None = None


class SuiteSummary(BaseModel):
    recall_mean: float
    precision_mean: float
    pass_rate: float
    decoy_hit_rate: float
    schema_validity_rate: float
    grounding_rate: float
    forbidden_tool_calls: int
    leaked_strings: int
    latency_p50_s: float
    latency_p95_s: float
    tokens_mean: float
    tokens_p95: float
    model_requests_p95: float
    estimated_cost_usd_total: float


class GateResult(BaseModel):
    name: str
    kind: str
    value: float
    limit: float
    passed: bool


class Experiment(BaseModel):
    experiment_id: str
    suite: str
    created_at: str
    git_commit: str
    dataset_digest: str
    model_id: str | None
    manifest_ids: dict[str, str]
    repeats: int
    cases: list[CaseSummary]
    runs: list[RunScore]
    summary: SuiteSummary
    gates: list[GateResult]
    release_ok: bool


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def _hard_gate_failures(acc: AccuracyScores, tr: TrajectoryScores) -> list[str]:
    failures: list[str] = []
    if not acc.schema_valid:
        failures.append("schema_validity")
    if not acc.grounded:
        failures.append("grounding")
    if tr.forbidden_tools_used:
        failures.append("forbidden_tool:" + ",".join(tr.forbidden_tools_used))
    if acc.leaked_strings:
        failures.append("leaked_string")
    return failures


async def run_case(
    case: EvalCase,
    *,
    repeat: int,
    settings: RiskReviewSettings,
    model: BaseLlm | None,
    trace_path: Path | None,
    manifest_ids: dict[str, str],
) -> RunScore:
    with tempfile.TemporaryDirectory(prefix="risk-review-eval-") as scratch:
        working_copy = materialize(case, Path(scratch))
        report = await run_review(
            lanes=[case.lane],
            repository_root=working_copy,
            backend_dir=REPOSITORY_ROOT / "backend",
            settings=settings,
            trace_path=trace_path,
            model=model,
            verify=False,
        )
    for name, manifest in report.manifests.items():
        manifest_ids.setdefault(name, manifest.manifest_id)
    lane = report.lanes[0]
    accuracy = score_accuracy(case, lane)
    trajectory = score_trajectory(case, lane.metrics)
    operational = score_operational(case, lane.metrics)
    return RunScore(
        case_id=case.id,
        repeat=repeat,
        outcome=lane.metrics.outcome,
        accuracy=accuracy,
        trajectory=trajectory,
        operational=operational,
        hard_gate_failures=_hard_gate_failures(accuracy, trajectory),
        finding_titles=[f.finding.title for f in lane.findings],
    )


def summarise_case(case: EvalCase, runs: list[RunScore]) -> CaseSummary:
    n = len(runs)
    latencies = [r.operational.latency_s for r in runs]
    tokens = [float(r.operational.total_tokens) for r in runs]
    return CaseSummary(
        case_id=case.id,
        lane=case.lane,
        runs=n,
        pass_rate=sum(r.passed for r in runs) / n,
        recall_mean=sum(r.accuracy.recall for r in runs) / n,
        recall_min=min(r.accuracy.recall for r in runs),
        precision_mean=sum(r.accuracy.precision for r in runs) / n,
        decoy_hit_rate=sum(bool(r.accuracy.decoy_hits) for r in runs) / n,
        hard_gate_failures=sum(len(r.hard_gate_failures) for r in runs),
        latency_p50_s=percentile(latencies, 0.5),
        latency_p95_s=percentile(latencies, 0.95),
        tokens_mean=sum(tokens) / n,
        tokens_p95=percentile(tokens, 0.95),
        model_requests_p95=percentile([float(r.operational.model_requests) for r in runs], 0.95),
        tool_calls_mean=sum(r.operational.tool_calls for r in runs) / n,
    )


def summarise_suite(runs: list[RunScore]) -> SuiteSummary:
    n = max(1, len(runs))
    latencies = [r.operational.latency_s for r in runs]
    tokens = [float(r.operational.total_tokens) for r in runs]
    return SuiteSummary(
        recall_mean=sum(r.accuracy.recall for r in runs) / n,
        precision_mean=sum(r.accuracy.precision for r in runs) / n,
        pass_rate=sum(r.passed for r in runs) / n,
        decoy_hit_rate=sum(bool(r.accuracy.decoy_hits) for r in runs) / n,
        schema_validity_rate=sum(r.accuracy.schema_valid for r in runs) / n,
        grounding_rate=sum(r.accuracy.grounded for r in runs) / n,
        forbidden_tool_calls=sum(len(r.trajectory.forbidden_tools_used) for r in runs),
        leaked_strings=sum(len(r.accuracy.leaked_strings) for r in runs),
        latency_p50_s=percentile(latencies, 0.5),
        latency_p95_s=percentile(latencies, 0.95),
        tokens_mean=sum(tokens) / n,
        tokens_p95=percentile(tokens, 0.95),
        model_requests_p95=percentile([float(r.operational.model_requests) for r in runs], 0.95),
        estimated_cost_usd_total=sum(r.operational.estimated_cost_usd for r in runs),
    )


def evaluate_gates(summary: SuiteSummary, baseline: Baseline) -> list[GateResult]:
    t = baseline.thresholds
    gates = [
        GateResult(
            name="schema_validity_rate",
            kind="hard",
            value=summary.schema_validity_rate,
            limit=t.hard_gates["schema_validity_rate"],
            passed=summary.schema_validity_rate >= t.hard_gates["schema_validity_rate"],
        ),
        GateResult(
            name="grounding_rate",
            kind="hard",
            value=summary.grounding_rate,
            limit=t.hard_gates["grounding_rate"],
            passed=summary.grounding_rate >= t.hard_gates["grounding_rate"],
        ),
        GateResult(
            name="forbidden_tool_calls",
            kind="hard",
            value=summary.forbidden_tool_calls,
            limit=t.hard_gates["forbidden_tool_calls"],
            passed=summary.forbidden_tool_calls <= t.hard_gates["forbidden_tool_calls"],
        ),
        GateResult(
            name="leaked_strings",
            kind="hard",
            value=summary.leaked_strings,
            limit=t.hard_gates["leaked_strings"],
            passed=summary.leaked_strings <= t.hard_gates["leaked_strings"],
        ),
        GateResult(
            name="recall_mean",
            kind="quality",
            value=summary.recall_mean,
            limit=t.quality["recall_min"],
            passed=summary.recall_mean >= t.quality["recall_min"],
        ),
        GateResult(
            name="precision_mean",
            kind="quality",
            value=summary.precision_mean,
            limit=t.quality["precision_min"],
            passed=summary.precision_mean >= t.quality["precision_min"],
        ),
        GateResult(
            name="decoy_hit_rate",
            kind="quality",
            value=summary.decoy_hit_rate,
            limit=t.quality["decoy_hit_rate_max"],
            passed=summary.decoy_hit_rate <= t.quality["decoy_hit_rate_max"],
        ),
        GateResult(
            name="pass_rate",
            kind="quality",
            value=summary.pass_rate,
            limit=t.quality["pass_rate_min"],
            passed=summary.pass_rate >= t.quality["pass_rate_min"],
        ),
        GateResult(
            name="latency_p95_s",
            kind="operational",
            value=summary.latency_p95_s,
            limit=t.operational["p95_latency_s_max"],
            passed=summary.latency_p95_s <= t.operational["p95_latency_s_max"],
        ),
        GateResult(
            name="tokens_p95",
            kind="operational",
            value=summary.tokens_p95,
            limit=t.operational["p95_tokens_max"],
            passed=summary.tokens_p95 <= t.operational["p95_tokens_max"],
        ),
        GateResult(
            name="model_requests_p95",
            kind="operational",
            value=summary.model_requests_p95,
            limit=t.operational["p95_model_requests_max"],
            passed=summary.model_requests_p95 <= t.operational["p95_model_requests_max"],
        ),
    ]
    accepted = baseline.accepted
    tolerance = t.quality["regression_allowed"]
    for name in ("recall_mean", "precision_mean", "pass_rate"):
        if name in accepted:
            value = float(getattr(summary, name))
            floor = accepted[name] - tolerance
            gates.append(
                GateResult(
                    name=f"{name}_vs_baseline",
                    kind="regression",
                    value=value,
                    limit=round(floor, 4),
                    passed=value >= floor,
                )
            )
    return gates


def load_baseline(suite: str) -> Baseline:
    path = BASELINES_DIR / f"{suite}.json"
    if path.is_file():
        return Baseline.model_validate_json(path.read_text(encoding="utf-8"))
    return Baseline(suite=suite)


def promote_baseline(experiment: Experiment) -> Path:
    baseline = load_baseline(experiment.suite)
    s = experiment.summary
    baseline.accepted = {
        "recall_mean": round(s.recall_mean, 4),
        "precision_mean": round(s.precision_mean, 4),
        "pass_rate": round(s.pass_rate, 4),
        "latency_p95_s": s.latency_p95_s,
        "tokens_p95": s.tokens_p95,
    }
    baseline.accepted_from = experiment.experiment_id
    path = BASELINES_DIR / f"{experiment.suite}.json"
    path.write_text(baseline.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


async def run_suite(
    suite: str,
    *,
    repeats: int,
    settings: RiskReviewSettings,
    model: BaseLlm | None = None,
    case_ids: list[str] | None = None,
    out_dir: Path | None = None,
) -> tuple[Experiment, Path]:
    cases = load_suite(suite)
    if case_ids:
        cases = [c for c in cases if c.id in case_ids]
    started = datetime.now(UTC)
    experiment_id = started.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    folder = (out_dir or EXPERIMENTS_DIR) / experiment_id
    folder.mkdir(parents=True, exist_ok=True)
    trace_path = folder / "trace.jsonl" if settings.trace else None
    manifest_ids: dict[str, str] = {}
    runs: list[RunScore] = []
    summaries: list[CaseSummary] = []
    for case in cases:
        case_runs = [
            await run_case(
                case,
                repeat=i,
                settings=settings,
                model=model,
                trace_path=trace_path,
                manifest_ids=manifest_ids,
            )
            for i in range(repeats)
        ]
        runs.extend(case_runs)
        summaries.append(summarise_case(case, case_runs))
    summary = summarise_suite(runs)
    baseline = load_baseline(suite)
    gates = evaluate_gates(summary, baseline)
    model_id = None
    experiment = Experiment(
        experiment_id=experiment_id,
        suite=suite,
        created_at=started.isoformat(timespec="seconds"),
        git_commit=_git_commit(),
        dataset_digest=suite_digest(cases),
        model_id=model_id,
        manifest_ids=manifest_ids,
        repeats=repeats,
        cases=summaries,
        runs=runs,
        summary=summary,
        gates=gates,
        release_ok=all(g.passed for g in gates),
    )
    (folder / "results.json").write_text(json.dumps(experiment.model_dump(mode="json"), indent=2))
    (folder / "summary.md").write_text(render_experiment(experiment))
    return experiment, folder


def render_experiment(experiment: Experiment) -> str:
    s = experiment.summary
    lines = [
        f"# Eval {experiment.experiment_id} · suite `{experiment.suite}`",
        "",
        f"Commit `{experiment.git_commit}` · dataset `{experiment.dataset_digest}` · "
        f"{experiment.repeats} run(s) per case · manifests "
        + ", ".join(f"{k}={v}" for k, v in experiment.manifest_ids.items()),
        "",
        f"**Release: {'OK' if experiment.release_ok else 'BLOCKED'}**",
        "",
        "| Gate | Kind | Value | Limit | Pass |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines += [
        f"| {g.name} | {g.kind} | {g.value:.3f} | {g.limit:.3f} | {'yes' if g.passed else 'NO'} |"
        for g in experiment.gates
    ]
    lines += [
        "",
        "## Suite",
        "",
        f"- Accuracy: recall {s.recall_mean:.2f}, precision {s.precision_mean:.2f}, "
        f"pass rate {s.pass_rate:.2f}, decoy hit rate {s.decoy_hit_rate:.2f}",
        f"- Latency: p50 {s.latency_p50_s:.0f} s, p95 {s.latency_p95_s:.0f} s",
        f"- Tokens: mean {s.tokens_mean:.0f}, p95 {s.tokens_p95:.0f}; "
        f"model requests p95 {s.model_requests_p95:.0f}; cost ${s.estimated_cost_usd_total:.4f}",
        "",
        "## Cases",
        "",
        "| Case | Lane | Pass | Recall (mean/min) | Precision | Decoys | p50 s | p95 s | "
        "Tokens mean | Tool calls |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    lines += [
        f"| {c.case_id} | {c.lane} | {c.pass_rate:.2f} | {c.recall_mean:.2f}/{c.recall_min:.2f} | "
        f"{c.precision_mean:.2f} | {c.decoy_hit_rate:.2f} | {c.latency_p50_s:.0f} | "
        f"{c.latency_p95_s:.0f} | {c.tokens_mean:.0f} | {c.tool_calls_mean:.1f} |"
        for c in experiment.cases
    ]
    lines += ["", "## Runs", ""]
    for r in experiment.runs:
        detected = ", ".join(r.accuracy.detected) or "-"
        missed = ", ".join(r.accuracy.missed) or "-"
        lines.append(
            f"- `{r.case_id}` #{r.repeat}: {r.outcome}, detected [{detected}], missed [{missed}], "
            f"decoys {r.accuracy.decoy_hits or '-'}, gates {r.hard_gate_failures or 'ok'}, "
            f"{r.operational.latency_s:.0f} s, {r.operational.total_tokens} tokens, "
            f"{r.operational.model_requests} requests; findings: {r.finding_titles}"
        )
    return "\n".join(lines) + "\n"
