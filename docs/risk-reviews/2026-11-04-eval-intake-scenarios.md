> Sample of `make eval-intake EVAL_ARGS="--suite scenarios --repeats 2"`: the second batch of 27 use-cases (agentic automation, retrieval, critical infrastructure, insurance, legal, education, law enforcement, migration, media, marketing, security operations, healthcare, trading, public services, children, accessibility, workforce management, with traps for specific false positives). Unseen, this suite started at pass 0.44 with risk false positives in 26 % of runs; the hint, vocabulary and completion-pass changes brought it here. The remaining tier disagreements are capped values (confidence 0.6) that become confirmation questions, not confident errors.

# Intake assessment eval `scenarios` — 20261104T184211Z-097fac

Model `openai/Qwen3.6-35B-A3B-NVFP4`, commit `49670db`, 27 cases x 2 run(s), dataset `713c24196323`. Release: **BLOCKED**.

| Metric | Value |
| --- | --- |
| Pass rate (no false positive, no missed risk, both tiers exact) | 0.72 |
| Field accuracy (expected facts recorded correctly) | 0.95 |
| Confident accuracy (correct at ≥ 0.8, no question needed) | 0.95 |
| Risk false positives (share of runs affected) | 0 (0.00) |
| Control false positives (share of runs affected) | 0 (0.00) |
| Missed risks (share of runs affected) | 2 (0.04) |
| Unsupported confident values | 0 |
| Invalid field rate | 0.000 |
| Inherent tier exact / under | 0.87 / 0.02 |
| Residual tier exact / under | 0.80 / 0.02 |
| Latency p50 / p95 | 19.7 s / 23.6 s |
| Prompt tokens mean / p95 | 7488 / 11667 |
| Completion tokens mean | 1590 |

## Gates

| Gate | Kind | Result | Detail |
| --- | --- | --- | --- |
| control_false_positives | hard | pass | 0.000 ≤ 0.000 |
| invalid_field_rate | hard | pass | 0.000 ≤ 0.020 |
| risk_false_positive_case_rate | quality | pass | 0.000 ≤ 0.100 |
| risk_missed_case_rate | quality | pass | 0.037 ≤ 0.100 |
| under_estimate_rate | quality | pass | 0.019 ≤ 0.050 |
| field_accuracy | quality | pass | 0.953 ≥ 0.850 |
| inherent_exact_rate | quality | pass | 0.870 ≥ 0.800 |
| residual_exact_rate | quality | FAIL | 0.796 ≥ 0.800 |
| pass_rate | quality | pass | 0.722 ≥ 0.700 |
| latency_p95_s | operational | pass | 23.637 ≤ 30.000 |
| prompt_tokens_p95 | operational | FAIL | 11667.000 ≤ 8000.000 |

## Cases

| Case | Pass | Acc | Risk FP | Ctrl FP | Missed | Inh | Res | Worst fields |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| agent-it-ticket-remediation | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | — |
| agent-procurement-orders | 1.00 | 0.92 | 0 | 0 | 0 | 1.00 | 1.00 | controls.in_place: missing |
| rag-hr-policy-assistant | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | — |
| ops-predictive-maintenance | 1.00 | 0.92 | 0 | 0 | 0 | 1.00 | 1.00 | use_case.generates_synthetic_content: missing; use_case.interacts_directly_with_people: missing |
| ops-grid-load-shedding | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | ai_system.fine_tuned_or_trained: unlisted riskier |
| legal-contract-clause-extraction | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | — |
| ins-claims-auto-settlement | 0.00 | 0.93 | 0 | 0 | 0 | 1.00 | 0.00 | data.trains_on_personal_data: unlisted riskier; use_case.domains: wrong riskier |
| ins-health-premium-pricing | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | — |
| edu-essay-grading | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | — |
| edu-proctoring-stress-detection | 1.00 | 0.94 | 0 | 0 | 0 | 1.00 | 1.00 | ai_system.autonomy_level: unlisted riskier; data.special_category_data: wrong riskier; use_case.interacts_directly_with_people: unlisted riskier |
| le-station-live-face-matching | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | ai_system.autonomy_level: unlisted riskier |
| le-interview-transcription | 0.00 | 1.00 | 0 | 0 | 0 | 1.00 | 0.00 | — |
| mig-visa-application-ranking | 0.00 | 0.89 | 0 | 0 | 0 | 1.00 | 0.00 | data.biometric_identification: missing; project.target_users: unlisted riskier |
| media-voice-clone-adverts | 0.00 | 0.92 | 0 | 0 | 2 | 1.00 | 1.00 | ai_system.gpai_model_used: wrong safer |
| media-manual-translation | 0.00 | 0.92 | 0 | 0 | 0 | 0.00 | 1.00 | project.target_users: missing |
| mkt-offer-targeting | 0.50 | 0.74 | 0 | 0 | 0 | 0.50 | 0.50 | ai_system.autonomy_level: missing; ai_system.fine_tuned_or_trained: missing; ai_system.human_oversight: missing; ai_system.model_source: missing; data.biometric_identification: missing; data.data_subjects: missing; data.special_category_data: missing; data.trains_on_personal_data: missing |
| mkt-checkout-assistant-persuasion-trap | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | — |
| sec-network-intrusion-blocking | 0.00 | 0.92 | 0 | 0 | 0 | 0.00 | 0.00 | ai_system.fine_tuned_or_trained: unlisted riskier; use_case.domains: wrong riskier |
| health-ct-nodule-flagging | 1.00 | 0.96 | 0 | 0 | 0 | 1.00 | 1.00 | ai_system.fine_tuned_or_trained: unlisted riskier; controls.in_place: missing; data.trains_on_personal_data: unlisted riskier |
| health-step-goal-app-trap | 1.00 | 0.89 | 0 | 0 | 0 | 1.00 | 1.00 | ai_system.autonomy_level: unlisted riskier; project.target_users: missing; use_case.interacts_directly_with_people: unlisted riskier |
| fin-algorithmic-trading | 1.00 | 0.92 | 0 | 0 | 0 | 1.00 | 1.00 | ai_system.fine_tuned_or_trained: unlisted riskier; project.target_users: missing |
| pub-benefits-prechecker | 1.00 | 0.93 | 0 | 0 | 0 | 1.00 | 1.00 | controls.in_place: wrong different |
| kids-companion-toy | 0.00 | 1.00 | 0 | 0 | 0 | 0.00 | 0.00 | ai_system.autonomy_level: unlisted riskier |
| access-live-captions-trap | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | — |
| hr-productivity-scoring | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | ai_system.fine_tuned_or_trained: unlisted riskier; data.trains_on_personal_data: unlisted riskier |
| hr-shift-rostering | 1.00 | 0.97 | 0 | 0 | 0 | 1.00 | 1.00 | ai_system.fine_tuned_or_trained: unlisted riskier; project.target_users: missing |
| noai-invoice-threshold-script | 1.00 | 1.00 | 0 | 0 | 0 | 1.00 | 1.00 | ai_system.autonomy_level: unlisted riskier |
