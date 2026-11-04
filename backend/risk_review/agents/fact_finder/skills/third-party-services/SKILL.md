---
name: third-party-services
description: Fact lane - the external services and software the system depends on at run time (hosted model APIs, cloud services, SaaS APIs, databases as a service, analytics, e-mail, payments), and what data goes to each.
metadata:
  owner: platform
  version: 1.0.0
  governance_tier: low
---

## Use this skill when

- You are assigned the fact lane `third-party-services`.

## Fields

- `project.third_party_services`: short text, a comma-separated list of the external
  services called at run time (`OpenAI API, AWS S3, Postgres (RDS), Elasticsearch
  (self-hosted)`). Say "(self-hosted)" when the software runs inside the organisation;
  a self-hosted open-source component is software, not a service, and goes last.
- `data.cross_border_transfer`: true when personal data is sent to a provider outside the
  region the documents name (for example EU data to a US model API) and the documents or
  code show it.

## Where to look

1. Dependency manifests for SDKs: `openai`, `anthropic`, `boto3`, `google-cloud-*`,
   `stripe`, `twilio`, `sendgrid`, `segment`, `sentry-sdk`, `datadog`, `elasticsearch`,
   `psycopg2`, `redis`.
2. Environment variable names in `.env.example`, settings modules, Helm values and
   `docker-compose.yml`: `*_API_KEY`, `*_URL`, `*_TOKEN` tell you the services.
3. Hosts in code and config: `api.openai.com`, `*.amazonaws.com`, `*.azure.com`.
4. Infrastructure: `terraform` providers and resources, `Dockerfile` base images.

## Traps

- A dev-only tool (linters, test runners, docs builders) is not a run-time service.
- An SDK that is installed but never imported is not a dependency at run time; cite the
  import or the client construction, not only the manifest, when both exist.
- Do not record secrets: quote the variable name line, never a value.

## Completion criteria

`project.third_party_services` is recorded with one evidence line per named service
where possible (at most three lines; name the rest in `note`).
