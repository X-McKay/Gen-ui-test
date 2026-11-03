"""Runtime configuration. Environment only; see ``.env.example`` for every variable."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Governance Intake"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    log_agui_events: bool = Field(default=False, description="Log AG-UI event types (dev only)")

    # Inference ---------------------------------------------------------------------------
    inference_provider: Literal["openai_compatible", "bedrock"] = "openai_compatible"
    openai_base_url: str = "https://llm.almckay.io/v1"
    openai_api_key: str | None = None
    model_id: str = "openai/Qwen3.6-35B-A3B-NVFP4"
    aws_region: str | None = None
    inference_timeout_s: int = 60
    inference_max_retries: int = 2
    mock_model: bool = Field(default=False, validation_alias="MOCK_MODEL")

    # Persistence -------------------------------------------------------------------------
    database_url: str = "sqlite:///./intake.db"

    # Web ---------------------------------------------------------------------------------
    frontend_origin: str = "http://localhost:3000"
    agent_rate_limit: str = "60/minute"
    # Interview threads waiting on the user (a rendered step) hold an execution slot in
    # ag_ui_adk until they finish or go stale, so this is the number of open interviews.
    agent_max_concurrent_runs: int = 200
    agent_execution_timeout_s: int = 600
    default_owner: str | None = None
    intake_webhook_url: str | None = None

    # Repository analysis -----------------------------------------------------------------
    repo_allowed_hosts: list[str] = ["github.com", "gitlab.com", "dev.azure.com"]
    repo_access_token: str | None = None
    repo_clone_timeout_s: int = 120
    repo_max_size_mb: int = 200
    repo_max_files: int = 20000

    @model_validator(mode="after")
    def _validate_provider(self) -> Settings:
        if self.mock_model:
            return self
        if self.inference_provider == "openai_compatible":
            if not self.openai_base_url.startswith(("http://", "https://")):
                raise ValueError(
                    "OPENAI_BASE_URL must be an http(s) URL "
                    f"(got {self.openai_base_url!r}). Set MOCK_MODEL=1 to run offline."
                )
            if not self.model_id.startswith("openai/"):
                raise ValueError(
                    "MODEL_ID must be 'openai/<model id from GET /v1/models>' "
                    f"for INFERENCE_PROVIDER=openai_compatible (got {self.model_id!r})."
                )
        elif self.inference_provider == "bedrock":
            if not self.model_id.startswith("bedrock/"):
                raise ValueError(
                    "MODEL_ID must be 'bedrock/<model-id>' for INFERENCE_PROVIDER=bedrock "
                    f"(got {self.model_id!r})."
                )
            if not (self.aws_region or os.environ.get("AWS_DEFAULT_REGION")):
                raise ValueError("AWS_REGION is required for INFERENCE_PROVIDER=bedrock.")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
