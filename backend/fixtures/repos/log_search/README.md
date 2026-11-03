# Log Search Assistant

Internal assistant that lets on-call engineers ask questions about production logs in
plain English. It translates the question into an Elasticsearch query with an LLM
(any provider through LiteLLM; we run it against our self-hosted vLLM endpoint and fall
back to the OpenAI API), runs the query and drafts a short explanation of the matching
log lines.

The service handles no personal data: application logs are anonymised before they reach
the cluster (user identifiers are hashed and IP addresses are dropped at ingest). The
assistant is used by the platform team only, behind the company SSO.

## Status

Pilot with the platform team; not yet rolled out to other teams.

## Running locally

```bash
pip install -r requirements.txt
uvicorn src.search.query:app --reload
```
