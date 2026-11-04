> Sample of `make eval-intake EVAL_ARGS="--suite repos --concurrency 1"`: the fact-finder agents on the two fixture repositories, scored against gold facts.

# Intake assessment eval `repos` — 20261104T161355Z-9f6a8d

Model `openai/Qwen3.6-35B-A3B-NVFP4`, commit `23beca6`, 2 cases x 1 run(s), dataset `d2e806638053`. Release: **BLOCKED**.

| Metric | Value |
| --- | --- |
| Pass rate (no false positive, no missed risk, both tiers exact) | 0.00 |
| Field accuracy (expected facts recorded correctly) | 0.89 |
| Confident accuracy (correct at ≥ 0.8, no question needed) | 0.65 |
| Risk false positives (share of runs affected) | 1 (0.50) |
| Control false positives (share of runs affected) | 0 (0.00) |
| Missed risks (share of runs affected) | 1 (0.50) |
| Unsupported confident values | 2 |
| Invalid field rate | 0.000 |
| Inherent tier exact / under | 0.50 / 0.00 |
| Residual tier exact / under | 0.50 / 0.00 |
| Latency p50 / p95 | 261.6 s / 289.1 s |
| Prompt tokens mean / p95 | 597109 / 688149 |
| Completion tokens mean | 27496 |

## Gates

| Gate | Kind | Result | Detail |
| --- | --- | --- | --- |
| control_false_positives | hard | pass | 0.000 ≤ 0.000 |
| invalid_field_rate | hard | pass | 0.000 ≤ 0.020 |
| risk_false_positive_case_rate | quality | FAIL | 0.500 ≤ 0.100 |
| risk_missed_case_rate | quality | FAIL | 0.500 ≤ 0.100 |
| under_estimate_rate | quality | pass | 0.000 ≤ 0.050 |
| field_accuracy | quality | pass | 0.892 ≥ 0.850 |
| inherent_exact_rate | quality | FAIL | 0.500 ≥ 0.800 |
| residual_exact_rate | quality | FAIL | 0.500 ≥ 0.800 |
| pass_rate | quality | FAIL | 0.000 ≥ 0.700 |
| latency_p95_s | operational | pass | 289.081 ≤ 900.000 |
| prompt_tokens_p95 | operational | pass | 688149.000 ≤ 2500000.000 |

## Cases

| Case | Pass | Acc | Risk FP | Ctrl FP | Missed | Inh | Res | Worst fields |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| repo-hr-screening | 0.00 | 0.95 | 0 | 0 | 1 | 1.00 | 1.00 | data.trains_on_personal_data: unsupported different; use_case.generates_synthetic_content: wrong safer |
| repo-log-search | 0.00 | 0.81 | 1 | 0 | 0 | 0.00 | 0.00 | ai_system.autonomy_level: wrong riskier; controls.in_place: wrong different; data.data_sources: wrong different; data.retention_policy: unsupported different |

