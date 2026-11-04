> Sample of `make eval-intake EVAL_ARGS="--repeats 2"`: the original 27 descriptions after the vetting round (see `2026-11-04-eval-intake-scenarios.md`).

# Intake assessment eval `facts` — 20261104T183615Z-3c1470

Model `openai/Qwen3.6-35B-A3B-NVFP4`, commit `49670db`, 27 cases x 2 run(s), dataset `5cda51d90672`. Release: **BLOCKED**.

| Metric | Value |
| --- | --- |
| Pass rate (no false positive, no missed risk, both tiers exact) | 0.70 |
| Field accuracy (expected facts recorded correctly) | 0.95 |
| Confident accuracy (correct at ≥ 0.8, no question needed) | 0.93 |
| Risk false positives (share of runs affected) | 3 (0.06) |
| Control false positives (share of runs affected) | 0 (0.00) |
| Missed risks (share of runs affected) | 0 (0.00) |
| Unsupported confident values | 23 |
| Invalid field rate | 0.000 |
| Inherent tier exact / under | 0.83 / 0.00 |
| Residual tier exact / under | 0.76 / 0.00 |
| Latency p50 / p95 | 18.5 s / 23.5 s |
| Prompt tokens mean / p95 | 7302 / 7177 |
| Completion tokens mean | 1476 |

## Gates

| Gate | Kind | Result | Detail |
| --- | --- | --- | --- |
| control_false_positives | hard | pass | 0.000 ≤ 0.000 |
| invalid_field_rate | hard | pass | 0.000 ≤ 0.020 |
| risk_false_positive_case_rate | quality | pass | 0.056 ≤ 0.100 |
| risk_missed_case_rate | quality | pass | 0.000 ≤ 0.100 |
| under_estimate_rate | quality | pass | 0.000 ≤ 0.050 |
| field_accuracy | quality | pass | 0.953 ≥ 0.850 |
| inherent_exact_rate | quality | pass | 0.833 ≥ 0.800 |
| residual_exact_rate | quality | FAIL | 0.759 ≥ 0.800 |
| pass_rate | quality | pass | 0.704 ≥ 0.700 |
| latency_p95_s | operational | pass | 23.541 ≤ 30.000 |
| prompt_tokens_p95 | operational | pass | 7177.000 ≤ 8000.000 |

## Cases

| Case | Pass | Acc | Risk FP | Ctrl FP | Missed | Inh | Res | Worst fields |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| genai-public-chatbot-guardrails | 0.00 | 1.00 | 0 | 0 | 0 | 1.00 | 0.00 | ai_system.fine_tuned_or_trained: unsupported different |
| genai-public-chatbot-no-controls | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | data.processes_personal_data: unsupported different |
| genai-internal-copilot | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | — |
| genai-hr-screening-pilot | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | — |
| genai-marketing-copy | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | ai_system.model_source: unsupported different |
| genai-autonomous-refunds | 0.00 | 0.86 | 0 | 0 | 0 | 0.00 | 0.00 | controls.in_place: missing; use_case.affects_legal_or_significant_effects: wrong riskier |
| genai-medical-triage | 1.00 | 0.93 | 0 | 0 | 0 | 1.00 | 1.00 | data.trains_on_personal_data: unlisted riskier; use_case.domains: missing; use_case.generates_synthetic_content: unlisted riskier |
| ml-fraud-scoring | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | — |
| ml-demand-forecast | 1.00 | 0.90 | 0 | 0 | 0 | 1.00 | 1.00 | ai_system.autonomy_level: unlisted riskier; ai_system.model_source: unsupported different; use_case.generates_synthetic_content: missing |
| ml-credit-decisioning | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | — |
| noai-rules-engine | 0.00 | 1.00 | 0 | 0 | 0 | 0.00 | 1.00 | ai_system.autonomy_level: unsupported different |
| noai-dashboard-ai-in-name | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | — |
| noai-replaced-model | 0.00 | 1.00 | 0 | 0 | 0 | 0.00 | 0.00 | ai_system.autonomy_level: unlisted riskier; data.processes_personal_data: unsupported different |
| pii-anonymised-logs | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | — |
| pii-employee-sentiment | 0.50 | 0.96 | 1 | 0 | 0 | 1.00 | 1.00 | data.special_category_data: wrong riskier |
| pii-special-category-health | 0.00 | 0.82 | 2 | 0 | 0 | 1.00 | 0.00 | ai_system.autonomy_level: wrong riskier; ai_system.gpai_model_used: unsupported different; project.lifecycle_stage: missing |
| pii-minors-tutor | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | ai_system.human_oversight: unsupported different; data.cross_border_transfer: unlisted riskier |
| bio-face-access-control | 0.00 | 0.96 | 0 | 0 | 0 | 0.00 | 0.00 | project.lifecycle_stage: missing |
| bio-device-fingerprint-trap | 0.50 | 0.91 | 0 | 0 | 0 | 0.50 | 0.50 | ai_system.autonomy_level: unlisted riskier; project.lifecycle_stage: missing |
| bio-face-of-brand-trap | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | — |
| bio-voice-assistant-no-id | 0.00 | 0.89 | 0 | 0 | 0 | 1.00 | 0.00 | ai_system.human_oversight: unsupported different; controls.in_place: wrong different; project.lifecycle_stage: missing |
| plan-guardrails-roadmap | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | data.processes_personal_data: unsupported different |
| plan-mixed-controls | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | use_case.interacts_directly_with_people: unlisted riskier |
| plan-oversight-aspiration | 1.00 | 0.93 | 0 | 0 | 0 | 1.00 | 1.00 | ai_system.gpai_model_used: unsupported different; controls.in_place: missing |
| prohibited-social-scoring | 1.00 | 0.81 | 0 | 0 | 0 | 1.00 | 1.00 | ai_system.autonomy_level: missing; ai_system.gpai_model_used: unsupported different; data.biometric_identification: missing; data.data_subjects: missing |
| prohibited-fit-score-is-not-social-scoring | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | — |
| prohibited-emotion-at-work | 1.00 | 0.70 | 0 | 0 | 0 | 1.00 | 1.00 | ai_system.autonomy_level: missing; data.data_subjects: missing; data.special_category_data: missing |
