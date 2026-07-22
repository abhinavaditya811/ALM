"""Which `ModelBackend` to build, by name. Shared by the CLI and the API layer.

Callable (not `type[ModelBackend]`) so a caller/test can register a plain
factory function/lambda, not just another class.
"""

from __future__ import annotations

from collections.abc import Callable

from llm.anthropic_backend import AnthropicBackend
from llm.client import ModelBackend
from llm.deepseek_backend import DeepSeekBackend

BACKENDS: dict[str, Callable[[], ModelBackend]] = {
    "deepseek": DeepSeekBackend,
    "anthropic": AnthropicBackend,
}
