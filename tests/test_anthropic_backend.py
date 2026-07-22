"""Task 11: AnthropicBackend translates our request/response shape correctly.

No real API call here (that would violate "tests never hit a real API") --
a fake object mimicking the `anthropic.Anthropic().messages.create` surface
stands in for the SDK client, injected via the `client` constructor param.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from llm.anthropic_backend import AnthropicBackend


@dataclass
class _FakeTextBlock:
    text: str
    type: str = "text"


@dataclass
class _FakeThinkingBlock:
    thinking: str
    type: str = "thinking"


@dataclass
class _FakeUsage:
    input_tokens: int
    output_tokens: int


@dataclass
class _FakeMessage:
    content: list[object]
    model: str
    usage: _FakeUsage


class _FakeMessagesResource:
    def __init__(self, response: _FakeMessage) -> None:
        self._response = response
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> _FakeMessage:
        self.calls.append(kwargs)
        return self._response


@dataclass
class _FakeAnthropicClient:
    response: _FakeMessage
    messages: _FakeMessagesResource = field(init=False)

    def __post_init__(self) -> None:
        self.messages = _FakeMessagesResource(self.response)


def test_complete_translates_response_into_model_response() -> None:
    fake_response = _FakeMessage(
        content=[_FakeTextBlock(text='{"category": "failure"}')],
        model="claude-opus-4-8",
        usage=_FakeUsage(input_tokens=42, output_tokens=7),
    )
    client = _FakeAnthropicClient(response=fake_response)
    backend = AnthropicBackend(client=client)  # type: ignore[arg-type]

    result = backend.complete("classify this", temperature=0.0)

    assert result.text == '{"category": "failure"}'
    assert result.model == "claude-opus-4-8"
    assert result.input_tokens == 42
    assert result.output_tokens == 7


def test_complete_picks_first_text_block_skipping_others() -> None:
    fake_response = _FakeMessage(
        content=[_FakeThinkingBlock(thinking="reasoning..."), _FakeTextBlock(text="the answer")],
        model="claude-opus-4-8",
        usage=_FakeUsage(input_tokens=10, output_tokens=5),
    )
    client = _FakeAnthropicClient(response=fake_response)
    backend = AnthropicBackend(client=client)  # type: ignore[arg-type]

    result = backend.complete("classify this", temperature=0.0)

    assert result.text == "the answer"


def test_complete_does_not_forward_temperature_to_the_api() -> None:
    """claude-opus-4-8 (and the rest of the current model family) rejects
    non-default temperature/top_p/top_k with a 400 -- this must never be sent.
    """
    fake_response = _FakeMessage(
        content=[_FakeTextBlock(text="ok")],
        model="claude-opus-4-8",
        usage=_FakeUsage(input_tokens=1, output_tokens=1),
    )
    client = _FakeAnthropicClient(response=fake_response)
    backend = AnthropicBackend(client=client)  # type: ignore[arg-type]

    backend.complete("classify this", temperature=0.9)

    assert len(client.messages.calls) == 1
    assert "temperature" not in client.messages.calls[0]
    assert "top_p" not in client.messages.calls[0]


def test_complete_uses_configured_model_and_max_tokens() -> None:
    fake_response = _FakeMessage(
        content=[_FakeTextBlock(text="ok")],
        model="claude-sonnet-5",
        usage=_FakeUsage(input_tokens=1, output_tokens=1),
    )
    client = _FakeAnthropicClient(response=fake_response)
    backend = AnthropicBackend(model="claude-sonnet-5", max_tokens=256, client=client)  # type: ignore[arg-type]

    backend.complete("classify this", temperature=0.0)

    call = client.messages.calls[0]
    assert call["model"] == "claude-sonnet-5"
    assert call["max_tokens"] == 256
    assert call["messages"] == [{"role": "user", "content": "classify this"}]
