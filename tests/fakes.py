"""Test doubles shared across tasks. Kept out of `src/` so no test scaffolding
ships in the package. Tests never hit a real API — they inject these fakes.
"""

from __future__ import annotations

from llm.client import ModelResponse


class ScriptedBackend:
    """A `ModelBackend` that returns canned responses in order.

    Pass either raw strings (wrapped in a `ModelResponse`) or `ModelResponse`
    objects. Records each call's (prompt, temperature) for assertions. Ignores
    the prompt when choosing what to return, so it can simulate a
    malformed-then-valid retry sequence.
    """

    def __init__(self, responses: list[str | ModelResponse], *, model: str = "fake-model") -> None:
        self._responses: list[str | ModelResponse] = list(responses)
        self._model = model
        self.calls: list[tuple[str, float]] = []

    def complete(self, prompt: str, *, temperature: float) -> ModelResponse:
        self.calls.append((prompt, temperature))
        if not self._responses:
            raise AssertionError("ScriptedBackend ran out of scripted responses")
        item = self._responses.pop(0)
        if isinstance(item, ModelResponse):
            return item
        return ModelResponse(text=item, model=self._model, input_tokens=10, output_tokens=5)
