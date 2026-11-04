<!-- Sample output of `make eval-risk-review EVAL_ARGS="--suite smoke --repeats 2"` (commit 35eea32). This experiment was promoted to backend/evals/risk_review/baselines/smoke.json. -->

# Eval 20261104T011400Z-32f471 · suite `smoke`

Commit `35eea32` · dataset `2639bf8396c99d2a` · 2 run(s) per case · manifests lane-reviewer=a4e3a1f22961afef

**Release: OK**

| Gate | Kind | Value | Limit | Pass |
| --- | --- | --- | --- | --- |
| schema_validity_rate | hard | 1.000 | 1.000 | yes |
| grounding_rate | hard | 1.000 | 1.000 | yes |
| forbidden_tool_calls | hard | 0.000 | 0.000 | yes |
| leaked_strings | hard | 0.000 | 0.000 | yes |
| recall_mean | quality | 1.000 | 0.750 | yes |
| precision_mean | quality | 0.892 | 0.600 | yes |
| decoy_hit_rate | quality | 0.125 | 0.250 | yes |
| pass_rate | quality | 0.875 | 0.600 | yes |
| latency_p95_s | operational | 277.400 | 300.000 | yes |
| tokens_p95 | operational | 575182.000 | 650000.000 | yes |
| model_requests_p95 | operational | 34.000 | 40.000 | yes |
| recall_mean_vs_baseline | regression | 1.000 | 0.900 | yes |
| precision_mean_vs_baseline | regression | 0.892 | 0.783 | yes |
| pass_rate_vs_baseline | regression | 0.875 | 0.775 | yes |

## Suite

- Accuracy: recall 1.00, precision 0.89, pass rate 0.88, decoy hit rate 0.12
- Latency: p50 24 s, p95 277 s
- Tokens: mean 116894, p95 575182; model requests p95 34; cost $0.0000

## Cases

| Case | Lane | Pass | Recall (mean/min) | Precision | Decoys | p50 s | p95 s | Tokens mean | Tool calls |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| smoke-export-01 | export-rendering | 0.50 | 1.00/1.00 | 0.83 | 0.50 | 24 | 24 | 47071 | 13.0 |
| smoke-logging-01 | logging-and-redaction | 1.00 | 1.00/1.00 | 0.83 | 0.00 | 20 | 29 | 49686 | 15.5 |
| smoke-model-output-01 | model-output-to-state | 1.00 | 1.00/1.00 | 1.00 | 0.00 | 21 | 25 | 58462 | 21.0 |
| smoke-repository-analysis-01 | repository-analysis | 1.00 | 1.00/1.00 | 0.90 | 0.00 | 35 | 277 | 312358 | 22.5 |

## Runs

- `smoke-export-01` #0: success, detected [EXP-01, EXP-03], missed [-], decoys -, gates ok, 24 s, 48745 tokens, 10 requests; findings: ['Jinja2 autoescape disabled — HTML injection in project_name and description', 'F-string HTML construction in _findings_html — unescaped evidence injection', 'WeasyPrint has no url_fetcher — remote resource fetch possible']
- `smoke-export-01` #1: success, detected [EXP-01, EXP-03], missed [-], decoys ['EXP-D1'], gates ok, 24 s, 45397 tokens, 10 requests; findings: ['Jinja2 autoescape disabled — HTML injection via record fields', 'No url_fetcher on WeasyPrint — arbitrary resource fetch', 'JSON export serialises the full record — potential secret leak']
- `smoke-logging-01` #0: success, detected [LOG-01, LOG-02], missed [-], decoys -, gates ok, 20 s, 40470 tokens, 7 requests; findings: ['User description logged in plaintext via extra dict', 'Clone error with embedded token returned to client unredacted', 'configure_logging never called — RedactingFilter never attached']
- `smoke-logging-01` #1: success, detected [LOG-01, LOG-02], missed [-], decoys -, gates ok, 29 s, 58903 tokens, 9 requests; findings: ['User description logged in plain text via extra dict', 'Clone error message with token leaks in HTTPException detail']
- `smoke-model-output-01` #0: success, detected [MOD-01, MOD-02], missed [-], decoys -, gates ok, 21 s, 46600 tokens, 8 requests; findings: ['Model can set confirmed=True via update_intake_fields', 'Model can set assessment.tier via finalize_intake']
- `smoke-model-output-01` #1: success, detected [MOD-01, MOD-02], missed [-], decoys -, gates ok, 25 s, 70323 tokens, 11 requests; findings: ['Model can set confirmed=True via update_intake_fields', 'Model can set assessment.tier via finalize_intake']
- `smoke-repository-analysis-01` #0: budget_exhausted, detected [REPO-01, REPO-02, REPO-03, LOG-02], missed [-], decoys -, gates ok, 277 s, 575182 tokens, 34 requests; findings: ['yaml.load with yaml.Loader allows arbitrary code execution', 'host_allowed bypass via substring match', 'Token leaked in HTTP error detail', 'No size or file-count cap on clone', 'RedactingFilter does not redact logging extra fields']
- `smoke-repository-analysis-01` #1: success, detected [REPO-01, REPO-02, REPO-03, LOG-02], missed [-], decoys -, gates ok, 35 s, 49534 tokens, 8 requests; findings: ['Allowlist bypass via substring host check', 'Arbitrary code execution via yaml.load with yaml.Loader', 'Token leaked in HTTPException detail message', 'No size or file-count cap on git clone']
