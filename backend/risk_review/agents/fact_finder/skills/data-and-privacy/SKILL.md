---
name: data-and-privacy
description: Fact lane - what data the system processes, whether it is personal, which categories, whether special-category or biometric data is involved, who the data subjects are, where the data comes from, whether personal data is used for training, retention and cross-border transfer.
metadata:
  owner: platform
  version: 1.0.0
  governance_tier: low
---

## Use this skill when

- You are assigned the fact lane `data-and-privacy`.

## Fields

- `data.processes_personal_data`: names, e-mail, phone, addresses, account or employee
  identifiers, CVs, health records, device identifiers and IP addresses all count.
- `data.pii_categories`: contact, identifiers (names, ids, device or IP identifiers),
  financial, employment, location, behavioural, free_text.
- `data.special_category_data`: health, biometric, ethnicity, political, religious,
  sexual_orientation, criminal. `[]` when the documents or the schema rule them out.
- `data.biometric_identification`: true only when faces, voices or fingerprints identify
  or verify a person.
- `data.data_subjects`: employees (staff and candidates), customers (including
  patients), public (applicants, visitors, residents), minors (under 18).
- `data.data_sources`: internal_db, user_upload, third_party, public_web, logs.
  `data.trains_on_personal_data`, `data.retention_policy` (short text),
  `data.cross_border_transfer` (true when data leaves the region it is collected in, e.g.
  EU data to a US provider API, or the docs say so).

## Where to look

1. ORM models, migrations and schemas: column names (`email`, `phone`, `date_of_birth`,
   `full_name`, `ssn`, `iban`, `diagnosis`, `face_embedding`).
2. Parsers and validators: regexes for e-mail, phone, dates of birth; PDF/CV readers.
3. `docs/privacy*`, `docs/retention*`, `PRIVACY.md`, DPIAs, data-flow diagrams.
4. Ingest and anonymisation code: hashing of user ids, dropping of IP addresses.
5. Region and provider configuration for transfers: cloud regions, provider API hosts.

## Traps

- Anonymised or hashed identifiers that cannot be reversed: say so in `note`; the README
  statement plus the ingest code make `processes_personal_data: false` a documented fact.
- Test fixtures and sample data with fake names are not processing.
- A device or browser fingerprint is personal data (device identifier) but not biometric.
- Facial-expression or emotion analysis processes biometric data (special category) even
  when it does not identify anyone.

## Completion criteria

`processes_personal_data` is always recorded with its evidence. When true, record
`data_subjects` and `special_category_data` (`[]` is a valid, evidenced value) because
they drive the classification.
