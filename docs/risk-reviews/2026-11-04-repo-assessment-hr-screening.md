# Repository risk assessment 20261104T155606Z-538b05

> Sample output of `make risk-assess REPO=backend/fixtures/repos/hr_screening` on the local model, before the owning-lane merge rule; kept as a reference for the report shape. Numbers are from one run.

Repository `/home/al/git/Gen-ui-test/backend/fixtures/repos/hr_screening` at `73972c5` · 2026-11-04T15:56:06+00:00 · lanes: ai-usage, controls-in-code, data-and-privacy, purpose-and-users, third-party-services

| Assessment | Result |
| --- | --- |
| EU AI Act classification | **high_risk** |
| Inherent risk | **high** (score 11) |
| Residual risk, controls unconfirmed | **high** (score 11) |
| Residual risk if claimed controls are confirmed | **medium** |
| Overall compliance tier | high |
| Frameworks | EU AI Act, GDPR, NIST AI RMF, ISO/IEC 42001, Internal AI policy |
| Facts recorded / rejected | 37 / 0 |
| Open questions for the owner | 6 |
| Wall time · requests · tokens in/out · tool calls | 313 s · 52 · 417733/26076 · 76 |

## Risk drivers

| Driver | Category | Points | Answer |
| --- | --- | --- | --- |
| It generates content | exposure | +1 | Generates content: Yes |
| Data leaves for a third-party model API | exposure | +1 | Model source: Third-party API |
| It recommends; a person decides | autonomy | +1 | Autonomy: Recommends, a person decides |
| It processes personal data | data | +2 | Personal data: Yes |
| Data crosses borders | data | +1 | Cross-border transfer: Yes |
| Outputs affect rights, access or significant decisions | impact | +3 | Significant effects: Yes |
| It operates in an Annex III area | impact | +2 | Domains: HR and employment |

## Controls

| Control | Status | Points removed |
| --- | --- | --- |
| A person reviews or can override outputs | unconfirmed | -0 |
| Human review limits the effect of errors | unconfirmed | -0 |
| Input and output guardrails are in place | absent | -0 |
| Personal data is minimised before the model | unconfirmed | -0 |
| Access is authenticated and authorised | unconfirmed | -0 |
| Rate limits and misuse monitoring | absent | -0 |
| Evaluated or red-teamed before release | absent | -0 |
| Ongoing evaluation of outputs | absent | -0 |
| Provider may not train on the data | absent | -0 |
| Rollback, kill switch and incident process | absent | -0 |
| Users are told they interact with AI | absent | -0 |

## Why this classification

- AI used for recruitment, selection, promotion, termination, task allocation or monitoring of workers is listed in Annex III and is high-risk. (EU AI Act Art. 6(2), Annex III 4) — Domains: HR and employment
- Generated content used only inside the team does not change the tier, but anything that leaves the team must be marked. (EU AI Act Art. 50(2)) — Generates content: Yes
- Generated content used only inside the team does not change the tier, but anything that leaves the team must be marked. (EU AI Act Art. 50(2)) — Target users: Internal staff
- A general-purpose AI model is part of the system. Its provider owes documentation and copyright duties; the integrator must build on them. (EU AI Act Art. 53, Chapter V) — General-purpose model: Yes

## Obligations

- **EU AI Act**: Mark AI-generated content that leaves the team (EU AI Act Art. 50(2))
- **EU AI Act**: Confirm the general-purpose model provider publishes technical documentation, a copyright policy and a training-content summary, and obtain its downstream information package (EU AI Act Art. 53(1))
- **EU AI Act**: As the downstream integrator, keep the model provider's documentation, respect its acceptable-use terms and check whether the model is designated as carrying systemic risk (EU AI Act Art. 25, Art. 51, Art. 55)
- **EU AI Act**: Run a documented risk management system across the whole lifecycle (EU AI Act Art. 9)
- **EU AI Act**: Apply data governance to training, validation and test data, including bias examination and representativeness (EU AI Act Art. 10)
- **EU AI Act**: Provide deployers with instructions for use that explain capabilities, limits, accuracy and oversight measures (EU AI Act Art. 13)
- **EU AI Act**: Design for, and operate with, effective human oversight that can intervene or stop the system (EU AI Act Art. 14)
- **EU AI Act**: Use the system in line with the instructions, assign trained human overseers, monitor operation, keep logs and inform affected workers and persons (EU AI Act Art. 26)
- **EU AI Act**: Carry out a fundamental rights impact assessment before first use when deploying as a public body or in essential private services (credit, insurance) (EU AI Act Art. 27)
- **EU AI Act**: Register the system in the EU database before placing it on the market or putting it into service (public-body deployers register too) (EU AI Act Art. 49)
- **GDPR**: Identify a lawful basis for each processing purpose and publish a privacy notice (GDPR Art. 6, Art. 13, Art. 14)
- **GDPR**: Add the processing to the records of processing activities (GDPR Art. 30)
- **GDPR**: Carry out a data protection impact assessment because the system is high-risk under the EU AI Act (GDPR Art. 35)
- **GDPR**: Put a transfer mechanism in place for data leaving the region (adequacy decision or standard contractual clauses with a transfer impact assessment) (GDPR Chapter V, Art. 44-46)
- **NIST AI RMF**: Govern: add the system to the AI inventory and name an accountable owner (NIST AI RMF GOVERN 1.6, GOVERN 2.1)
- **NIST AI RMF**: Map: document the intended use, the deployment context and who is affected (NIST AI RMF MAP 1.1, MAP 3.1)
- **NIST AI RMF**: Measure: write an evaluation plan with accuracy and robustness metrics (NIST AI RMF MEASURE 2.5, MEASURE 2.6)
- **NIST AI RMF**: Manage: define how incidents and harmful outputs are reported and handled (NIST AI RMF MANAGE 4.1, MANAGE 4.3)
- **NIST AI RMF**: Measure: test for bias and disparate impact across affected groups before and after deployment (NIST AI RMF MEASURE 2.11)
- **NIST AI RMF**: Manage: monitor performance and drift in operation and review on a schedule (NIST AI RMF MANAGE 2.2, MEASURE 2.4)
- **NIST AI RMF**: Manage: document residual risks and obtain the accountable owner's sign-off before deployment (NIST AI RMF MANAGE 1.2, MANAGE 1.3)
- **ISO/IEC 42001**: Complete an AI system impact assessment covering individuals, groups and society (ISO/IEC 42001 Clause 6.1.4, Annex A.5)
- **ISO/IEC 42001**: Apply supplier controls to the model provider: contract terms, change notice and service-level monitoring (ISO/IEC 42001 Annex A.10.3)
- **Internal AI policy**: Register the system in the AI inventory (Internal AI policy §1)
- **Internal AI policy**: Complete the vendor review for the third-party model provider (Internal AI policy §5)

## Facts and evidence

| Field | Value | Conf. | Basis | Lane | Evidence |
| --- | --- | --- | --- | --- | --- |
| Uses AI | Yes | 1.00 | code | data-and-privacy | `src/ranking/summarise.py:10` `from openai import OpenAI` |
| Personal data | Yes | 1.00 | code | data-and-privacy | `src/ingest/cv_parser.py:21` `full_name: str \| None` |
| Domains | HR and employment | 0.95 | documented | data-and-privacy | `README.md:3` `Internal HR tool that helps recruiters screen CVs faster.` |
| Significant effects | Yes | 0.85 | documented | purpose-and-users | `README.md:5` `the service extracts the key facts and asks OpenAI GPT-4 via the API to write a short, structured su` |
| Project name | Candidate Summary Assistant | 1.00 | documented | data-and-privacy | `README.md:1` `# Candidate Summary Assistant` |
| Owner | Talent Acquisition team | 0.90 | documented | ai-usage | `README.md:8` `It is used by the Talent Acquisition team only` |
| Lifecycle stage | Production | 0.95 | documented | ai-usage | `README.md:20` `Running in production for the EU hiring teams since Q2.` |
| Target users | Internal staff | 0.95 | documented | ai-usage | `README.md:3` `Internal HR tool that helps recruiters screen CVs faster.` |
| Description | Internal HR tool that helps recruiters screen CVs faster by extracting key facts from uploaded CVs and using OpenAI GPT-4 to write structured summaries and suggested rankings. | 0.90 | documented | ai-usage | `README.md:3` `Internal HR tool that helps recruiters screen CVs faster. Recruiters upload a batch of candidate CVs` (conflicts: data-and-privacy: 'Internal HR tool that helps recruiters screen CVs faster by extracting key facts from uploaded CVs and using OpenAI GPT-4 to draft structured summaries and suggested rankings.' (0.90); purpose-and-users: 'An internal HR tool that helps recruiters screen CVs by extracting candidate facts and using OpenAI GPT-4 to draft structured summaries and fit scores. It is used exclusively by the Talent Acquisition team for EU hiring and is not exposed to candidates or the public.' (0.90)) |
| Team | Talent Acquisition team | 0.90 | documented | ai-usage | `README.md:8` `It is used by the Talent Acquisition team only` |
| Business unit | Talent Acquisition / HR | 0.90 | documented | ai-usage | `README.md:8` `It is used by the Talent Acquisition team only` |
| Deployment regions | European Union | 0.90 | documented | ai-usage | `README.md:20` `Running in production for the EU hiring teams since Q2. Deployed on AWS (eu-west-1).` |
| Third-party services | OpenAI (GPT-4o API) | 0.95 | code | ai-usage | `requirements.txt:3` `openai==1.51.0` (conflicts: third-party-services: 'OpenAI API (GPT-4o), AWS RDS (Postgres, eu-west-1)' (0.95); data-and-privacy: 'OpenAI GPT-4o API for summarisation; AWS for hosting (eu-west-1); Postgres database.' (0.90)) |
| Model source | Third-party API | 1.00 | code | data-and-privacy | `src/ranking/summarise.py:10` `from openai import OpenAI` |
| Autonomy | Recommends, a person decides | 0.90 | code | ai-usage | `src/ranking/summarise.py:18` `then suggest a fit score from 1 to 5 for the role. The recruiter makes the decision.` |
| Human oversight | Yes | 0.95 | documented | purpose-and-users | `README.md:7` `The recruiter reviews every summary before shortlisting; the assistant never rejects a candidate on ` |
| General-purpose model | Yes | 0.95 | code | ai-usage | `src/ranking/summarise.py:24` `model="gpt-4o"` |
| Fine-tuned or trained | No | 0.85 | documented | data-and-privacy | `src/ranking/summarise.py:24` `model="gpt-4o",` |
| Model types | Large language model | 1.00 | code | data-and-privacy | `src/ranking/summarise.py:24` `model="gpt-4o",` |
| Model providers | OpenAI | 1.00 | code | data-and-privacy | `src/ranking/summarise.py:10` `from openai import OpenAI` |
| Special-category data | None | 0.80 | code | data-and-privacy | `src/ingest/cv_parser.py:20` `class ParsedCv:` |
| Data subjects | Employees or candidates, Members of the public | 0.90 | documented | data-and-privacy | `README.md:3` `Internal HR tool that helps recruiters screen CVs faster. Recruiters upload a batch of` (conflicts: ai-usage: ['employees'] (0.85)) |
| Biometric identification | No | 0.70 | absence | data-and-privacy | `src/ingest/cv_parser.py:20` `class ParsedCv:` |
| Personal data categories | Names and contact details, IDs and account numbers | 0.90 | code | ai-usage | `src/ingest/cv_parser.py:22` `candidate_email: str \| None` (conflicts: data-and-privacy: ['contact', 'identifiers', 'employment', 'location', 'free_text'] (0.90)) |
| Trains on personal data | No | 0.90 | documented | data-and-privacy | `src/ranking/summarise.py:24` `model="gpt-4o",` |
| Cross-border transfer | Yes | 0.90 | documented | third-party-services | `README.md:20` `Running in production for the EU hiring teams since Q2. Deployed on AWS (eu-west-1).` |
| Retention policy | Under a year | 0.90 | documented | ai-usage | `docs/retention.md:3` `- Uploaded CVs and the parsed candidate record are deleted after 6 months unless the` |
| Data sources | User uploads | 0.95 | code | ai-usage | `src/api/routes.py:22` `async def upload_cv(file: UploadFile, role_description: str) -> dict[str, str]:` (conflicts: data-and-privacy: ['user_upload', 'internal_db'] (0.90)) |
| Purpose | Automated CV summarisation and candidate ranking to help HR recruiters screen candidates faster. | 0.90 | documented | ai-usage | `README.md:5` `asks OpenAI GPT-4 via the API to write a short, structured summary and a suggested ranking for each ` (conflicts: data-and-privacy: 'Assist recruiters in screening candidate CVs by generating structured summaries and fit scores, with human review before any shortlisting decision.' (0.90); purpose-and-users: 'Draft structured summaries and fit scores for candidate CVs to help recruiters screen candidates faster, with recruiter review before any shortlisting decision.' (0.90)) |
| Interacts with people | No | 0.90 | documented | ai-usage | `README.md:9` `It is used by the Talent Acquisition team only and is not exposed to candidates or to the public.` |
| Generates content | Yes | 0.90 | code | ai-usage | `src/ranking/summarise.py:23` `response = client.chat.completions.create(` |
| Emotion recognition | No | 0.70 | absence | ai-usage | `src/ranking/summarise.py:16` `SYSTEM_PROMPT = (` |
| Social scoring | No | 0.85 | documented | data-and-privacy | `README.md:7` `The recruiter reviews every summary before shortlisting; the assistant never rejects a candidate on ` |
| Remote biometric ID | No | 0.70 | absence | ai-usage | `src/ingest/cv_parser.py:1` `"""Extract structured facts from an uploaded CV (PDF or Word)."""` |
| Manipulative techniques | No | 0.70 | absence | ai-usage | `src/ranking/summarise.py:16` `SYSTEM_PROMPT = (` |
| Facial-image scraping | No | 0.70 | absence | ai-usage | `src/ingest/cv_parser.py:1` `"""Extract structured facts from an uploaded CV (PDF or Word)."""` |
| Controls in place | Access controls, Personal data minimisation | 0.80 | documented | data-and-privacy | `docs/retention.md:7` `- Only the Talent Acquisition team and HR administrators can read candidate records.` (conflicts: controls-in-code: ['none'] (0.70)) |

## Open questions for the owner

- Domains (`use_case.domains`)
- Special-category data (`data.special_category_data`)
- Biometric identification (`data.biometric_identification`)
- Emotion recognition (`use_case.emotion_recognition`)
- Social scoring (`use_case.social_scoring`)
- Controls in place (`controls.in_place`)

## Lanes

| Lane | Status | Facts | Requests | Tokens in/out | Tool calls | Time |
| --- | --- | --- | --- | --- | --- | --- |
| ai-usage | completed | 33 | 9 | 87950/8632 | 15 | 192 s |
| | notes | The system is an internal HR tool for CV screening. It uses OpenAI GPT-4o (third-party API) to generate summaries and fit scores for candidates. Personal data (name, email, phone, date of birth) is extracted from uploaded CVs and stored in a Postgres database. The system does not train or fine-tune  | | | | |
| controls-in-code | completed | 2 | 8 | 59239/2401 | 23 | 98 s |
| | notes | The system is an HR CV screening assistant calling OpenAI GPT-4o. Recruiter reviews every summary (human oversight confirmed). No controls in code: no auth on API routes, no rate limiting, no PII redaction before model call, no guardrails, no kill switch, no user disclosure of AI-generated content,  | | | | |
| data-and-privacy | completed | 31 | 16 | 147206/10479 | 15 | 296 s |
| | notes | The system is an internal HR CV screening assistant. It processes personal data (names, emails, phone numbers, dates of birth, nationalities) from uploaded CVs. It uses OpenAI GPT-4o API (third-party, US-based) for summarisation, meaning EU data is transferred to the US. The system recommends (does  | | | | |
| purpose-and-users | completed | 14 | 14 | 96707/3551 | 13 | 216 s |
| | notes | The system is an internal HR tool for CV screening. It uses OpenAI GPT-4 (third-party API) to generate summaries and fit scores. The recruiter reviews all outputs before any action, so autonomy is "recommends" with human oversight. The domain is clearly hr_employment. The fit score is a ranking sugg | | | | |
| third-party-services | completed | 2 | 5 | 26631/1013 | 10 | 95 s |
| | notes | The system is an internal HR CV screening tool. It calls the OpenAI GPT-4o API (a US-based service) to summarise candidate CVs. The application itself is deployed on AWS in eu-west-1 (Ireland), but personal data (CVs containing names, emails, phone numbers, dates of birth) is sent to OpenAI's API, w | | | | |
