"""The only module that knows which inference provider is in use.

``create_agent_model`` returns the ADK model for the intake agent; ``completion_kwargs``
gives the structured-extraction pass the same provider; ``health_check`` asks for one token.
``MOCK_MODEL=1`` swaps both for deterministic fixtures.
"""

from __future__ import annotations

import logging
import time
from typing import Any, cast

from google.adk.models.base_llm import BaseLlm
from google.adk.models.lite_llm import LiteLlm
from pydantic import BaseModel

from app.settings import Settings, get_settings

logger = logging.getLogger(__name__)


class HealthStatus(BaseModel):
    ok: bool
    provider: str
    model: str
    latency_ms: int | None = None
    detail: str | None = None


def _provider_kwargs(settings: Settings) -> dict[str, Any]:
    """LiteLLM keyword arguments for the configured provider."""
    if settings.inference_provider == "bedrock":
        kwargs: dict[str, Any] = {}
        if settings.aws_region:
            kwargs["aws_region_name"] = settings.aws_region
        return kwargs
    kwargs = {"api_base": settings.openai_base_url}
    # vLLM-style servers accept any key; LiteLLM insists on one being present.
    kwargs["api_key"] = settings.openai_api_key or "not-needed"
    return kwargs


def completion_kwargs(settings: Settings | None = None) -> dict[str, Any]:
    """Arguments for ``litellm.acompletion`` that select the configured provider."""
    settings = settings or get_settings()
    return {
        "model": settings.model_id,
        "timeout": settings.inference_timeout_s,
        "num_retries": settings.inference_max_retries,
        "drop_params": True,
        **_provider_kwargs(settings),
    }


def create_agent_model(settings: Settings | None = None) -> BaseLlm:
    """The ADK model for the intake agent."""
    settings = settings or get_settings()
    if settings.mock_model:
        from app.inference.mock_model import ScriptedLlm

        logger.info("inference.provider", extra={"provider": "mock", "model": "scripted"})
        return ScriptedLlm()
    logger.info(
        "inference.provider",
        extra={"provider": settings.inference_provider, "model": settings.model_id},
    )
    return cast(BaseLlm, LiteLlm(model=settings.model_id, **completion_kwargs(settings)))


async def health_check(settings: Settings | None = None) -> HealthStatus:
    """One-token completion against the configured provider."""
    settings = settings or get_settings()
    if settings.mock_model:
        return HealthStatus(ok=True, provider="mock", model="scripted", latency_ms=0)
    import litellm

    started = time.perf_counter()
    try:
        kwargs = completion_kwargs(settings)
        kwargs["timeout"] = min(settings.inference_timeout_s, 20)
        kwargs["num_retries"] = 0
        await litellm.acompletion(
            messages=[{"role": "user", "content": "Reply with the single word: ok"}],
            max_tokens=1,
            **kwargs,
        )
    except Exception as error:  # reported, not raised
        return HealthStatus(
            ok=False,
            provider=settings.inference_provider,
            model=settings.model_id,
            detail=type(error).__name__,
        )
    return HealthStatus(
        ok=True,
        provider=settings.inference_provider,
        model=settings.model_id,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
