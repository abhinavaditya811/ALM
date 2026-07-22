"""The one concrete `ModelBackend` that calls a real model (Anthropic API).

Design constraints (see CLAUDE.md / docs/architecture.md):
- This is the only module in the project that talks to a real LLM provider.
  Everything else (the skill, the LLM client's retry/validation logic) only
  depends on the `ModelBackend` protocol and never imports this module
  directly except at the composition root.
- No retry or JSON-repair logic here -- `call_structured()` in `llm/client.py`
  already owns that. This module's only job is: our prompt in, `ModelResponse`
  out.
- Credentials resolve the same way the SDK always does (`ANTHROPIC_API_KEY`,
  `ANTHROPIC_AUTH_TOKEN`, or an `ant auth login` profile) -- never hardcode a
  key here.
"""

from __future__ import annotations

import anthropic

from llm.client import ModelResponse

# Opus-tier is the default per the project's LLM guidance: don't downgrade to a
# cheaper model without an explicit decision to do so.
DEFAULT_MODEL = "claude-opus-4-8"
DEFAULT_MAX_TOKENS = 1024


class AnthropicBackend:
    """A `ModelBackend` backed by the real Anthropic Messages API.

    `temperature` is accepted (the `ModelBackend` protocol requires it) but
    deliberately NOT forwarded to the API call: `claude-opus-4-8` (and the
    rest of the current Opus/Sonnet-5/Fable-5 model family) rejects
    `temperature`/`top_p`/`top_k` outright with a 400. Determinism is
    controlled by prompting, not sampling parameters, on these models.
    """

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        client: anthropic.Anthropic | None = None,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._client = client if client is not None else anthropic.Anthropic()

    def complete(self, prompt: str, *, temperature: float) -> ModelResponse:
        del temperature  # see class docstring: not supported by this model family
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = next((block.text for block in response.content if block.type == "text"), "")
        return ModelResponse(
            text=text,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
