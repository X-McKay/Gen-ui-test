---
name: purpose-and-users
description: Fact lane - what the system is for, who uses it, its stage and region, the regulated domain its purpose falls in, whether it talks to people, generates content, affects significant decisions, what it executes itself (money, equipment, commitments) and with how much at stake, how autonomous it is and whether a person reviews its outputs.
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
  medical_or_safety_component, essential_services, financial_markets (trading or
  investing in financial instruments: order placement, market making, execution; not an
  Annex III area), other. The domain the system's own purpose falls in, not the
  company's industry.
- `use_case.interacts_directly_with_people`, `use_case.generates_synthetic_content`,
  `use_case.affects_legal_or_significant_effects`, `use_case.emotion_recognition`,
  `use_case.social_scoring`.
  `interacts_directly_with_people` is true only when people converse with the system
  itself (chat, voice, an assistant that answers them). Uploading a file, filling a form
  or using an app in which the output appears (a summary, an estimate, a roster) is not
  direct interaction: record false with the route or handler as evidence.
- `ai_system.autonomy_level` (assistive, recommends, decides), `ai_system.human_oversight`.
- `use_case.acts_on_the_world`: what the system itself carries out, as a list:
  `financial_transactions` (it places orders or trades, pays, refunds, settles or
  transfers money: an order-gateway client, a payments API call, a payout job),
  `physical_or_system_actions` (it runs commands or playbooks on hosts, controls
  equipment, blocks addresses, opens gates: SSH or device clients called from the
  decision path), `legal_commitments` (it signs, files or accepts terms), or `["none"]`
  when the outputs are read by people and nothing is executed. Cite the client or the
  call that performs the action, not the model code.
- `use_case.financial_exposure` (under_10k, ten_k_to_1m, over_1m): only when a config value,
  limit or document states amounts (`MAX_ORDER_EUR`, position limits, refund caps). The
  band is set by the cap on one action or position: `AUTO_SETTLE_LIMIT_EUR = 2000` is
  under_10k, a 5-million position limit is over_1m. Leave it out when nothing states an
  amount.

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
- A decision about a request is not an action: approving or declining a loan, blocking
  a card payment, unlocking a gate for a verified person, assigning shifts or grading are
  `none`; the system acts when it moves money, operates equipment or changes systems
  itself (payout jobs, order gateways, playbooks on hosts, firewall rules, load shedding).
  A credit, pricing or eligibility decision is not a financial transaction; the money
  moves elsewhere. A signal or recommendation a trader executes is not
  `financial_transactions` and a desk that only recommends is not `financial_markets`
  algorithmic trading under MiFID II; the order-placing code is what makes it one.

## Completion criteria

Record `use_case.domains` and `project.target_users` whenever the documents allow it;
they drive the classification. Leave `lifecycle_stage` out when nothing states it.
