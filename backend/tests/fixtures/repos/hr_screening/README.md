# Candidate Summary Assistant

Internal HR tool that helps recruiters screen CVs faster. Recruiters upload a batch of
candidate CVs (PDF or Word), the service extracts the key facts and asks OpenAI GPT-4 via
the API to write a short, structured summary and a suggested ranking for each candidate.

The recruiter reviews every summary before shortlisting; the assistant never rejects a
candidate on its own. It is used by the Talent Acquisition team only and is not exposed to
candidates or to the public.

## How it works

1. A recruiter uploads CVs through the internal web UI.
2. `src/ingest/cv_parser.py` extracts name, contact details and work history.
3. `src/ranking/summarise.py` calls the OpenAI chat completions API to draft a summary.
4. Summaries and the parsed candidate record are stored in the HR Postgres database.

## Status

Running in production for the EU hiring teams since Q2. Deployed on AWS (eu-west-1).

## Development

```bash
pip install -r requirements.txt
uvicorn src.api.routes:app --reload
```

See `docs/retention.md` for the data retention rules.
