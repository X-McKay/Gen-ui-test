"""A scripted ADK model for component tests: replays a fixed list of responses and attaches
usage metadata so the ledger has numbers to count."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import PrivateAttr


def call(name: str, args: dict[str, Any]) -> LlmResponse:
    part = types.Part(function_call=types.FunctionCall(name=name, args=args))
    return LlmResponse(content=types.Content(role="model", parts=[part]), turn_complete=True)


def text(message: str) -> LlmResponse:
    return LlmResponse(
        content=types.Content(role="model", parts=[types.Part(text=message)]), turn_complete=True
    )


class ScriptedLlm(BaseLlm):
    model: str = "scripted"
    _script: list[LlmResponse] = PrivateAttr(default_factory=list)
    _calls: int = PrivateAttr(default=0)
    _requests: list[LlmRequest] = PrivateAttr(default_factory=list)

    @classmethod
    def with_script(cls, script: list[LlmResponse]) -> ScriptedLlm:
        instance = cls()
        instance._script = list(script)
        return instance

    @property
    def requests(self) -> list[LlmRequest]:
        return self._requests

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        self._requests.append(llm_request)
        index = min(self._calls, len(self._script) - 1)
        self._calls += 1
        response = self._script[index].model_copy(deep=True)
        response.usage_metadata = types.GenerateContentResponseUsageMetadata(
            prompt_token_count=100, candidates_token_count=20, total_token_count=120
        )
        yield response
