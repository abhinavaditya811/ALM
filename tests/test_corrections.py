"""Task 9: correction capture is STORE ONLY -- round-trips with full
provenance, and never touches the frozen eval set.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from harness.corrections import capture_correction, load_corrections
from harness.evalset import DEFAULT_EVAL_SET_PATH
from schema.models import Category, Classification, Correction


def _model_output(wo_id: str) -> Classification:
    return Classification(
        wo_id=wo_id,
        category=Category.PRECAUTIONARY,
        failure_mode=None,
        confidence=0.55,
        evidence_span="routine check",
        needs_review=True,
        skill_version="failure_vs_suspension@v1",
    )


def _correction(wo_id: str) -> Correction:
    return Correction(
        wo_id=wo_id,
        model_output=_model_output(wo_id),
        corrected_category=Category.FAILURE,
        corrected_failure_mode="Bearing Failure",
        corrected_by="jane.engineer",
    )


def test_capture_and_load_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "candidates.jsonl"
    correction = _correction("WO-1")

    capture_correction(correction, path=path)
    loaded = load_corrections(path=path)

    assert len(loaded) == 1
    assert loaded[0].wo_id == "WO-1"
    assert loaded[0].corrected_category == Category.FAILURE
    assert loaded[0].corrected_failure_mode == "Bearing Failure"
    assert loaded[0].corrected_by == "jane.engineer"
    assert loaded[0].model_output.category == Category.PRECAUTIONARY


def test_multiple_corrections_preserve_order(tmp_path: Path) -> None:
    path = tmp_path / "candidates.jsonl"
    capture_correction(_correction("WO-1"), path=path)
    capture_correction(_correction("WO-2"), path=path)

    loaded = load_corrections(path=path)
    assert [c.wo_id for c in loaded] == ["WO-1", "WO-2"]


def test_load_from_nonexistent_store_returns_empty(tmp_path: Path) -> None:
    assert load_corrections(path=tmp_path / "nothing.jsonl") == []


def test_capture_never_touches_the_frozen_eval_set(tmp_path: Path) -> None:
    before = hashlib.sha256(DEFAULT_EVAL_SET_PATH.read_bytes()).hexdigest()

    path = tmp_path / "candidates.jsonl"
    capture_correction(_correction("WO-1"), path=path)
    capture_correction(_correction("WO-2"), path=path)

    after = hashlib.sha256(DEFAULT_EVAL_SET_PATH.read_bytes()).hexdigest()
    assert before == after
