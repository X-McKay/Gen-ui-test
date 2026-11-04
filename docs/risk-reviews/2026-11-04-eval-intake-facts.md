> Sample of `make eval-intake EVAL_ARGS="--suite facts --repeats 2"` on the local model after evidence grounding and the control vocabulary guard. Run concurrently with other load, so the latency numbers are pessimistic.

# Intake assessment eval `facts` — 20261104T161205Z-e0ce29

Model `openai/Qwen3.6-35B-A3B-NVFP4`, commit `73972c5`, 27 cases x 2 run(s), dataset `1e552214b8b4`. Release: **BLOCKED**.

| Metric | Value |
| --- | --- |
| Pass rate (no false positive, no missed risk, both tiers exact) | 0.74 |
| Field accuracy (expected facts recorded correctly) | 0.88 |
| Confident accuracy (correct at ≥ 0.8, no question needed) | 0.88 |
| Risk false positives (share of runs affected) | 10 (0.19) |
| Control false positives (share of runs affected) | 0 (0.00) |
| Missed risks (share of runs affected) | 0 (0.00) |
| Unsupported confident values | 21 |
| Invalid field rate | 0.000 |
| Inherent tier exact / under | 0.89 / 0.00 |
| Residual tier exact / under | 0.89 / 0.00 |
| Latency p50 / p95 | 20.6 s / 36.3 s |
| Prompt tokens mean / p95 | 6640 / 6666 |
| Completion tokens mean | 1196 |

## Gates

| Gate | Kind | Result | Detail |
| --- | --- | --- | --- |
| control_false_positives | hard | pass | 0.000 ≤ 0.000 |
| invalid_field_rate | hard | pass | 0.000 ≤ 0.020 |
| risk_false_positive_case_rate | quality | FAIL | 0.185 ≤ 0.100 |
| risk_missed_case_rate | quality | pass | 0.000 ≤ 0.100 |
| under_estimate_rate | quality | pass | 0.000 ≤ 0.050 |
| field_accuracy | quality | pass | 0.881 ≥ 0.850 |
| inherent_exact_rate | quality | pass | 0.889 ≥ 0.800 |
| residual_exact_rate | quality | pass | 0.889 ≥ 0.800 |
| pass_rate | quality | pass | 0.741 ≥ 0.700 |
| latency_p95_s | operational | FAIL | 36.265 ≤ 30.000 |
| prompt_tokens_p95 | operational | pass | 6666.000 ≤ 8000.000 |

## Cases

| Case | Pass | Acc | Risk FP | Ctrl FP | Missed | Inh | Res | Worst fields |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| genai-public-chatbot-guardrails | 0.50 | 0.97 | 0 | 0 | 0 | 1.00 | 0.50 | ai_system.fine_tuned_or_trained: unsupported different; ai_system.human_oversight: missing |
| genai-public-chatbot-no-controls | 1.00 | 0.82 | 0 | 0 | 0 | 1.00 | 1.00 | ai_system.human_oversight: missing; controls.in_place: missing; data.biometric_identification: missing; data.processes_personal_data: unsupported different |
| genai-internal-copilot | 1.00 | 0.81 | 0 | 0 | 0 | 1.00 | 1.00 | ai_system.human_oversight: missing; data.biometric_identification: missing; use_case.generates_synthetic_content: missing; use_case.interacts_directly_with_people: missing; use_case.social_scoring: missing |
| genai-hr-screening-pilot | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | — |
| genai-marketing-copy | 1.00 | 0.88 | 0 | 0 | 0 | 1.00 | 1.00 | ai_system.human_oversight: missing; ai_system.model_source: unsupported different; use_case.generates_synthetic_content: missing |
| genai-autonomous-refunds | 0.00 | 0.79 | 2 | 0 | 0 | 1.00 | 1.00 | ai_system.human_oversight: missing; data.biometric_identification: missing; use_case.affects_legal_or_significant_effects: wrong riskier |
| genai-medical-triage | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | — |
| ml-fraud-scoring | 0.00 | 1.00 | 0 | 0 | 0 | 0.00 | 1.00 | — |
| ml-demand-forecast | 1.00 | 0.90 | 0 | 0 | 0 | 1.00 | 1.00 | ai_system.model_source: unsupported different; data.biometric_identification: missing; use_case.generates_synthetic_content: missing |
| ml-credit-decisioning | 1.00 | 0.69 | 0 | 0 | 0 | 1.00 | 1.00 | ai_system.autonomy_level: missing; ai_system.human_oversight: missing; data.biometric_identification: missing; data.data_subjects: missing |
| noai-rules-engine | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | — |
| noai-dashboard-ai-in-name | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | ai_system.gpai_model_used: unsupported different |
| noai-replaced-model | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | data.processes_personal_data: unsupported different |
| pii-anonymised-logs | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | — |
| pii-employee-sentiment | 1.00 | 0.69 | 0 | 0 | 0 | 1.00 | 1.00 | ai_system.autonomy_level: missing; ai_system.human_oversight: missing; data.biometric_identification: missing; data.data_subjects: missing |
| pii-special-category-health | 1.00 | 0.55 | 0 | 0 | 0 | 1.00 | 1.00 | ai_system.autonomy_level: missing; ai_system.gpai_model_used: unsupported different; ai_system.human_oversight: missing; data.biometric_identification: missing; data.data_subjects: missing; data.special_category_data: missing |
| pii-minors-tutor | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | — |
| bio-face-access-control | 0.00 | 0.92 | 2 | 0 | 0 | 0.00 | 0.00 | use_case.domains: wrong riskier |
| bio-device-fingerprint-trap | 0.50 | 0.82 | 0 | 0 | 0 | 0.50 | 0.50 | data.special_category_data: missing; project.lifecycle_stage: missing; use_case.generates_synthetic_content: missing |
| bio-face-of-brand-trap | 1.00 | 0.92 | 0 | 0 | 0 | 1.00 | 1.00 | ai_system.human_oversight: missing |
| bio-voice-assistant-no-id | 0.00 | 0.87 | 2 | 0 | 0 | 1.00 | 0.00 | ai_system.human_oversight: unsupported different; controls.in_place: wrong different; use_case.domains: wrong riskier |
| plan-guardrails-roadmap | 0.50 | 0.91 | 1 | 0 | 0 | 1.00 | 1.00 | controls.in_place: missing; data.processes_personal_data: unsupported different; use_case.domains: wrong riskier |
| plan-mixed-controls | 0.50 | 0.97 | 1 | 0 | 0 | 0.50 | 1.00 | ai_system.autonomy_level: wrong riskier |
| plan-oversight-aspiration | 1.00 | 0.93 | 0 | 0 | 0 | 1.00 | 1.00 | ai_system.gpai_model_used: unsupported different; controls.in_place: missing |
| prohibited-social-scoring | 0.00 | 0.56 | 2 | 0 | 0 | 1.00 | 1.00 | ai_system.autonomy_level: missing; ai_system.gpai_model_used: unsupported different; data.biometric_identification: missing; data.data_subjects: missing; use_case.domains: wrong riskier |
| prohibited-fit-score-is-not-social-scoring | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | — |
| prohibited-emotion-at-work | 1.00 | 0.80 | 0 | 0 | 0 | 1.00 | 1.00 | ai_system.autonomy_level: missing; data.data_subjects: missing; data.special_category_data: missing |

