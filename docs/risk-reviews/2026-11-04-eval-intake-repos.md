> Sample of `make eval-intake EVAL_ARGS="--suite repos --concurrency 1"`: the fact-finder agents on the four fixture repositories, scored against gold facts. Two of the four "wrong" controls rows in earlier runs were gold errors the agents exposed (the claims repository states customers are told about the automated estimate and that names are dropped before training; the agent repository states commercial API terms); the gold now records them.

# Intake assessment eval `repos` — 20261104T183040Z-a86ba5

Model `openai/Qwen3.6-35B-A3B-NVFP4`, commit `49670db`, 4 cases x 1 run(s), dataset `565fcc0738cd`. Release: **BLOCKED**.

| Metric | Value |
| --- | --- |
| Pass rate (no false positive, no missed risk, both tiers exact) | 0.25 |
| Field accuracy (expected facts recorded correctly) | 0.88 |
| Confident accuracy (correct at ≥ 0.8, no question needed) | 0.71 |
| Risk false positives (share of runs affected) | 1 (0.25) |
| Control false positives (share of runs affected) | 1 (0.25) |
| Missed risks (share of runs affected) | 1 (0.25) |
| Unsupported confident values | 1 |
| Invalid field rate | 0.000 |
| Inherent tier exact / under | 1.00 / 0.00 |
| Residual tier exact / under | 0.75 / 0.00 |
| Latency p50 / p95 | 135.5 s / 291.0 s |
| Prompt tokens mean / p95 | 668005 / 1052570 |
| Completion tokens mean | 27976 |

## Gates

| Gate | Kind | Result | Detail |
| --- | --- | --- | --- |
| control_false_positives | hard | FAIL | 1.000 ≤ 0.000 |
| invalid_field_rate | hard | pass | 0.000 ≤ 0.020 |
| risk_false_positive_case_rate | quality | FAIL | 0.250 ≤ 0.100 |
| risk_missed_case_rate | quality | FAIL | 0.250 ≤ 0.100 |
| under_estimate_rate | quality | pass | 0.000 ≤ 0.050 |
| field_accuracy | quality | pass | 0.883 ≥ 0.850 |
| inherent_exact_rate | quality | pass | 1.000 ≥ 0.800 |
| residual_exact_rate | quality | FAIL | 0.750 ≥ 0.800 |
| pass_rate | quality | FAIL | 0.250 ≥ 0.700 |
| latency_p95_s | operational | pass | 291.035 ≤ 900.000 |
| prompt_tokens_p95 | operational | pass | 1052570.000 ≤ 2500000.000 |

## Cases

| Case | Pass | Acc | Risk FP | Ctrl FP | Missed | Inh | Res | Worst fields |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| repo-hr-screening | 0.00 | 0.95 | 0 | 0 | 0 | 1.00 | 0.00 | controls.in_place: wrong different; data.cross_border_transfer: unlisted riskier; data.trains_on_personal_data: unsupported different |
| repo-log-search | 0.00 | 0.76 | 1 | 0 | 1 | 1.00 | 1.00 | ai_system.autonomy_level: wrong riskier; controls.in_place: wrong different; data.data_sources: wrong different; use_case.interacts_directly_with_people: wrong safer |
| repo-claims-settlement | 0.00 | 0.86 | 0 | 1 | 0 | 1.00 | 1.00 | ai_system.fine_tuned_or_trained: wrong safer; controls.in_place: wrong different; use_case.domains: wrong riskier |
| repo-ops-agent | 1.00 | 0.94 | 0 | 0 | 0 | 1.00 | 1.00 | controls.in_place: wrong different; data.cross_border_transfer: unlisted riskier |
