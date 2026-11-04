"""Logical model policies resolved against the application's inference settings.

The review runs on the same endpoint as the product (``app.settings``); the policy only
chooses the generation settings and whether the reasoning model may think. Resolution is
recorded in the manifest, including the pricing version used for cost estimates.
"""

from __future__ import annotations

from typing import Any, cast

from google.adk.models.base_llm import BaseLlm
from google.adk.models.lite_llm import LiteLlm
from pydantic import BaseModel, ConfigDict

from app.inference.model_factory import completion_kwargs
from app.settings import Settings, get_settings
from risk_review.runtime.spec import ModelSettings, SpecError
from risk_review.settings import RiskReviewSettings, get_review_settings


class ModelPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    max_tokens_ceiling: int
    allow_thinking: bool


MODEL_POLICIES: dict[str, ModelPolicy] = {
    "balanced-v1": ModelPolicy(
        name="balanced-v1",
        description="Default review model; thinking off, bounded output.",
        max_tokens_ceiling=6000,
        allow_thinking=False,
    ),
    "reasoning-v1": ModelPolicy(
        name="reasoning-v1",
        description="Same endpoint with thinking allowed; stricter request budget expected.",
        max_tokens_ceiling=12000,
        allow_thinking=True,
    ),
}


class ResolvedModel(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    policy: str
    provider: str
    model_id: str
    temperature: float
    max_tokens: int
    enable_thinking: bool
    pricing_version: str
    price_per_million: tuple[float, float]


def resolve_model_policy(
    policy_name: str,
    settings: ModelSettings,
    *,
    app_settings: Settings | None = None,
    review_settings: RiskReviewSettings | None = None,
) -> ResolvedModel:
    policy = MODEL_POLICIES.get(policy_name)
    if policy is None:
        raise SpecError(f"unknown model policy {policy_name!r}; known: {sorted(MODEL_POLICIES)}")
    if settings.enable_thinking and not policy.allow_thinking:
        raise SpecError(f"model policy {policy_name!r} does not allow enable_thinking")
    if settings.max_tokens > policy.max_tokens_ceiling:
        raise SpecError(
            f"model policy {policy_name!r} caps max_tokens at {policy.max_tokens_ceiling}"
        )
    app_settings = app_settings or get_settings()
    review_settings = review_settings or get_review_settings()
    return ResolvedModel(
        policy=policy.name,
        provider=app_settings.inference_provider,
        model_id=app_settings.model_id,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        enable_thinking=settings.enable_thinking,
        pricing_version=review_settings.pricing_version,
        price_per_million=(
            review_settings.price_input_per_million,
            review_settings.price_output_per_million,
        ),
    )


def build_model(resolved: ResolvedModel, app_settings: Settings | None = None) -> BaseLlm:
    """The ADK model for a resolved policy. Thinking is switched per request through the
    chat template, which is how the vLLM endpoint expects it."""
    app_settings = app_settings or get_settings()
    kwargs: dict[str, Any] = completion_kwargs(app_settings)
    model_id = str(kwargs.pop("model"))
    kwargs["temperature"] = resolved.temperature
    kwargs["max_tokens"] = resolved.max_tokens
    if app_settings.inference_provider == "openai_compatible":
        kwargs["extra_body"] = {
            "chat_template_kwargs": {"enable_thinking": resolved.enable_thinking}
        }
    return cast(BaseLlm, LiteLlm(model=model_id, **kwargs))
