"""HTTP API used by the internal recruiter UI."""

from __future__ import annotations

import os
import tempfile

import psycopg2
from fastapi import FastAPI, UploadFile

from src.ingest.cv_parser import parse_cv
from src.ranking.summarise import summarise_candidate

app = FastAPI(title="Candidate Summary Assistant")


def connection():
    return psycopg2.connect(os.environ["DATABASE_URL"])


@app.post("/candidates/upload")
async def upload_cv(file: UploadFile, role_description: str) -> dict[str, str]:
    with tempfile.NamedTemporaryFile(suffix=file.filename, delete=False) as handle:
        handle.write(await file.read())
        path = handle.name
    parsed = parse_cv(path)
    summary = summarise_candidate(parsed, role_description)
    with connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO candidates (full_name, email, phone, cv_text, summary) "
            "VALUES (%s, %s, %s, %s, %s)",
            (parsed.full_name, parsed.candidate_email, parsed.phone, parsed.raw_text, summary),
        )
    return {"summary": summary}
