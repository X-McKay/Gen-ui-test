"""SQLModel persistence for intakes. SQLite by default; Postgres by connection string."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import Engine
from sqlmodel import Field, Session, SQLModel, create_engine, select

from app.intake.schema import IntakeRecord, IntakeStatus
from app.settings import get_settings


class IntakeRow(SQLModel, table=True):
    __tablename__ = "intakes"

    intake_id: str = Field(primary_key=True)
    status: str = Field(default=IntakeStatus.IN_PROGRESS.value, index=True)
    mode: str = Field(default="new")
    record_json: str
    current_step_json: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = get_settings().database_url
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _engine = create_engine(url, connect_args=connect_args)
        SQLModel.metadata.create_all(_engine)
    return _engine


def reset_engine(url: str | None = None) -> None:
    """Testing seam: point persistence at a fresh database."""
    global _engine
    if url is not None:
        get_settings.cache_clear()
        import os

        os.environ["DATABASE_URL"] = url
    _engine = None


@contextmanager
def session_scope() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session


def save_record(record: IntakeRecord, current_step: dict[str, object] | None = None) -> None:
    with session_scope() as session:
        row = session.get(IntakeRow, record.meta.intake_id)
        payload = record.model_dump_json()
        if row is None:
            row = IntakeRow(
                intake_id=record.meta.intake_id,
                record_json=payload,
                mode=record.meta.mode.value,
                created_at=record.meta.created_at,
            )
        row.record_json = payload
        row.status = record.meta.status.value
        row.mode = record.meta.mode.value
        row.updated_at = datetime.now(UTC)
        if current_step is not None:
            row.current_step_json = json.dumps(current_step)
        session.add(row)
        session.commit()


def load_record(intake_id: str) -> IntakeRecord | None:
    with session_scope() as session:
        row = session.get(IntakeRow, intake_id)
        if row is None:
            return None
        return IntakeRecord.model_validate_json(row.record_json)


def load_current_step(intake_id: str) -> dict[str, object] | None:
    with session_scope() as session:
        row = session.get(IntakeRow, intake_id)
        if row is None or row.current_step_json is None:
            return None
        step: dict[str, object] = json.loads(row.current_step_json)
        return step


def save_current_step(intake_id: str, step: dict[str, object] | None) -> None:
    with session_scope() as session:
        row = session.get(IntakeRow, intake_id)
        if row is None:
            return
        row.current_step_json = json.dumps(step) if step is not None else None
        session.add(row)
        session.commit()


def list_records(limit: int = 100) -> list[IntakeRecord]:
    with session_scope() as session:
        rows = session.exec(
            select(IntakeRow).order_by(IntakeRow.updated_at.desc()).limit(limit)  # type: ignore[attr-defined]
        ).all()
        return [IntakeRecord.model_validate_json(row.record_json) for row in rows]


def delete_record(intake_id: str) -> bool:
    with session_scope() as session:
        row = session.get(IntakeRow, intake_id)
        if row is None:
            return False
        session.delete(row)
        session.commit()
        return True
