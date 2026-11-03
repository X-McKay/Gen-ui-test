"""Translate a plain-English question into an Elasticsearch query and explain the hits."""

from __future__ import annotations

import os

import litellm
from elasticsearch import Elasticsearch
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Log Search Assistant")
elastic = Elasticsearch(os.environ.get("ELASTICSEARCH_URL", "http://elasticsearch:9200"))
MODEL = os.environ.get("LOG_SEARCH_MODEL", "hosted_vllm/Qwen2.5-7B-Instruct")

QUERY_PROMPT = (
    "Translate the question into an Elasticsearch query DSL JSON object for the index "
    "'app-logs-*'. Return only JSON."
)
EXPLAIN_PROMPT = "Explain in two sentences what these log lines have in common."


class Question(BaseModel):
    text: str
    hours: int = 1


def ask_model(system_prompt: str, user_content: str) -> str:
    response = litellm.completion(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0,
    )
    return response.choices[0].message.content or ""


@app.post("/search")
def search(question: Question) -> dict[str, object]:
    query = ask_model(QUERY_PROMPT, question.text)
    hits = elastic.search(index="app-logs-*", body=query, size=50)["hits"]["hits"]
    lines = [hit["_source"].get("message", "") for hit in hits]
    explanation = ask_model(EXPLAIN_PROMPT, "\n".join(lines[:20]))
    return {"hits": lines, "explanation": explanation}
