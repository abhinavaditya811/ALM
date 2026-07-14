"""Frozen eval set loader — the read-only ruler a skill is scored against.

Design constraints (see CLAUDE.md / docs/architecture.md):
- The eval set is READ-ONLY. This module exposes a loader only; there is no
  save/write function anywhere here, by design.
- Integrity is checked on every load: the `.jsonl` file's line count and
  sha256 must match a companion `.manifest.json`. A drift (accidental edit,
  corruption, a hand "fix" to a label) raises rather than silently scoring
  against a mutated ruler.
- Malformed records raise immediately; nothing is skipped or guessed at.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import ValidationError

from schema.models import EvalCase

DEFAULT_EVAL_SET_PATH = Path("data/evalset/failure_vs_suspension.jsonl")


class EvalSetIntegrityError(RuntimeError):
    """Raised when the eval set file does not match its manifest (count/hash)."""


class EvalSetFormatError(RuntimeError):
    """Raised when a record is not valid JSON or fails `EvalCase` validation."""


def _manifest_path(eval_set_path: Path) -> Path:
    return eval_set_path.with_suffix(".manifest.json")


def _load_manifest(manifest_path: Path) -> tuple[int, str]:
    if not manifest_path.is_file():
        raise EvalSetIntegrityError(f"eval set manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    try:
        return int(manifest["count"]), str(manifest["sha256"])
    except KeyError as exc:
        raise EvalSetIntegrityError(
            f"manifest at {manifest_path} missing required key: {exc}"
        ) from exc


def load_eval_set(path: Path | None = None) -> list[EvalCase]:
    """Load and validate the frozen eval set. Read-only; no write path exists.

    Raises `EvalSetIntegrityError` if the file's hash or line-count does not
    match its manifest (the set looks mutated). Raises `EvalSetFormatError` if
    any line is not valid JSON or fails `EvalCase` validation.
    """
    eval_set_path = path if path is not None else DEFAULT_EVAL_SET_PATH
    if not eval_set_path.is_file():
        raise EvalSetIntegrityError(f"eval set file not found: {eval_set_path}")

    expected_count, expected_sha256 = _load_manifest(_manifest_path(eval_set_path))

    raw = eval_set_path.read_bytes()
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if actual_sha256 != expected_sha256:
        raise EvalSetIntegrityError(
            f"eval set {eval_set_path} failed integrity check: sha256 mismatch "
            f"(expected {expected_sha256}, got {actual_sha256}). The frozen eval "
            "set may have been mutated."
        )

    lines = [line for line in raw.decode("utf-8").splitlines() if line.strip()]
    if len(lines) != expected_count:
        raise EvalSetIntegrityError(
            f"eval set {eval_set_path} failed integrity check: expected "
            f"{expected_count} records, found {len(lines)}."
        )

    cases: list[EvalCase] = []
    for line_no, line in enumerate(lines, start=1):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise EvalSetFormatError(f"{eval_set_path}:{line_no}: invalid JSON: {exc}") from exc
        try:
            cases.append(EvalCase.model_validate(payload))
        except ValidationError as exc:
            raise EvalSetFormatError(
                f"{eval_set_path}:{line_no}: invalid EvalCase: {exc}"
            ) from exc

    return cases
