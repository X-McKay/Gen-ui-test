"""Extract structured facts from an uploaded CV (PDF or Word)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from docx import Document
from pypdf import PdfReader

EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE_PATTERN = re.compile(r"\+?\d[\d\s().-]{7,}\d")
DATE_OF_BIRTH_PATTERN = re.compile(
    r"(?:born|date of birth|dob)[:\s]+(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})", re.I
)


@dataclass
class ParsedCv:
    full_name: str | None
    candidate_email: str | None
    phone: str | None
    date_of_birth: date | None
    work_history: list[str]
    raw_text: str


def read_text(path: str) -> str:
    if path.lower().endswith(".pdf"):
        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    return "\n".join(paragraph.text for paragraph in Document(path).paragraphs)


def parse_candidate_email(text: str) -> str | None:
    match = EMAIL_PATTERN.search(text)
    return match.group(0) if match else None


def parse_phone(text: str) -> str | None:
    match = PHONE_PATTERN.search(text)
    return match.group(0).strip() if match else None


def parse_date_of_birth(text: str) -> date | None:
    match = DATE_OF_BIRTH_PATTERN.search(text)
    if not match:
        return None
    day, month, year = re.split(r"[./-]", match.group(1))
    if len(year) == 2:
        year = f"19{year}"
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


def parse_cv(path: str) -> ParsedCv:
    text = read_text(path)
    first_line = text.strip().splitlines()[0] if text.strip() else ""
    return ParsedCv(
        full_name=first_line or None,
        candidate_email=parse_candidate_email(text),
        phone=parse_phone(text),
        date_of_birth=parse_date_of_birth(text),
        work_history=[line for line in text.splitlines() if re.search(r"\b(19|20)\d{2}\b", line)],
        raw_text=text,
    )
