---
name: add-question
description: Add a new intake question end to end (schema leaf, question bank, generated contract, frontend field catalog, mock extractor, tests). Use when asked to add, gate or rename an interview question or record field.
---

# Add a question

One `QuestionSpec` drives the gap analysis, the review page order, the PDF form, the extraction
tool schema and the render plan, so most of the work is one entry plus its mirror on the
frontend. Budget about 20 minutes. The worked example in `README.md` ("How-to: add a question")
adds `project.deployed_outside_eu`; follow the same shape.

## Checklist

1. **Schema leaf** (skip if the field exists): add `name: FieldMeta[T] = Field(default_factory=FieldMeta[T])`
   to the right section model in `backend/app/intake/schema.py`. Enum values go in the enum
   classes in the same file.
2. **Question bank**: append a `QuestionSpec` to `QUESTION_BANK` in
   `backend/app/intake/question_bank.py`. Set `section`, `priority` (ordering inside the
   section), `control` (`yes_no` | `choice` | `multi` | `text`), `options` for choice controls,
   `gate=Gate(field=..., values=[...])` to skip it until the gate holds, `must_confirm=True`
   when a chip may never be auto-accepted, and `why_asked` + `sensitive=True` for sensitive
   questions.
3. **Extraction hint** (live model only): add a phrase to `FIELD_HINTS` in
   `backend/app/inference/structured_extraction.py` if the model needs guidance.
4. **Regenerate the contract**: `make export-schema`, then commit `schema/intake.schema.json`
   and `frontend/lib/intakeTypes.ts`. `make check-schema` must pass.
5. **Frontend field catalog**: add the matching `spec({...})` to `FIELD_SPECS` in
   `frontend/lib/fieldCatalog.ts` (label, prompt, control, options, mustConfirm, sensitive,
   whyAsked). Chips, the progress rail, the findings table and the review page read it.
6. **Mock mode**: add a rule to `backend/app/intake/heuristic_extractor.py` so `ScriptedLlm`
   infers the field from a description; the e2e fixtures in `frontend/e2e/fixtures/descriptions.ts`
   may need a sentence that triggers it.
7. **Tests**:
   - `backend/tests/intake/test_gap_analysis.py`: gate behaviour (`SKIPPED` → `MISSING` →
     `NEEDS_CONFIRMATION` when `must_confirm`).
   - `backend/tests/intake/test_schema.py` if you added an enum.
   - `frontend/lib/fieldCatalog.test.ts` if the catalog has an invariant for the control.
   - If the answer changes classification, add a rule row or framework obligation and its
     tests (see `/add-framework`); governance coverage must stay at 100 %.
8. **Run** `make lint typecheck test check-schema`, then
   `cd frontend && MOCK_MODEL=1 pnpm exec playwright test --project=chromium`.

## Rules

- `"unknown"` is a legal value for every field; read values through
  `app/governance/field_values.py` helpers, never compare to `False` directly.
- Keep the question budget: a new always-asked question costs every user a step. Prefer a gate
  or a chip the extractor can usually fill.
- Prompts are plain language, one sentence, no legal citations in the question itself; put
  the citation in `why_asked`.
