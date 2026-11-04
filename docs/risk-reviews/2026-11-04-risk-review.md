<!-- Sample output of `make risk-review` (commit 35eea32, local model Qwen3.6-35B-A3B-NVFP4, six lanes, verification on). Regenerate with `make risk-review`; live output lands in reports/risk-review/. -->

# Risk review 20261104T012224Z-86dc83

Commit `35eea32` · 2026-11-04T01:22:24+00:00 · lanes: api-and-persistence, export-rendering, frontend-trust, logging-and-redaction, model-output-to-state, repository-analysis

| Metric | Value |
| --- | --- |
| Findings | 6 (confirmed 4, refuted 1, uncertain 0, unverified 1) |
| Wall time | 513 s |
| Model requests | 222 |
| Tokens in / out / thinking | 4403251 / 58729 / 0 |
| Tool calls | 300 |
| Estimated cost | $0.0000 |
| Budget violations | 5 |

## Lanes

| Lane | Status | Findings | Requests | Tokens in/out | Tool calls | Time |
| --- | --- | --- | --- | --- | --- | --- |
| api-and-persistence | completed | 2 | 21 | 627744/5200 | 37 | 151 s |
| export-rendering | completed | 0 | 36 | 655750/4987 | 36 | 156 s |
| frontend-trust | completed | 1 | 18 | 454603/4775 | 37 | 137 s |
| logging-and-redaction | completed | 3 | 22 | 676936/5613 | 38 | 145 s |
| model-output-to-state | completed | 0 | 16 | 417874/14158 | 25 | 268 s |
| repository-analysis | completed | 0 | 41 | 1140203/13363 | 41 | 265 s |

## Findings

### [high] HTTPException detail leaks exception message without redaction

- Lane: `logging-and-redaction` · Category: `token-in-error` · Verdict: **confirmed** · Reviewer confidence 0.90
- Location: `backend/app/api/exports.py:85`
- Invariant: Tokens and credentials are stripped from error messages returned to clients (redact_secrets, logging_config.redact).
- Failure scenario: A webhook delivery fails with an httpx.TransportError whose str() contains a URL with embedded credentials or headers. The exception message is passed directly as HTTPException(detail=str(error)) on line 85, reaching the client without any redaction.
- Evidence:
  - `backend/app/api/exports.py:85` `raise HTTPException(status_code=502, detail=str(error)) from error`
  - `backend/app/export/webhook.py:34` `last_error = f"connection error ({error.__class__.__name__}: {error})"`
  - `backend/app/export/webhook.py:43` `raise WebhookDeliveryError(`
- Proposed test: Mock httpx.AsyncClient.post to raise httpx.ConnectError with a message containing a token-like string, call submit_intake, and assert the HTTP 502 response detail does not contain the raw token.
- Verifier (0.90): Traced the full path: (1) deliver_webhook (webhook.py:34) catches httpx.TransportError and formats the exception's str() into last_error, including the raw error message which may contain credentials in URLs. (2) After retries, it raises WebhookDeliveryError with that message (webhook.py:43-45). (3) submit_intake (exports.py:85) catches WebhookDeliveryError and raises HTTPException with detail=str(error) — no redaction is applied. (4) No middleware or exception handler in main.py redacts HTTPException details before sending to the client. (5) The redact_secrets function exists but is only used in the repo_analysis module, not in the webhook/exports path. (6) The existing test (test_exports_api.py:186) only checks for status code and generic message fragments — it does not test that secrets are redacted from transport error messages.
  - `backend/app/api/exports.py:85` `raise HTTPException(status_code=502, detail=str(error)) from error`
  - `backend/app/export/webhook.py:34` `last_error = f"connection error ({error.__class__.__name__}: {error})"`
  - `backend/app/export/webhook.py:43` `raise WebhookDeliveryError(`
  - `backend/app/repo_analysis/clone_repository.py:99` `def redact_secrets(text: str, extra_secrets: Sequence[str] = ()) -> str:`
  - `backend/tests/export/test_exports_api.py:196` `assert response.status_code == 502`

### [medium] Intake IDs are truncated UUID4 hex (48 bits), making them brute-forceable

- Lane: `api-and-persistence` · Category: `guessable-id` · Verdict: **confirmed** · Reviewer confidence 0.90
- Location: `backend/app/intake/record_service.py:47`
- Invariant: Every intake is reachable only by its unguessable id.
- Failure scenario: An attacker can brute-force 12-hex-char IDs (16^12 ≈ 281 trillion combinations). While not trivial, this is orders of magnitude weaker than full UUID4 (2^122) and could be enumerated to discover existing intakes, especially if intake count is low.
- Evidence:
  - `backend/app/intake/record_service.py:47` `record = new_record(intake_id or uuid.uuid4().hex[:12], mode)`
  - `backend/app/api/intakes.py:90` `@router.get("/intakes/{intake_id}")`
  - `backend/app/api/exports.py:46` `@router.get("/intakes/{intake_id}/export.json", response_class=Response)`
  - `backend/app/api/repositories.py:86` `@router.get("/intakes/{intake_id}/findings", response_model=list[RepositoryFindingDto])`
- Proposed test: Create an intake, extract its 12-char hex id, then attempt to guess nearby ids by incrementing the hex value and verify whether any valid intake is returned.
- Verifier (0.90): I traced the full path: (1) intake IDs are generated as uuid4().hex[:12] at record_service.py:47, producing 12 hex characters (48 bits of entropy). (2) Multiple public API endpoints (intakes.py:90, exports.py:46, repositories.py:86) accept intake_id as a path parameter and look it up directly in the store, returning 404 if not found. (3) No rate limiting exists on these endpoints — the only rate limiter in main.py covers the agent endpoint only. (4) No input validation constrains the intake_id format. (5) No existing tests cover brute-force guessing of intake IDs. The scenario is reachable: an attacker can enumerate 12-hex-char IDs to discover existing intakes.
  - `backend/app/intake/record_service.py:47` `record = new_record(intake_id or uuid.uuid4().hex[:12], mode)`
  - `backend/app/api/intakes.py:90` `@router.get("/intakes/{intake_id}")`
  - `backend/app/api/exports.py:46` `@router.get("/intakes/{intake_id}/export.json", response_class=Response)`
  - `backend/app/api/repositories.py:86` `@router.get("/intakes/{intake_id}/findings", response_model=list[RepositoryFindingDto])`
  - `backend/app/intake/record_service.py:56` `def get_record(intake_id: str) -> IntakeRecord:`

### [medium] extra dict values in logger calls are not redacted

- Lane: `logging-and-redaction` · Category: `redaction-gap` · Verdict: **confirmed** · Reviewer confidence 0.70
- Location: `backend/app/agents/tools/context.py:74`
- Invariant: Tokens and credentials are stripped from log lines and from error messages returned to clients.
- Failure scenario: tool_error is called with a message containing sensitive data. The logger.warning call passes extra={'detail': message}, and RequestIdFilter only redacts record.msg (logging_config.py line 32), never touching extra dict values.
- Evidence:
  - `backend/app/agents/tools/context.py:74` `logger.warning("tool.error", extra={"detail": message})`
  - `backend/app/logging_config.py:32` `record.msg = redact(record.msg)`
  - `backend/app/agents/tools/extract_intake_facts.py:28` `return tool_error(f"intake not found: {error}")`
- Proposed test: Call tool_error with a message containing a GitHub token pattern (ghp_xxxxxxxxxxxx) and verify the log output does not contain the raw token.
- Verifier (0.90): I traced the full path and found no guard. The `tool_error` function at context.py:73-75 calls `logger.warning("tool.error", extra={"detail": message})` where `message` is passed directly into the `extra` dict. The `RequestIdFilter` in logging_config.py:28-33 only redacts `record.msg` (line 32: `record.msg = redact(record.msg)`), never touching `record.extra` or the `extra` dict values. The `message` parameter is also returned directly in the response dict at line 75: `return {"status": "error", "error": message, **extra}`. There is no redaction applied to the response before it's sent to the client. The callers (extract_intake_facts.py:28, finalize_intake.py:25, get_next_questions.py:65, update_intake_fields.py:44,47) all pass error messages that could contain sensitive data (e.g., from exception messages). No existing test covers this scenario.
  - `backend/app/agents/tools/context.py:74` `logger.warning("tool.error", extra={"detail": message})`
  - `backend/app/agents/tools/context.py:75` `return {"status": "error", "error": message, **extra}`
  - `backend/app/logging_config.py:32` `record.msg = redact(record.msg)`
  - `backend/app/agents/tools/extract_intake_facts.py:28` `return tool_error(f"intake not found: {error}")`
  - `backend/app/logging_config.py:28` `class RequestIdFilter(logging.Filter):`

### [low] Repository access token from request body is never persisted to the database

- Lane: `api-and-persistence` · Category: `secret-persisted` · Verdict: **confirmed** · Reviewer confidence 0.90
- Location: `backend/app/api/repositories.py:69`
- Invariant: Secrets never land in the database or in responses.
- Failure scenario: The access_token from the AnalyzeRepositoryRequest body is used only in-memory for git clone operations and is never stored in the IntakeRecord, IntakeRow, RepositoryFindingsRow, or any other persisted model. The token is also redacted in error messages via redact_secrets(). No secret persistence risk.
- Evidence:
  - `backend/app/api/repositories.py:69` `token = body.access_token.strip() if body.access_token else None`
  - `backend/app/repo_analysis/analysis_job.py:225` `token = access_token or settings.repo_access_token`
  - `backend/app/repo_analysis/analysis_job.py:274` `await _fail(job, record, redact_secrets(str(error), secrets))`
- Proposed test: Submit an analyze request with a known token, then query the database to confirm the token does not appear in any table.
- Verifier (0.95): I traced the full path of the access_token from the request body through the codebase. At line 69 of repositories.py, the token is extracted from the request body. It is then passed to analysis_job.start_analysis() at line 70, and used in _run_job() at line 225 where it's stored in a local variable `token` and added to a `secrets` list. The token is only used in-memory for git clone operations (line 236: _clone_only). It is never written to any persisted model: IntakeRecord (schema.py:260) has no token field, IntakeRow (intake_store.py:17) stores record_json but the IntakeRecord model has no access_token field, and RepositoryFindingsRow (findings_store.py:15) stores findings_json. The token is only redacted in error messages via redact_secrets() at lines 274 and 282. No code path persists the token to the database. The finding correctly identifies that the token is never persisted.
  - `backend/app/api/repositories.py:69` `token = body.access_token.strip() if body.access_token else None`
  - `backend/app/repo_analysis/analysis_job.py:225` `token = access_token or settings.repo_access_token`
  - `backend/app/repo_analysis/analysis_job.py:236` `clone_path = await asyncio.to_thread(_clone_only, parsed.url, token, workspace)`
  - `backend/app/repo_analysis/analysis_job.py:274` `await _fail(job, record, redact_secrets(str(error), secrets))`
  - `backend/app/intake/schema.py:147` `analysis_progress: str | None = None`

### [high] HTTPException detail leaks exception message without redaction in repositories

- Lane: `logging-and-redaction` · Category: `token-in-error` · Verdict: **refuted** · Reviewer confidence 0.60
- Location: `backend/app/api/repositories.py:64`
- Invariant: Tokens and credentials are stripped from error messages returned to clients (redact_secrets, logging_config.redact).
- Failure scenario: validate_repository_url raises RepositoryUrlError with a message that could contain user-provided URL data. The str(error) is passed directly as HTTPException detail on line 64 without redaction.
- Evidence:
  - `backend/app/api/repositories.py:64` `raise HTTPException(status_code=400, detail=str(error)) from None`
  - `backend/app/repo_analysis/clone_repository.py:67` `class RepositoryUrlError(ValueError):`
- Proposed test: Call analyze_repository with a URL that triggers a RepositoryUrlError and verify the response detail is safe. Also verify that any future exception types raised by validate_repository_url would be redacted.
- Verifier (0.90): The finding claims that str(error) on line 64 leaks tokens/credentials without redaction. However, examining validate_repository_url (clone_repository.py:135-179), all RepositoryUrlError messages are either static strings or only include safe URL components like host, scheme, or port — never the actual credential/token values. When credentials are detected in the URL (line 153-156), the error message is a generic 'Remove credentials from the URL. Paste an access token in the token field instead.' with no credential data included. There is an explicit test at test_url_validation.py:110-113 that verifies credentials are not echoed in the error message. The invariant holds because the source (validate_repository_url) already produces safe messages — no additional redaction is needed. Existing test covers it.
  - `backend/app/repo_analysis/clone_repository.py:155` `"Remove credentials from the URL. Paste an access token in the token field instead."`
  - `backend/app/repo_analysis/clone_repository.py:139` `raise RepositoryUrlError("Enter the repository URL.")`
  - `backend/app/repo_analysis/clone_repository.py:143` `"SSH URLs are not supported. Use an https URL such as https://github.com/org/repo."`
  - `backend/tests/repo_analysis/test_url_validation.py:110` `def test_credentials_are_not_echoed_in_the_message() -> None:`
  - `backend/tests/repo_analysis/test_url_validation.py:113` `assert "ghp_FAKE123456" not in str(excinfo.value)`

### [medium] repoUrl from record used as href without scheme check

- Lane: `frontend-trust` · Category: `url-sink` · Verdict: **unverified** · Reviewer confidence 0.70
- Location: `frontend/components/review/ReviewHeader.tsx:38`
- Invariant: Agent or record strings are rendered as text, never as an href/src without a scheme check.
- Failure scenario: A record's meta.repo_url field contains a javascript: or data: URL. The ReviewHeader renders it as href={repoUrl} with target="_blank" but no scheme validation, potentially triggering XSS when the user clicks the link.
- Evidence:
  - `frontend/components/review/ReviewHeader.tsx:16` `const repoUrl = record.meta.repo_url ?? null;`
  - `frontend/components/review/ReviewHeader.tsx:37` `<a`
  - `frontend/components/review/ReviewHeader.tsx:38` `href={repoUrl}`
  - `frontend/components/review/ReviewHeader.tsx:39` `target="_blank"`
  - `frontend/components/review/ReviewHeader.tsx:40` `rel="noreferrer noopener"`
- Proposed test: Set record.meta.repo_url to 'javascript:alert(1)' and render ReviewHeader; verify the href is sanitized or rejected.

## Notes

- `api-and-persistence`: Reviewed all API routes in backend/app/api/ and backend/app/main.py. Traced intake id generation (uuid4().hex[:12] = 48 bits), rate limiter (X-Forwarded-For behind proxy - known safe), webhook destination (settings-only, not from request body), SQL (SQLModel only, no raw SQL), secret persistence (access_token used in-memory only, redacted in errors), and response bodies (snippets redacted, no tokens in exports or findings). The only finding is the truncated UUID4 hex for intake IDs which provides only 48 bits of entropy instead of the full 122 bits of UUID4.
- `export-rendering`: Traced all data flows from sources (record fields, repo findings, evidence snippets) to sinks (PDF via WeasyPrint, JSON export, webhook). Key findings: (1) Jinja2 template uses autoescape=True with no |safe or Markup, so all user/model values are HTML-escaped. (2) No <img>, <link>, @import, or url() in the template; WeasyPrint base_url is local templates dir. (3) JSON export serializes only IntakeRecord.model_dump() which contains no secrets (repo_access_token, api_key are in Settings model, not in record). (4) Evidence snippets from repo analysis are stored in findings_store (separate DB table) and never flow into IntakeRecord or exports. (5) Content-Disposition header uses regex to strip unsafe chars from intake_id, preventing header injection. (6) Webhook receives the same JSON bytes as the download endpoint. All invariants hold.
- `frontend-trust`: Lane review complete. All catalog components validate props via Zod schemas enforced by CopilotKit generative-UI middleware. No HTML sinks (dangerouslySetInnerHTML, innerHTML, eval, etc.) found. Proxy routes forward only whitelisted headers and use encodeURIComponent on path segments. No NEXT_PUBLIC_ secrets exposed. One medium-severity finding: repoUrl from record used as href without scheme validation.
- `logging-and-redaction`: Reviewed all logger calls, HTTPException calls, and redaction patterns. Key observations: (1) RequestIdFilter only redacts record.msg, not extra dict values. (2) HTTPException detail fields in exports.py:85 and repositories.py:64 pass str(error) without redaction. (3) The clone_repository module properly redacts secrets in exception messages before they propagate. (4) tool_error function logs extra dict values that bypass the redaction filter. (5) CONTENT_LOGGERS are capped at WARNING in production, so debug-level content logging is safe. (6) No print() calls found. (7) exc_info=True in analysis_job.py:293 and summarize_findings.py:236 logs exception tracebacks which could contain sensitive data, but these are at WARNING level and the filter redacts record.msg.
- `repository-analysis`: Traced the full flow from sources (repo_url, access_token from API request) through clone_repository.py (host allowlist, https enforcement, shallow clone, size cap, timeout, submodule disable, token via GIT_CONFIG_* env vars, redaction of all error messages), inventory.py (symlink skipping, binary file skipping, file size cap, text budget cap), signal_detectors.py (snippets redacted via make_snippet→redact_secrets), summarize_findings.py (findings values validated against intake schema, snippets redacted), findings_store.py (findings persisted without token exposure), and analysis_job.py (token never logged, error messages redacted, logger.exception does not include token in traceback). No path allows the access token to reach logs, errors, or persisted findings. Symlink escape is prevented by followlinks=False and explicit is_symlink() checks. No code execution, unsafe deserialization, or allowlist bypass detected. Budget exhausted after thorough review with zero findings.

## Manifests

- `lane-reviewer` v1.1.0 manifest `379afb30b68980e4` · openai/Qwen3.6-35B-A3B-NVFP4 (balanced-v1, thinking off) · skills evidence-standards, api-and-persistence · tools list_files, read_file, report_findings, search_text
- `finding-verifier` v1.0.0 manifest `a00f7869d99734be` · openai/Qwen3.6-35B-A3B-NVFP4 (balanced-v1, thinking off) · skills evidence-standards, disprove-finding · tools list_files, read_file, record_verdict, run_backend_tests, search_text
