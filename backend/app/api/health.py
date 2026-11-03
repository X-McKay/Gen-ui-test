"""Health endpoint: process liveness plus a cached one-token model check."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Query

from app.inference.model_factory import HealthStatus, health_check
from app.intake.schema import SCHEMA_VERSION
from app.settings import get_settings

router = APIRouter()

_cache: dict[str, Any] = {"checked_at": 0.0, "status": None}
CACHE_SECONDS = 60


@router.get("/healthz")
async def healthz(refresh: bool = Query(default=False)) -> dict[str, Any]:
    settings = get_settings()
    now = time.monotonic()
    cached: HealthStatus | None = _cache["status"]
    if refresh or cached is None or now - float(_cache["checked_at"]) > CACHE_SECONDS:
        cached = await health_check(settings)
        _cache["status"] = cached
        _cache["checked_at"] = now
    return {
        "status": "ok" if cached.ok else "degraded",
        "schema_version": SCHEMA_VERSION,
        "mock_model": settings.mock_model,
        "model": cached.model_dump(),
    }
