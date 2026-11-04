---
name: ai-usage
description: Fact lane - whether the system uses any machine-learning or generative model, which kind, where the model comes from (hosted API, open weights, in-house), which providers, whether a general-purpose model is involved and whether anything is trained or fine-tuned.
metadata:
  owner: platform
  version: 1.0.0
  governance_tier: low
---

## Use this skill when

- You are assigned the fact lane `ai-usage`.

## Fields

- `ai_system.uses_ai`: true for any ML or statistical model (regression, boosting,
  forecasting, classifiers, embeddings) and for any generative model or LLM API.
- `ai_system.model_types`: llm, vision, speech, classical_ml (regression, boosting,
  forecasting, classifiers), recommender, other. `ai_system.model_providers`: openai,
  anthropic, google, aws_bedrock, azure_openai, mistral, meta, self_hosted, other.
- `ai_system.model_source`: third_party_api (hosted provider API), open_weights (a
  published model you run yourself: Llama, Mistral, Qwen, "self-hosted"), in_house
  (trained by the team).
- `ai_system.gpai_model_used`: true whenever an LLM or other foundation model is used.
- `ai_system.fine_tuned_or_trained`: true when there is training or fine-tuning code or a
  documented training process.

## Where to look

1. Dependency manifests: `requirements*.txt`, `pyproject.toml`, `package.json`, `go.mod`,
   `Gemfile`, `pom.xml`: `openai`, `anthropic`, `google-generativeai`, `litellm`,
   `langchain`, `llama-index`, `transformers`, `torch`, `tensorflow`, `scikit-learn`,
   `xgboost`, `lightgbm`, `prophet`, `sentence-transformers`, `@anthropic-ai/sdk`,
   `@google/generative-ai`, `ai`.
2. Imports and client construction: `search_text` for `OpenAI(|Anthropic(|litellm|
   genai\.|bedrock|chat\.completions|messages\.create|\.fit\(|\.predict\(|pipeline\(`.
3. Model identifiers in config, env and code: `gpt-`, `claude-`, `gemini`, `llama`,
   `qwen`, `mistral`, `MODEL`, `hosted_vllm/`, `bedrock/`.
4. Training: `train.py`, `fine_tune`, notebooks, `fit(`, a `models/` directory with
   weights.

## Traps

- "AI" in a product or dashboard name, in marketing copy or in a company name is not use
  of a model.
- A model library only in a dev or test dependency group, or imported only by tests, is
  not use in the system.
- A README that says a classifier was replaced by rules makes `uses_ai: false`
  (documented) unless code still imports a model.
- `uses_ai: false` needs the manifest search in step 1 to come back empty; cite the
  manifest line that shows the stack instead.

## Completion criteria

`uses_ai` is always recorded (true with the import or dependency line; false with the
manifest checked). When true, record `model_source` and `gpai_model_used`.
