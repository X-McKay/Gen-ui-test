"""Settings for the risk review tool. Environment only (``RISK_REVIEW_*``); the model
comes from the application settings so the review runs against the same endpoint."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class RiskReviewSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RISK_REVIEW_", extra="ignore")

    repository_root: Path = Field(default=REPOSITORY_ROOT)
    output_dir: Path = Field(default=REPOSITORY_ROOT / "reports" / "risk-review")
    concurrency: int = Field(default=3, ge=1, le=8, description="Lanes reviewed in parallel")
    step_timeout_s: int = Field(default=900, description="Wall-clock limit for one agent run")
    max_findings_per_lane: int = Field(default=8, ge=1, le=30)
    verify: bool = Field(default=True, description="Run the verifier pass on every finding")
    trace: bool = Field(default=True, description="Write a JSONL trace next to the report")
    # Cost estimates: the self-hosted endpoint is free at the margin, so the default is 0.
    pricing_version: str = Field(default="local-free-v1")
    price_input_per_million: float = Field(default=0.0, ge=0)
    price_output_per_million: float = Field(default=0.0, ge=0)


@lru_cache(maxsize=1)
def get_review_settings() -> RiskReviewSettings:
    return RiskReviewSettings()
