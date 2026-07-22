"""Task 7: the regression gate must PASS improvements and FAIL regressions,
with a specific, correct reason string in both directions.
"""

from __future__ import annotations

from harness.gate import METRIC_TOLERANCE, evaluate_gate
from schema.models import SkillScore

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _score(
    version: str,
    *,
    failure_precision: float = 0.8,
    failure_recall: float = 0.8,
    macro_f1: float = 0.8,
    calibration_error: float = 0.1,
) -> SkillScore:
    return SkillScore(
        skill_version=version,
        failure_precision=failure_precision,
        failure_recall=failure_recall,
        macro_f1=macro_f1,
        calibration_error=calibration_error,
        n_cases=50,
        run_id=f"run-{version}",
    )


# --------------------------------------------------------------------------- #
# No baseline
# --------------------------------------------------------------------------- #

def test_no_baseline_always_passes() -> None:
    candidate = _score("v1")
    result = evaluate_gate(candidate, None)
    assert result.decision == "PASS"
    assert result.baseline_version is None
    assert result.candidate_version == "v1"


# --------------------------------------------------------------------------- #
# Clear improvement / within tolerance
# --------------------------------------------------------------------------- #

def test_clear_improvement_passes() -> None:
    baseline = _score("v1", failure_precision=0.80)
    candidate = _score("v2", failure_precision=0.90)
    result = evaluate_gate(candidate, baseline)
    assert result.decision == "PASS"
    assert result.baseline_version == "v1"


def test_within_tolerance_drop_passes() -> None:
    baseline = _score("v1", failure_precision=0.80)
    candidate = _score("v2", failure_precision=0.80 - METRIC_TOLERANCE)
    result = evaluate_gate(candidate, baseline)
    assert result.decision == "PASS"


# --------------------------------------------------------------------------- #
# Regressions (one per tracked metric)
# --------------------------------------------------------------------------- #

def test_failure_precision_regression_fails() -> None:
    baseline = _score("v1", failure_precision=0.80)
    candidate = _score("v2", failure_precision=0.80 - METRIC_TOLERANCE - 0.01)
    result = evaluate_gate(candidate, baseline)
    assert result.decision == "FAIL"
    assert "failure_precision regressed" in result.reason


def test_failure_recall_regression_fails() -> None:
    baseline = _score("v1", failure_recall=0.80)
    candidate = _score("v2", failure_recall=0.80 - METRIC_TOLERANCE - 0.01)
    result = evaluate_gate(candidate, baseline)
    assert result.decision == "FAIL"
    assert "failure_recall regressed" in result.reason


def test_macro_f1_regression_fails() -> None:
    baseline = _score("v1", macro_f1=0.80)
    candidate = _score("v2", macro_f1=0.80 - METRIC_TOLERANCE - 0.01)
    result = evaluate_gate(candidate, baseline)
    assert result.decision == "FAIL"
    assert "macro_f1 regressed" in result.reason


def test_calibration_error_regression_fails() -> None:
    baseline = _score("v1", calibration_error=0.10)
    candidate = _score("v2", calibration_error=0.10 + METRIC_TOLERANCE + 0.01)
    result = evaluate_gate(candidate, baseline)
    assert result.decision == "FAIL"
    assert "calibration_error regressed" in result.reason


def test_calibration_error_improvement_passes() -> None:
    baseline = _score("v1", calibration_error=0.20)
    candidate = _score("v2", calibration_error=0.05)
    result = evaluate_gate(candidate, baseline)
    assert result.decision == "PASS"
