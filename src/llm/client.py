"""The one LLM entry point: prompt + schema -> validated pydantic object.

Design constraints (see CLAUDE.md / docs/architecture.md):
- The LLM does language only; this module never counts, scores, or decides.
- The model call is injected via the `ModelBackend` protocol, so tests supply a
  fake and never hit a real API (and no API key is needed to build/test).
- Structured output is validated against a caller-supplied pydantic model.
  On a schema/JSON violation the call retries up to `max_retries` times, each
  retry appending a repair hint to the prompt.
- Every call logs prompt hash, model, token counts, and latency.
- Prompts are loaded from versioned files under `prompts/`; never inline.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, ValidationError

logger = logging.getLogger("llm.client")

PROMPTS_DIR = Path(__file__).parent / "prompts"

T = TypeVar("T", bound=BaseModel)


# --------------------------------------------------------------------------- #
# Backend contract (injectable / mockable)
# --------------------------------------------------------------------------- #

@dataclass
class ModelResponse:
    """What a backend returns for one completion.

    Token counts default to 0 so fakes need not supply them; a real backend
    fills them from the provider's usage payload.
    """
    text: str
    model: str = "unknown"
    input_tokens: int = 0
    output_tokens: int = 0


@runtime_checkable
class ModelBackend(Protocol):
    """A completion source. The only surface the client depends on.

    Implementations must be deterministic-friendly: honor `temperature`. Tests
    provide a scripted fake; a real provider client would implement this too.
    """

    def complete(self, prompt: str, *, temperature: float) -> ModelResponse:
        ...


class StructuredCallError(RuntimeError):
    """Raised when the model cannot produce schema-valid output within retries."""


# --------------------------------------------------------------------------- #
# Prompt loading (versioned files only)
# --------------------------------------------------------------------------- #

def load_prompt(name: str, *, base_dir: Path | None = None) -> str:
    """Load a versioned prompt file by name (e.g. 'skill_v1.txt').

    Prompts live as files so a prompt change is a reviewable, versioned diff.
    Raises FileNotFoundError if the named prompt does not exist.
    """
    directory = base_dir if base_dir is not None else PROMPTS_DIR
    path = directory / name
    if not path.is_file():
        raise FileNotFoundError(f"prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Structured call with validate-and-retry
# --------------------------------------------------------------------------- #

@dataclass
class _Attempt:
    ok: bool
    error: str | None = field(default=None)


def _extract_json(text: str) -> str:
    """Pull the JSON object out of a model response.

    Tolerates a leading/trailing markdown code fence, which providers often add
    even at temperature 0. Does not otherwise transform the payload.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        # Drop the opening fence line (``` or ```json) and the closing fence.
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


def call_structured(
    prompt: str,
    schema: type[T],
    backend: ModelBackend,
    *,
    temperature: float = 0.0,
    max_retries: int = 2,
    logger_: logging.Logger | None = None,
) -> T:
    """Call the model and return a validated instance of `schema`.

    Retries up to `max_retries` times on JSON/schema violations (so a total of
    `max_retries + 1` attempts). Each retry appends the prior error as a repair
    hint. Raises `StructuredCallError` if every attempt fails.
    """
    log = logger_ if logger_ is not None else logger
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]

    last_error: str | None = None
    current_prompt = prompt

    for attempt in range(max_retries + 1):
        started = time.perf_counter()
        response = backend.complete(current_prompt, temperature=temperature)
        latency_ms = (time.perf_counter() - started) * 1000.0

        log.info(
            "llm_call prompt_hash=%s model=%s attempt=%d/%d "
            "input_tokens=%d output_tokens=%d latency_ms=%.1f",
            prompt_hash,
            response.model,
            attempt + 1,
            max_retries + 1,
            response.input_tokens,
            response.output_tokens,
            latency_ms,
        )

        try:
            payload = json.loads(_extract_json(response.text))
            return schema.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)
            log.warning(
                "llm_call schema_violation prompt_hash=%s attempt=%d error=%s",
                prompt_hash,
                attempt + 1,
                last_error,
            )
            current_prompt = (
                f"{prompt}\n\n"
                "Your previous response was invalid and could not be parsed "
                f"into the required schema. Error: {last_error}\n"
                "Return ONLY a valid JSON object matching the schema."
            )

    raise StructuredCallError(
        f"model did not produce schema-valid output for {schema.__name__} "
        f"after {max_retries + 1} attempts (prompt_hash={prompt_hash}); "
        f"last error: {last_error}"
    )
