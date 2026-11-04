---
name: purpose-and-users
description: Fact lane - what the system is for, who uses it, its stage and region, the regulated domain its purpose falls in, whether it talks to people, generates content, affects significant decisions, how autonomous it is and whether a person reviews its outputs.
metadata:
  owner: platform
  version: 1.0.0
  governance_tier: low
---

## Use this skill when

- You are assigned the fact lane `purpose-and-users`.

## Fields

- `project.name`, `project.description` (two sentences: what it does and for whom),
  `project.purpose` is recorded as `use_case.purpose`.
- `project.lifecycle_stage` (idea, poc, pilot, production), `project.target_users`
  (internal, external, public), `project.deployment_regions` (eu, uk, us, apac, global;
  `eu-west-1` is eu).
- `use_case.domains`: hr_employment, credit_insurance, education, law_enforcement,
  migration_border, justice_democratic, critical_infrastructure,
  medical_or_safety_component, essential_services, other. The domain the system's own
  purpose falls in, not the company's industry.
- `use_case.interacts_directly_with_people`, `use_case.generates_synthetic_content`,
  `use_case.affects_legal_or_significant_effects`, `use_case.emotion_recognition`,
  `use_case.social_scoring`.
- `ai_system.autonomy_level` (assistive, recommends, decides), `ai_system.human_oversight`.

## Where to look

1. README, `docs/`, ADRs, `CHANGELOG`, deployment manifests (`infra/`, `terraform`,
   `helm`, `docker-compose`) for stage, users and regions.
2. Route handlers and UI copy for who calls it and whether a person reviews outputs
   (`approve`, `review`, `draft`, `auto`, `without review`).
3. Prompts and system messages in code: they state the task plainly ("summarise CVs",
   "decide", "rank").

## Traps

- "Internal" in a README beats a guess from the deployment; "public" needs an
  unauthenticated route or a public site.
- `decides` means the output takes effect without a person reviewing that case; an
  override button afterwards does not make it `recommends`.
- A fit score, a ranking or a triage suggestion is not synthetic content; a summary, a
  drafted message or an explanation is.
- Significant effects: hiring, credit, insurance, benefits, education, legal status.
  Answering questions and small customer-service outcomes are not.

## Completion criteria

Record `use_case.domains` and `project.target_users` whenever the documents allow it;
they drive the classification. Leave `lifecycle_stage` out when nothing states it.
