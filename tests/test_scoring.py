"""Task 6: the scoring runner is pure and must be exact — known-answer tests.

5 hand-built cases with by-hand-computed precision/recall/F1/ECE (see
docs/architecture.md or PR description for the worked arithmetic). Also
covers the matching failures (missing/duplicate wo_id, empty eval set).
"""

from __future__ import annotations

import pytest

from harness.scoring import ScoringError, score_skill
from schema.models import Category, Classification, EvalCase, WORecord

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _classification(
    wo_id: str, category: Category, confidence: float, *, failure_mode: str | None = None
) -> Classification:
    return Classification(
        wo_id=wo_id,
        category=category,
        failure_mode=failure_mode,
        confidence=confidence,
        evidence_span="evidence" if confidence > 0.5 else "",
        needs_review=confidence < 0.6,
        skill_version="failure_vs_suspension@v1",
    )


def _eval_case(
    wo_id: str, true_category: Category, *, true_failure_mode: str | None = None
) -> EvalCase:
    return EvalCase(
        record=WORecord(wo_id=wo_id, asset_id="PUMP-1", note="note"),
        true_category=true_category,
        true_failure_mode=true_failure_mode,
    )


# --------------------------------------------------------------------------- #
# Known-answer set:
#   wo-1: pred failure/Bearing Failure conf=0.9 | true failure/Bearing Failure -> correct
#   wo-2: pred precautionary        conf=0.8 | true failure/Seal/Packing Leak -> wrong
#   wo-3: pred precautionary        conf=0.85| true precautionary             -> correct
#   wo-4: pred unclassifiable       conf=0.1 | true unclassifiable            -> correct
#   wo-5: pred failure/Motor/Electrical conf=0.4 | true failure/Motor/Electrical -> correct
# --------------------------------------------------------------------------- #

def _known_answer_pairs() -> tuple[list[Classification], list[EvalCase]]:
    classifications = [
        _classification("wo-1", Category.FAILURE, 0.9, failure_mode="Bearing Failure"),
        _classification("wo-2", Category.PRECAUTIONARY, 0.8),
        _classification("wo-3", Category.PRECAUTIONARY, 0.85),
        _classification("wo-4", Category.UNCLASSIFIABLE, 0.1),
        _classification("wo-5", Category.FAILURE, 0.4, failure_mode="Motor/Electrical"),
    ]
    eval_cases = [
        _eval_case("wo-1", Category.FAILURE, true_failure_mode="Bearing Failure"),
        _eval_case("wo-2", Category.FAILURE, true_failure_mode="Seal/Packing Leak"),
        _eval_case("wo-3", Category.PRECAUTIONARY),
        _eval_case("wo-4", Category.UNCLASSIFIABLE),
        _eval_case("wo-5", Category.FAILURE, true_failure_mode="Motor/Electrical"),
    ]
    return classifications, eval_cases


def test_known_answer_metrics() -> None:
    classifications, eval_cases = _known_answer_pairs()
    score = score_skill(
        classifications, eval_cases, skill_version="failure_vs_suspension@v1", run_id="run-1"
    )

    # failure: tp=2 (wo-1, wo-5), fp=0, fn=1 (wo-2 missed)
    assert score.failure_precision == pytest.approx(1.0)
    assert score.failure_recall == pytest.approx(2 / 3)

    # macro F1 = mean(f1_failure=0.8, f1_precautionary=2/3, f1_unclassifiable=1.0)
    assert score.macro_f1 == pytest.approx(37 / 45)

    # ECE across 4 confidence bins (0.1, 0.4, {0.8, 0.85}, 0.9) = 0.45
    assert score.calibration_error == pytest.approx(0.45)

    assert score.n_cases == 5
    assert score.skill_version == "failure_vs_suspension@v1"
    assert score.run_id == "run-1"


def test_perfect_score_all_correct_high_confidence() -> None:
    # All 3 categories represented and every prediction correct -> macro_f1 == 1.0.
    classifications = [
        _classification("wo-1", Category.FAILURE, 1.0, failure_mode="Other"),
        _classification("wo-2", Category.PRECAUTIONARY, 1.0),
        _classification("wo-3", Category.UNCLASSIFIABLE, 1.0),
    ]
    eval_cases = [
        _eval_case("wo-1", Category.FAILURE, true_failure_mode="Other"),
        _eval_case("wo-2", Category.PRECAUTIONARY),
        _eval_case("wo-3", Category.UNCLASSIFIABLE),
    ]
    score = score_skill(classifications, eval_cases, skill_version="v1", run_id="run-2")
    assert score.failure_precision == pytest.approx(1.0)
    assert score.failure_recall == pytest.approx(1.0)
    assert score.macro_f1 == pytest.approx(1.0)
    assert score.calibration_error == pytest.approx(0.0)


def test_macro_f1_penalizes_unrepresented_categories() -> None:
    # Only `failure` appears; the other 2 categories get precision=recall=f1=0,
    # which macro-averaging (over the fixed 3-category set) must reflect.
    classifications = [_classification("wo-1", Category.FAILURE, 1.0, failure_mode="Other")]
    eval_cases = [_eval_case("wo-1", Category.FAILURE, true_failure_mode="Other")]
    score = score_skill(classifications, eval_cases, skill_version="v1", run_id="run-2b")
    assert score.macro_f1 == pytest.approx(1 / 3)


# --------------------------------------------------------------------------- #
# Matching failures
# --------------------------------------------------------------------------- #

def test_missing_classification_raises() -> None:
    eval_cases = [_eval_case("wo-1", Category.FAILURE, true_failure_mode="Other")]
    with pytest.raises(ScoringError, match="no classification found"):
        score_skill([], eval_cases, skill_version="v1", run_id="run-3")


def test_duplicate_classification_raises() -> None:
    classifications = [
        _classification("wo-1", Category.FAILURE, 0.9, failure_mode="Other"),
        _classification("wo-1", Category.FAILURE, 0.9, failure_mode="Other"),
    ]
    eval_cases = [_eval_case("wo-1", Category.FAILURE, true_failure_mode="Other")]
    with pytest.raises(ScoringError, match="duplicate classification"):
        score_skill(classifications, eval_cases, skill_version="v1", run_id="run-4")


def test_empty_eval_set_raises() -> None:
    with pytest.raises(ScoringError, match="empty eval set"):
        score_skill([], [], skill_version="v1", run_id="run-5")
