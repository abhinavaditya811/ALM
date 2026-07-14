"""Task 1: exercise every validator branch in src/schema/models.py.

The pydantic models are the source of truth for all data shapes; these tests
pin down the behavior of their consistency validators so later tasks can rely
on them.
"""

import pytest
from pydantic import ValidationError

from schema.models import (
    Category,
    Classification,
    Correction,
    EvalCase,
    WORecord,
)

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _record() -> WORecord:
    return WORecord(wo_id="WO-1", asset_id="PUMP-7", note="bearing seized")


# --------------------------------------------------------------------------- #
# Classification._check_mode_consistency
# --------------------------------------------------------------------------- #

def test_valid_failure_classification() -> None:
    c = Classification(
        wo_id="WO-1",
        category=Category.FAILURE,
        failure_mode="Bearing Failure",
        confidence=0.9,
        evidence_span="bearing seized",
        needs_review=False,
        skill_version="failure_vs_suspension@v1",
    )
    assert c.category == Category.FAILURE
    assert c.failure_mode == "Bearing Failure"


def test_failure_missing_mode_rejected() -> None:
    with pytest.raises(ValidationError, match="failure category requires a failure_mode"):
        Classification(
            wo_id="WO-1",
            category=Category.FAILURE,
            failure_mode=None,
            confidence=0.9,
            evidence_span="bearing seized",
            needs_review=False,
            skill_version="v1",
        )


def test_failure_mode_not_in_vocabulary_rejected() -> None:
    with pytest.raises(ValidationError, match="failure_mode must be one of"):
        Classification(
            wo_id="WO-1",
            category=Category.FAILURE,
            failure_mode="Exploded",  # not in FAILURE_MODES
            confidence=0.9,
            evidence_span="bearing seized",
            needs_review=False,
            skill_version="v1",
        )


def test_non_failure_with_mode_rejected() -> None:
    with pytest.raises(ValidationError, match="failure_mode must be None unless"):
        Classification(
            wo_id="WO-1",
            category=Category.PRECAUTIONARY,
            failure_mode="Bearing Failure",
            confidence=0.8,
            evidence_span="scheduled PM",
            needs_review=False,
            skill_version="v1",
        )


def test_empty_evidence_high_confidence_rejected() -> None:
    with pytest.raises(ValidationError, match="empty evidence_span requires low confidence"):
        Classification(
            wo_id="WO-1",
            category=Category.PRECAUTIONARY,
            failure_mode=None,
            confidence=0.9,  # > 0.5 with empty evidence
            evidence_span="",
            needs_review=False,
            skill_version="v1",
        )


def test_unclassifiable_low_confidence_empty_evidence_accepted() -> None:
    c = Classification(
        wo_id="WO-1",
        category=Category.UNCLASSIFIABLE,
        failure_mode=None,
        confidence=0.2,  # <= 0.5, so empty evidence is allowed
        evidence_span="",
        needs_review=True,
        skill_version="v1",
    )
    assert c.category == Category.UNCLASSIFIABLE
    assert c.evidence_span == ""
    assert c.needs_review is True


def test_empty_evidence_at_threshold_boundary_accepted() -> None:
    # confidence == 0.5 is NOT > 0.5, so empty evidence is permitted (boundary).
    c = Classification(
        wo_id="WO-1",
        category=Category.UNCLASSIFIABLE,
        confidence=0.5,
        evidence_span="",
        needs_review=True,
        skill_version="v1",
    )
    assert c.confidence == 0.5


def test_confidence_out_of_range_rejected() -> None:
    with pytest.raises(ValidationError):
        Classification(
            wo_id="WO-1",
            category=Category.UNCLASSIFIABLE,
            confidence=1.5,  # > 1.0
            evidence_span="",
            needs_review=True,
            skill_version="v1",
        )


# --------------------------------------------------------------------------- #
# WORecord field constraints
# --------------------------------------------------------------------------- #

def test_negative_cost_rejected() -> None:
    with pytest.raises(ValidationError):
        WORecord(wo_id="WO-1", asset_id="PUMP-7", note="x", cost=-5.0)


# --------------------------------------------------------------------------- #
# EvalCase._check_truth_consistency
# --------------------------------------------------------------------------- #

def test_evalcase_valid_failure() -> None:
    ec = EvalCase(
        record=_record(),
        true_category=Category.FAILURE,
        true_failure_mode="Bearing Failure",
    )
    assert ec.true_failure_mode == "Bearing Failure"


def test_evalcase_failure_without_valid_mode_rejected() -> None:
    with pytest.raises(ValidationError, match="failure eval case needs a valid true_failure_mode"):
        EvalCase(
            record=_record(),
            true_category=Category.FAILURE,
            true_failure_mode=None,
        )


def test_evalcase_non_failure_with_mode_rejected() -> None:
    with pytest.raises(ValidationError, match="non-failure eval case must have"):
        EvalCase(
            record=_record(),
            true_category=Category.PRECAUTIONARY,
            true_failure_mode="Bearing Failure",
        )


def test_evalcase_non_failure_none_mode_accepted() -> None:
    ec = EvalCase(
        record=_record(),
        true_category=Category.UNCLASSIFIABLE,
        true_failure_mode=None,
    )
    assert ec.true_failure_mode is None


# --------------------------------------------------------------------------- #
# Correction._check_correction_consistency
# --------------------------------------------------------------------------- #

def _model_output() -> Classification:
    return Classification(
        wo_id="WO-1",
        category=Category.PRECAUTIONARY,
        confidence=0.7,
        evidence_span="scheduled PM",
        needs_review=False,
        skill_version="v1",
    )


def test_correction_valid_failure() -> None:
    corr = Correction(
        wo_id="WO-1",
        model_output=_model_output(),
        corrected_category=Category.FAILURE,
        corrected_failure_mode="Seal/Packing Leak",
        corrected_by="engineer@site",
    )
    assert corr.corrected_failure_mode == "Seal/Packing Leak"


def test_correction_failure_without_valid_mode_rejected() -> None:
    with pytest.raises(ValidationError, match="failure correction needs a valid failure_mode"):
        Correction(
            wo_id="WO-1",
            model_output=_model_output(),
            corrected_category=Category.FAILURE,
            corrected_failure_mode=None,
            corrected_by="engineer@site",
        )


def test_correction_non_failure_with_mode_rejected() -> None:
    with pytest.raises(ValidationError, match="non-failure correction must have failure_mode None"):
        Correction(
            wo_id="WO-1",
            model_output=_model_output(),
            corrected_category=Category.UNCLASSIFIABLE,
            corrected_failure_mode="Bearing Failure",
            corrected_by="engineer@site",
        )


def test_correction_non_failure_none_mode_accepted() -> None:
    corr = Correction(
        wo_id="WO-1",
        model_output=_model_output(),
        corrected_category=Category.UNCLASSIFIABLE,
        corrected_failure_mode=None,
        corrected_by="engineer@site",
    )
    assert corr.corrected_category == Category.UNCLASSIFIABLE
