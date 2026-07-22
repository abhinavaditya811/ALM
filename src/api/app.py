"""Composition root for the classification API — same spirit as `harness.cli`.

The one place a real `ModelBackend` and skill get wired together and exposed
over HTTP. Real deployments run `uvicorn api.app:create_app --factory`, so
`create_app()` only executes when the server actually starts, never on plain
import. Tests call `create_app(backend=..., api_key=...)` directly.
"""

from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from llm.client import ModelBackend
from llm.registry import BACKENDS
from skills.registry import SKILLS

DEFAULT_BACKEND_NAME = "deepseek"  # the funded account today; anthropic has no credit balance


def _build_backend() -> ModelBackend:
    name = os.environ.get("ANALYTIXLLM_BACKEND", DEFAULT_BACKEND_NAME)
    try:
        return BACKENDS[name]()
    except KeyError:
        raise RuntimeError(f"unknown backend: {name!r} (choices: {sorted(BACKENDS)})") from None


def create_app(*, backend: ModelBackend | None = None, api_key: str | None = None) -> FastAPI:
    """Build the API app.

    `backend`/`api_key` overrides exist for tests only; real deployments
    configure via the `ANALYTIXLLM_BACKEND` / `ANALYTIXLLM_API_KEY` env vars.
    Refuses to build (fail-closed) if no API key is available from either
    source, since the batch-classify endpoint spends real LLM API credits.
    """
    resolved_key = api_key if api_key is not None else os.environ.get("ANALYTIXLLM_API_KEY")
    if not resolved_key:
        raise RuntimeError(
            "ANALYTIXLLM_API_KEY must be set - the batch-classify endpoint requires auth."
        )

    app = FastAPI(title="analytixLLM classification API")
    # Auth is a custom header (x-api-key), not cookies, so a wildcard origin is
    # fine here without allow_credentials — lets a browser-based demo page on
    # any origin (e.g. a local file:// dashboard) call this API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["POST"],
        allow_headers=["x-api-key", "Content-Type"],
    )
    app.state.api_key = resolved_key
    resolved_backend = backend if backend is not None else _build_backend()
    app.state.skill = SKILLS["failure_vs_suspension"](backend=resolved_backend)
    app.include_router(router)
    return app


if __name__ == "__main__":
    uvicorn.run(create_app(), host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
