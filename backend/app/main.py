"""FastAPI application: AG-UI agent endpoint, REST routes, security headers, logging."""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from ag_ui_adk import add_adk_fastapi_endpoint
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agents.intake_agent import create_adk_agent
from app.api import health, intakes
from app.intake.intake_store import get_engine
from app.logging_config import configure_logging, request_id_middleware
from app.settings import Settings, get_settings

logger = logging.getLogger(__name__)

AGENT_PATH = "/agent"


def _parse_rate(rate: str) -> tuple[int, float]:
    count, _, unit = rate.partition("/")
    seconds = {"second": 1.0, "minute": 60.0, "hour": 3600.0}.get(unit.strip(), 60.0)
    return int(count), seconds


class AgentRateLimiter:
    """Sliding-window limiter for the agent endpoint, per client address."""

    def __init__(self, rate: str) -> None:
        self.limit, self.window = _parse_rate(rate)
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        bucket = self.hits[key]
        while bucket and now - bucket[0] > self.window:
            bucket.popleft()
        if len(bucket) >= self.limit:
            return False
        bucket.append(now)
        return True


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, log_agui_events=settings.log_agui_events)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        get_engine()
        logger.info(
            "startup",
            extra={
                "provider": "mock" if settings.mock_model else settings.inference_provider,
                "model": settings.model_id,
                "environment": settings.environment,
            },
        )
        yield

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["*"],
    )
    app.middleware("http")(request_id_middleware)

    limiter = AgentRateLimiter(settings.agent_rate_limit)

    @app.middleware("http")
    async def security_and_rate_limit(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path == AGENT_PATH and request.method == "POST":
            forwarded = request.headers.get("x-forwarded-for", "")
            client = forwarded.split(",")[0].strip() or (
                request.client.host if request.client else "unknown"
            )
            if not limiter.allow(client):
                return JSONResponse({"detail": "Too many requests"}, status_code=429)
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    app.include_router(health.router, tags=["health"])
    app.include_router(intakes.router, tags=["intakes"])
    for module_name in ("app.api.exports", "app.api.repositories"):
        try:
            module = __import__(module_name, fromlist=["router"])
        except ImportError as error:  # pragma: no cover - only while modules are missing
            logger.warning(
                "router.missing", extra={"router_module": module_name, "error": str(error)}
            )
            continue
        app.include_router(module.router, tags=[module_name.rsplit(".", 1)[-1]])

    add_adk_fastapi_endpoint(
        app,
        create_adk_agent(settings),
        path=AGENT_PATH,
        extract_headers=["x-forwarded-user", "x-forwarded-email"],
    )
    return app


app = create_app()
