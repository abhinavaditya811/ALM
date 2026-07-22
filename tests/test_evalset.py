"""Task 5: the frozen eval set loader — integrity check + format validation.

Covers: loading the real frozen set, a missing manifest, a hash mismatch (the
set looks mutated), a line-count mismatch, a malformed JSON line, and a line
that is valid JSON but an invalid `EvalCase`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from harness.evalset import (
    DEFAULT_EVAL_SET_PATH,
    EvalSetFormatError,
    EvalSetIntegrityError,
    load_eval_set,
)
from schema.models import Category

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _write_set(tmp_path: Path, lines: list[str], *, count: int | None = None) -> Path:
    """Write a jsonl + matching manifest to tmp_path; return the jsonl path."""
    eval_set_path = tmp_path / "toy.jsonl"
    content = "\n".join(lines) + "\n"
    eval_set_path.write_text(content, encoding="utf-8")

    manifest = {
        "count": count if count is not None else len(lines),
        "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
    }
    manifest_path = eval_set_path.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return eval_set_path


_VALID_CASE = json.dumps(
    {
        "record": {"wo_id": "WO-1", "asset_id": "PUMP-1", "note": "bearing seized"},
        "true_category": "failure",
        "true_failure_mode": "Bearing Failure",
        "labeler_notes": None,
    }
)

_INVALID_SCHEMA_CASE = json.dumps(
    {
        # failure category but no true_failure_mode -> fails EvalCase validator
        "record": {"wo_id": "WO-2", "asset_id": "PUMP-2", "note": "seized"},
        "true_category": "failure",
        "true_failure_mode": None,
    }
)


# --------------------------------------------------------------------------- #
# The real frozen set
# --------------------------------------------------------------------------- #

def test_loads_real_frozen_eval_set() -> None:
    cases = load_eval_set()
    assert len(cases) == 50
    categories = [c.true_category for c in cases]
    assert categories.count(Category.FAILURE) == 30
    assert categories.count(Category.PRECAUTIONARY) == 12
    assert categories.count(Category.UNCLASSIFIABLE) == 8


def test_default_path_points_at_frozen_set() -> None:
    assert DEFAULT_EVAL_SET_PATH == Path("data/evalset/failure_vs_suspension.jsonl")


# --------------------------------------------------------------------------- #
# Happy path (toy set)
# --------------------------------------------------------------------------- #

def test_valid_toy_set_loads(tmp_path: Path) -> None:
    path = _write_set(tmp_path, [_VALID_CASE])
    cases = load_eval_set(path)
    assert len(cases) == 1
    assert cases[0].true_category == Category.FAILURE


# --------------------------------------------------------------------------- #
# Integrity failures
# --------------------------------------------------------------------------- #

def test_missing_eval_set_file_raises(tmp_path: Path) -> None:
    with pytest.raises(EvalSetIntegrityError, match="not found"):
        load_eval_set(tmp_path / "does_not_exist.jsonl")


def test_missing_manifest_raises(tmp_path: Path) -> None:
    path = tmp_path / "toy.jsonl"
    path.write_text(_VALID_CASE + "\n", encoding="utf-8")
    with pytest.raises(EvalSetIntegrityError, match="manifest not found"):
        load_eval_set(path)


def test_tampered_content_fails_hash_check(tmp_path: Path) -> None:
    path = _write_set(tmp_path, [_VALID_CASE])
    # Mutate the file AFTER the manifest was written for its original content.
    path.write_text(_VALID_CASE.replace("Bearing Failure", "Other") + "\n", encoding="utf-8")
    with pytest.raises(EvalSetIntegrityError, match="sha256 mismatch"):
        load_eval_set(path)


def test_line_count_mismatch_raises(tmp_path: Path) -> None:
    path = _write_set(tmp_path, [_VALID_CASE], count=2)
    with pytest.raises(EvalSetIntegrityError, match="expected 2 records"):
        load_eval_set(path)


# --------------------------------------------------------------------------- #
# Format failures (hash/count matches; content itself is bad)
# --------------------------------------------------------------------------- #

def test_malformed_json_line_raises(tmp_path: Path) -> None:
    path = _write_set(tmp_path, ["not valid json"])
    with pytest.raises(EvalSetFormatError, match="invalid JSON"):
        load_eval_set(path)


def test_invalid_evalcase_schema_raises(tmp_path: Path) -> None:
    path = _write_set(tmp_path, [_INVALID_SCHEMA_CASE])
    with pytest.raises(EvalSetFormatError, match="invalid EvalCase"):
        load_eval_set(path)
