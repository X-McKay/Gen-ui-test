"""Persist repository findings per intake so the review page can show the evidence later."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import TypeAdapter
from sqlalchemy import Engine
from sqlmodel import Field, SQLModel

from app.intake.intake_store import get_engine, session_scope
from app.repo_analysis.summarize_findings import RepositoryFinding


class RepositoryFindingsRow(SQLModel, table=True):
    __tablename__ = "repository_findings"

    intake_id: str = Field(primary_key=True)
    findings_json: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


_findings_adapter: TypeAdapter[list[RepositoryFinding]] = TypeAdapter(list[RepositoryFinding])
_prepared_engine: Engine | None = None


def _ensure_table() -> None:
    """Create the table on first use (the engine may predate this module's import)."""
    global _prepared_engine
    engine = get_engine()
    if _prepared_engine is not engine:
        SQLModel.metadata.create_all(engine)
        _prepared_engine = engine


def save_findings(intake_id: str, findings: list[RepositoryFinding]) -> None:
    _ensure_table()
    payload = _findings_adapter.dump_json(findings).decode()
    with session_scope() as session:
        row = session.get(RepositoryFindingsRow, intake_id)
        if row is None:
            row = RepositoryFindingsRow(intake_id=intake_id, findings_json=payload)
        else:
            row.findings_json = payload
            row.created_at = datetime.now(UTC)
        session.add(row)
        session.commit()


def load_findings(intake_id: str) -> list[RepositoryFinding]:
    _ensure_table()
    with session_scope() as session:
        row = session.get(RepositoryFindingsRow, intake_id)
        if row is None:
            return []
        return _findings_adapter.validate_json(row.findings_json)


def delete_findings(intake_id: str) -> bool:
    _ensure_table()
    with session_scope() as session:
        row = session.get(RepositoryFindingsRow, intake_id)
        if row is None:
            return False
        session.delete(row)
        session.commit()
        return True
