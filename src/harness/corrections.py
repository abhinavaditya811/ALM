"""Correction capture: STORE ONLY. No promotion, no eval-set write, no retrain.

Design constraints (see CLAUDE.md / docs/architecture.md):
- v0.1 scope is capture only: a human override of a skill output is persisted
  with full provenance to a candidate pool. Promoting a correction into the
  frozen eval set or a few-shot pool is a deferred human step this module
  deliberately does not implement.
- This module never imports or touches `src/harness/evalset.py` or any path
  under `data/evalset/`. No LLM calls.
- Storage is an append-only JSON-lines candidate pool.
"""

from __future__ import annotations

import json
from pathlib import Path

from schema.models import Correction

DEFAULT_CORRECTIONS_PATH = Path("data/corrections/candidates.jsonl")


def capture_correction(correction: Correction, *, path: Path | None = None) -> None:
    """Append `correction` to the candidate pool. Never mutates prior entries."""
    store_path = path if path is not None else DEFAULT_CORRECTIONS_PATH
    store_path.parent.mkdir(parents=True, exist_ok=True)
    with store_path.open("a", encoding="utf-8") as f:
        f.write(correction.model_dump_json() + "\n")


def load_corrections(path: Path | None = None) -> list[Correction]:
    """Return every captured correction, in capture order. Empty if none yet."""
    store_path = path if path is not None else DEFAULT_CORRECTIONS_PATH
    if not store_path.is_file():
        return []
    corrections = []
    for line in store_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            corrections.append(Correction.model_validate(json.loads(line)))
    return corrections
