"""A second concrete `ModelBackend`: DeepSeek, via its OpenAI-compatible API.

Design constraints (see CLAUDE.md / docs/architecture.md):
- All LLM calls go through `src/llm/` only. This module is the DeepSeek entry
  point, parallel to `AnthropicBackend` -- nothing else in the skill/harness
  cares which concrete `ModelBackend` is wired in.
- DeepSeek exposes an OpenAI-compatible REST API; we use the `openai` SDK
  pointed at DeepSeek's base URL rather than hand-rolling HTTP.
- No retry or JSON-repair logic here -- `call_structured()` in `llm/client.py`
  already owns that.
"""

from __future__ import annotations

import os

import openai

from llm.client import ModelResponse

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_MAX_TOKENS = 1024


class DeepSeekBackend:
    """A `ModelBackend` backed by DeepSeek's chat completions API.

    Unlike `AnthropicBackend`, DeepSeek accepts `temperature` normally, so it
    is forwarded to the API call here rather than dropped.
    """

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        api_key: str | None = None,
        client: openai.OpenAI | None = None,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        if client is not None:
            self._client = client
        else:
            resolved_key = api_key if api_key is not None else os.environ.get("DEEPSEEK_API_KEY")
            self._client = openai.OpenAI(api_key=resolved_key, base_url=DEEPSEEK_BASE_URL)

    def complete(self, prompt: str, *, temperature: float) -> ModelResponse:
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.choices[0].message.content or ""
        usage = response.usage
        return ModelResponse(
            text=text,
            model=response.model,
            input_tokens=usage.prompt_tokens if usage is not None else 0,
            output_tokens=usage.completion_tokens if usage is not None else 0,
        )
