"""Guards for dependencies that nothing in ``app`` imports directly but the live path needs."""

from __future__ import annotations

import importlib


def test_litellm_lazy_dependencies_are_installed() -> None:
    """LiteLLM imports ``mcp`` lazily inside its chat-completion path and ``boto3`` for Bedrock.

    Neither module appears in ``app``, so a dependency clean-up can drop them without any unit
    test failing; only a live model call would. Keep them declared in ``pyproject.toml``.
    """
    for module in ("mcp", "boto3"):
        assert importlib.import_module(module) is not None
