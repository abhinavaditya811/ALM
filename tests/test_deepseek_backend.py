"""Task 11: DeepSeekBackend translates our request/response shape correctly.

No real API call here -- a fake object mimicking the
`openai.OpenAI().chat.completions.create` surface stands in for the SDK
client, injected via the `client` constructor param.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from llm.deepseek_backend import DeepSeekBackend


@dataclass
class _FakeMessage:
    content: str | None


@dataclass
class _FakeChoice:
    message: _FakeMessage


@dataclass
class _FakeUsage:
    prompt_tokens: int
    completion_tokens: int


@dataclass
class _FakeCompletion:
    choices: list[_FakeChoice]
    model: str
    usage: _FakeUsage | None


class _FakeCompletionsResource:
    def __init__(self, response: _FakeCompletion) -> None:
        self._response = response
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> _FakeCompletion:
        self.calls.append(kwargs)
        return self._response


class _FakeChatResource:
    def __init__(self, response: _FakeCompletion) -> None:
        self.completions = _FakeCompletionsResource(response)


@dataclass
class _FakeOpenAIClient:
    response: _FakeCompletion
    chat: _FakeChatResource = field(init=False)

    def __post_init__(self) -> None:
        self.chat = _FakeChatResource(self.response)


def test_complete_translates_response_into_model_response() -> None:
    fake_response = _FakeCompletion(
        choices=[_FakeChoice(message=_FakeMessage(content='{"category": "failure"}'))],
        model="deepseek-chat",
        usage=_FakeUsage(prompt_tokens=42, completion_tokens=7),
    )
    client = _FakeOpenAIClient(response=fake_response)
    backend = DeepSeekBackend(client=client)  # type: ignore[arg-type]

    result = backend.complete("classify this", temperature=0.0)

    assert result.text == '{"category": "failure"}'
    assert result.model == "deepseek-chat"
    assert result.input_tokens == 42
    assert result.output_tokens == 7


def test_complete_forwards_temperature_unlike_anthropic_backend() -> None:
    fake_response = _FakeCompletion(
        choices=[_FakeChoice(message=_FakeMessage(content="ok"))],
        model="deepseek-chat",
        usage=_FakeUsage(prompt_tokens=1, completion_tokens=1),
    )
    client = _FakeOpenAIClient(response=fake_response)
    backend = DeepSeekBackend(client=client)  # type: ignore[arg-type]

    backend.complete("classify this", temperature=0.3)

    assert client.chat.completions.calls[0]["temperature"] == 0.3


def test_complete_handles_missing_usage() -> None:
    fake_response = _FakeCompletion(
        choices=[_FakeChoice(message=_FakeMessage(content="ok"))],
        model="deepseek-chat",
        usage=None,
    )
    client = _FakeOpenAIClient(response=fake_response)
    backend = DeepSeekBackend(client=client)  # type: ignore[arg-type]

    result = backend.complete("classify this", temperature=0.0)

    assert result.input_tokens == 0
    assert result.output_tokens == 0


def test_complete_uses_configured_model_and_max_tokens() -> None:
    fake_response = _FakeCompletion(
        choices=[_FakeChoice(message=_FakeMessage(content="ok"))],
        model="deepseek-reasoner",
        usage=_FakeUsage(prompt_tokens=1, completion_tokens=1),
    )
    client = _FakeOpenAIClient(response=fake_response)
    backend = DeepSeekBackend(model="deepseek-reasoner", max_tokens=256, client=client)  # type: ignore[arg-type]

    backend.complete("classify this", temperature=0.0)

    call = client.chat.completions.calls[0]
    assert call["model"] == "deepseek-reasoner"
    assert call["max_tokens"] == 256
    assert call["messages"] == [{"role": "user", "content": "classify this"}]
