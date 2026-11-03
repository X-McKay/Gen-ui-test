---
name: add-framework
description: Add or change a governance framework module (GDPR, NIST AI RMF, ISO 42001, internal policy or a new one) with full branch-coverage tests. Use when asked to add obligations, a tier floor, a new regulation or a policy rule.
---

# Add a framework module

Framework modules are plain Python modules satisfying the `FrameworkModule` protocol in
`backend/app/governance/frameworks/base.py`: a module-level `name` and a pure
`evaluate(record, eu) -> FrameworkResult`. They run after the EU AI Act table, may add
obligations, next steps, framework names and a tier floor, and never persist anything.
Budget about 25 minutes. `README.md` ("How-to: add a framework module") has a complete
`local_ai_policy.py` example with its tests.

## Checklist

1. **Create** `backend/app/governance/frameworks/<snake_name>.py`:
   - `name = "<Display name>"`, field path constants, a private `_obligation(text, reference)`
     helper that sets `framework=name`.
   - `evaluate` returns `NOT_APPLICABLE` early when the module does not apply, else
     `FrameworkResult(applies=True, obligations=[...], next_steps=[...], tier_floor=RiskTier.X)`.
   - Read record values only through `app/governance/field_values.py` (`is_true`, `is_false`,
     `equals`, `contains_any`, `list_value`, `is_asserted`); they treat `None` and `"unknown"`
     as not asserted.
2. **Register** it in `backend/app/governance/frameworks/__init__.py` (`FRAMEWORK_MODULES`);
   list order is the order of `applicable_frameworks` and `obligations` in the assessment.
3. **Label** it in `frontend/lib/fieldCatalog.ts` (`FRAMEWORK_LABELS`) so the review page and
   PDF show the display name.
4. **Tests** in `backend/tests/governance/test_frameworks.py`, using `make_record` from
   `tests/conftest.py` and the `MINIMAL_EU` fixture:
   - one test for "does not apply",
   - one test per obligation and per branch inside `evaluate`,
   - one for the tier floor,
   - update `test_registry_order_and_names` and any `applicable_frameworks` assertion in
     `tests/governance/test_classify.py`.
   The governance package has a **100 % branch-coverage gate**: an untested `if` fails
   `make test-backend`.
5. **EU AI Act table changes** go in `backend/app/governance/eu_ai_act.py` as rule rows, with
   a test per row in `tests/governance/test_eu_ai_act_rules.py`; the rationale text is what
   the review page shows, so keep it one sentence with the article reference.
6. **Run** `make test-backend` (coverage report prints missing branches), then
   `make lint typecheck`.

## Rules

- Modules are pure: no I/O, no settings reads, no model calls.
- Never lower a tier; `classify()` raises to the highest floor and merges obligations
  de-duplicated by framework + text.
- The classification is a conservative starting point, not legal advice; phrase obligations
  as actions ("Keep decision logs for 12 months"), with a `reference`.
