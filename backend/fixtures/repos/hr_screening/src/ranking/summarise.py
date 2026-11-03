"""Draft a candidate summary with the OpenAI chat completions API.

The recruiter reviews before shortlisting; nothing here makes a hiring decision.
"""

from __future__ import annotations

import os

from openai import OpenAI

from src.ingest.cv_parser import ParsedCv

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

SYSTEM_PROMPT = (
    "You summarise CVs for recruiters. Write three bullet points on experience, skills and "
    "gaps, then suggest a fit score from 1 to 5 for the role. The recruiter makes the decision."
)


def summarise_candidate(parsed: ParsedCv, role_description: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Role:\n{role_description}\n\nCV:\n{parsed.raw_text}"},
        ],
    )
    return response.choices[0].message.content or ""
