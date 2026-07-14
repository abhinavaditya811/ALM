"""Task 2: LLM client behavior with a mocked backend (never a real API)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from fakes import ScriptedBackend
from llm.client import (
    ModelResponse,
    StructuredCallError,
    call_structured,
    load_prompt,
)


class _Toy(BaseModel):
    label: str
    score: float


# --------------------------------------------------------------------------- #
# call_structured — happy path
# --------------------------------------------------------------------------- #

def test_returns_validated_object() -> None:
    backend = ScriptedBackend(['{"label": "ok", "score": 0.7}'])
    result = call_structured("classify this", _Toy, backend)
    assert isinstance(result, _Toy)
    assert result.label == "ok"
    assert result.score == 0.7
    assert len(backend.calls) == 1


def test_uses_temperature_zero_by_default() -> None:
    backend = ScriptedBackend(['{"label": "ok", "score": 0.1}'])
    call_structured("prompt", _Toy, backend)
    _, temperature = backend.calls[0]
    assert temperature == 0.0


def test_strips_markdown_code_fence() -> None:
    fenced = '```json\n{"label": "fenced", "score": 0.5}\n```'
    backend = ScriptedBackend([fenced])
    result = call_structured("prompt", _Toy, backend)
    assert result.label == "fenced"


def test_token_counts_do_not_break_call() -> None:
    resp = ModelResponse(
        text='{"label": "x", "score": 0.0}',
        model="fake-model",
        input_tokens=123,
        output_tokens=45,
    )
    backend = ScriptedBackend([resp])
    assert call_structured("p", _Toy, backend).label == "x"


# --------------------------------------------------------------------------- #
# call_structured — retry path
# --------------------------------------------------------------------------- #

def test_malformed_then_valid_exercises_retry() -> None:
    # First response is not JSON; second is valid. Client should recover.
    backend = ScriptedBackend(["not json at all", '{"label": "recovered", "score": 0.9}'])
    result = call_structured("prompt", _Toy, backend, max_retries=2)
    assert result.label == "recovered"
    assert len(backend.calls) == 2
    # The retry prompt must carry a repair hint, not just the original prompt.
    assert "prompt" == backend.calls[0][0]
    assert "invalid" in backend.calls[1][0]


def test_schema_violation_then_valid_exercises_retry() -> None:
    # Parses as JSON but fails the pydantic schema (score missing), then valid.
    backend = ScriptedBackend(['{"label": "x"}', '{"label": "y", "score": 0.3}'])
    result = call_structured("prompt", _Toy, backend, max_retries=2)
    assert result.label == "y"
    assert len(backend.calls) == 2


def test_exhausted_retries_raise() -> None:
    backend = ScriptedBackend(["bad", "still bad", "nope"])
    with pytest.raises(StructuredCallError, match="after 3 attempts"):
        call_structured("prompt", _Toy, backend, max_retries=2)
    assert len(backend.calls) == 3  # max_retries + 1


# --------------------------------------------------------------------------- #
# load_prompt
# --------------------------------------------------------------------------- #

def test_load_prompt_reads_versioned_file(tmp_path: Path) -> None:
    (tmp_path / "skill_v1.txt").write_text("hello prompt", encoding="utf-8")
    assert load_prompt("skill_v1.txt", base_dir=tmp_path) == "hello prompt"


def test_load_prompt_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_prompt("does_not_exist.txt", base_dir=tmp_path)
