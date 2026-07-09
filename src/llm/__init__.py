"""Single home for all LLM access.

No LLM calls happen anywhere else in the codebase. Everything goes through
`call_structured`, which takes an injectable backend so tests never touch a
real API. Prompts are versioned files under `src/llm/prompts/` — never inline.
"""

from llm.client import (
    ModelBackend,
    ModelResponse,
    StructuredCallError,
    call_structured,
    load_prompt,
)

__all__ = [
    "ModelBackend",
    "ModelResponse",
    "StructuredCallError",
    "call_structured",
    "load_prompt",
]
