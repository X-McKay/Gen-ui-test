"""Contract: the extraction tool schema matches IntakeRecord and both providers share it."""

from __future__ import annotations

import json

import pytest

from app.inference.structured_extraction import (
    EXTRACTION_TOOL_NAME,
    extraction_tool_schema,
    parse_tool_arguments,
)
from app.intake.question_bank import QUESTION_BANK, QUESTIONS_BY_FIELD
from app.intake.record_service import coerce_value
from app.intake.schema import field_paths, new_record
from app.settings import Settings


def test_tool_schema_covers_every_askable_field_and_nothing_else() -> None:
    schema = extraction_tool_schema()
    assert schema["function"]["name"] == EXTRACTION_TOOL_NAME
    properties = schema["function"]["parameters"]["properties"]
    assert set(properties) == {spec.field.replace(".", "__") for spec in QUESTION_BANK}
    assert set(properties) <= {path.replace(".", "__") for path in field_paths()}


def test_enum_values_in_the_tool_schema_validate_against_the_record() -> None:
    properties = extraction_tool_schema()["function"]["parameters"]["properties"]
    record = new_record("t")
    for key, prop in properties.items():
        path = key.replace("__", ".")
        value_schema = prop["properties"]["value"]
        samples: list[object] = []
        if value_schema.get("type") == "boolean":
            samples = [True, False]
        elif "enum" in value_schema:
            samples = list(value_schema["enum"])
        elif value_schema.get("type") == "array":
            samples = [list(value_schema["items"]["enum"])]
        else:
            samples = ["free text"]
        for sample in samples:
            record.set_field(
                path, coerce_value(path, sample), source="inferred", confidence=0.5, confirmed=False
            )


def test_parse_tool_arguments_keeps_valid_fields_and_clamps_confidence() -> None:
    arguments = json.dumps(
        {
            "ai_system__uses_ai": {"value": True, "confidence": 1.7, "evidence": "uses an LLM"},
            "use_case__domains": {"value": ["hr_employment"], "confidence": "0.9"},
            "unknown__field": {"value": 1, "confidence": 0.9},
            "project__name": {"value": None, "confidence": 0.9},
            "data__processes_personal_data": "not an object",
        }
    )
    fields = {field.path: field for field in parse_tool_arguments(arguments)}
    assert set(fields) == {"ai_system.uses_ai", "use_case.domains"}
    assert fields["ai_system.uses_ai"].confidence == 1.0
    assert fields["ai_system.uses_ai"].evidence == "uses an LLM"
    assert fields["use_case.domains"].confidence == 0.9


def test_both_providers_share_the_same_completion_contract() -> None:
    from app.inference.model_factory import completion_kwargs

    openai_settings = Settings(
        inference_provider="openai_compatible",
        openai_base_url="https://llm.example/v1",
        model_id="openai/test",
        _env_file=None,  # type: ignore[call-arg]
    )
    bedrock_settings = Settings(
        inference_provider="bedrock",
        model_id="bedrock/anthropic.claude",
        aws_region="eu-west-1",
        _env_file=None,  # type: ignore[call-arg]
    )
    openai_kwargs = completion_kwargs(openai_settings)
    bedrock_kwargs = completion_kwargs(bedrock_settings)
    assert (
        openai_kwargs["model"] == "openai/test"
        and openai_kwargs["api_base"] == "https://llm.example/v1"
    )
    assert bedrock_kwargs["model"] == "bedrock/anthropic.claude"
    assert bedrock_kwargs["aws_region_name"] == "eu-west-1"
    assert "api_key" not in bedrock_kwargs
    # The extraction tool schema does not depend on the provider.
    assert extraction_tool_schema() == extraction_tool_schema()
    assert all(QUESTIONS_BY_FIELD[spec.field] is spec for spec in QUESTION_BANK)


@pytest.mark.asyncio
async def test_abbreviated_first_pass_gets_one_completion_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json
    from types import SimpleNamespace

    import litellm

    from app.inference import structured_extraction as module

    def call(arguments: dict[str, object], prompt: int, completion: int) -> object:
        tool_call = SimpleNamespace(
            function=SimpleNamespace(
                name=module.EXTRACTION_TOOL_NAME, arguments=json.dumps(arguments)
            )
        )
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=[tool_call]))],
            usage=SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion),
        )

    first = {"ai_system__uses_ai": {"value": True, "confidence": 1.0, "evidence": "GPT-4o"}}
    second = {
        "ai_system__uses_ai": {"value": False, "confidence": 0.9},  # already recorded: ignored
        "ai_system__model_source": {
            "value": "third_party_api",
            "confidence": 0.9,
            "evidence": "GPT-4o",
        },
    }
    seen: list[dict[str, object]] = []

    async def fake_acompletion(**kwargs: object) -> object:
        seen.append(kwargs)
        return call(first, 100, 20) if len(seen) == 1 else call(second, 50, 10)

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
    monkeypatch.setattr(module, "get_settings", lambda: SimpleNamespace(mock_model=False))
    monkeypatch.setattr(module, "completion_kwargs", lambda settings: {"model": "test"})

    result = await module.extract_fields_detailed("Built on GPT-4o.")
    assert len(seen) == 2
    properties = seen[1]["tools"][0]["function"]["parameters"]["properties"]  # type: ignore[index]
    assert "ai_system__uses_ai" not in properties and "ai_system__model_source" in properties
    assert "Already recorded: ai_system.uses_ai" in seen[1]["messages"][1]["content"]  # type: ignore[index]
    assert {f.path: f.value for f in result.fields} == {
        "ai_system.uses_ai": True,
        "ai_system.model_source": "third_party_api",
    }
    assert result.prompt_tokens == 150 and result.completion_tokens == 30

    seen.clear()
    full = {
        spec.field.replace(".", "__"): {"value": True, "confidence": 0.85}
        for spec in module.QUESTION_BANK[: module.ABBREVIATED_FIELD_COUNT + 2]
    }
    assert len(full) >= module.ABBREVIATED_FIELD_COUNT

    async def one_full_call(**kwargs: object) -> object:
        seen.append(kwargs)
        return call(full, 100, 20)

    monkeypatch.setattr(litellm, "acompletion", one_full_call)
    await module.extract_fields_detailed("A rules engine.")
    assert len(seen) == 1
