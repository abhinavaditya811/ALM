"""Task 10: end-to-end proof that the harness loop turns.

Mocked model only; no real API. Scores a v1 run, registers it, scores a "v2"
run (a different mocked backend simulating a changed/improved prompt -- see
`_SimulatedV2Skill` below), runs the gate, registers the outcome, and
captures one human correction. Ties every harness component (evalset,
scoring, gate, registry, corrections) together for real.
"""

from __future__ import annotations

from pathlib import Path

from fakes import ConstantBackend
from harness.corrections import capture_correction, load_corrections
from harness.evalset import load_eval_set
from harness.gate import evaluate_gate
from harness.registry import current_version, history, register_version
from harness.scoring import score_skill
from schema.models import Category, Correction, VersionRecord
from skills.failure_vs_suspension import FailureVsSuspensionSkill


class _SimulatedV2Skill(FailureVsSuspensionSkill):
    """Same skill logic; a distinct version tag standing in for a v2 prompt.

    Task 10 only asks to "simulate a changed prompt via a different mock" --
    building an actual second prompt/skill is out of v0.1 scope (BUILD_PLAN's
    "no second skill" non-goal). This subclass exists only in this test.
    """

    VERSION = "failure_vs_suspension@v2-sim"


# v1: guesses "precautionary" for everything -> wrong on all 30 failure cases.
_WEAK_RESPONSE = (
    '{"category": "precautionary", "failure_mode": null, '
    '"confidence": 0.55, "evidence_span": "routine check"}'
)
# v2: guesses "failure"/Bearing Failure with high confidence for everything ->
# correct on the 30 failure cases, wrong on the 20 non-failure cases. Enough
# of an improvement in failure_precision/recall for the gate to PASS.
_STRONG_RESPONSE = (
    '{"category": "failure", "failure_mode": "Bearing Failure", '
    '"confidence": 0.9, "evidence_span": "bearing noise"}'
)


def test_harness_loop_turns(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.jsonl"
    corrections_path = tmp_path / "corrections.jsonl"

    eval_cases = load_eval_set()

    # --- v1: score, register as the first (and thus automatically current) version.
    v1_skill = FailureVsSuspensionSkill(ConstantBackend(_WEAK_RESPONSE))
    v1_classifications = [v1_skill.run(case.record) for case in eval_cases]
    v1_score = score_skill(
        v1_classifications, eval_cases, skill_version=v1_skill.version, run_id="run-v1"
    )
    register_version(
        VersionRecord(skill_version=v1_skill.version, score=v1_score, is_current=True),
        path=registry_path,
    )

    v1_current = current_version(path=registry_path)
    assert v1_current is not None
    assert v1_current.skill_version == v1_skill.version

    # --- v2: score against the same registered baseline, gate, then register.
    v2_skill = _SimulatedV2Skill(ConstantBackend(_STRONG_RESPONSE))
    v2_classifications = [v2_skill.run(case.record) for case in eval_cases]
    v2_score = score_skill(
        v2_classifications, eval_cases, skill_version=v2_skill.version, run_id="run-v2"
    )

    baseline = current_version(path=registry_path)
    assert baseline is not None
    gate_result = evaluate_gate(v2_score, baseline.score)

    register_version(
        VersionRecord(
            skill_version=v2_skill.version,
            score=v2_score,
            is_current=(gate_result.decision == "PASS"),
        ),
        path=registry_path,
    )

    assert gate_result.decision == "PASS"
    assert gate_result.baseline_version == v1_skill.version

    all_history = history(path=registry_path)
    assert [r.skill_version for r in all_history] == [v1_skill.version, v2_skill.version]
    assert [r.is_current for r in all_history] == [False, True]

    v2_current = current_version(path=registry_path)
    assert v2_current is not None
    assert v2_current.skill_version == v2_skill.version

    # --- capture one human correction on a v1 miss (a true-failure case v1 got wrong).
    v1_miss = next(
        c
        for c, case in zip(v1_classifications, eval_cases, strict=True)
        if case.true_category == Category.FAILURE and c.category != Category.FAILURE
    )
    correction = Correction(
        wo_id=v1_miss.wo_id,
        model_output=v1_miss,
        corrected_category=Category.FAILURE,
        corrected_failure_mode="Bearing Failure",
        corrected_by="jane.engineer",
    )
    capture_correction(correction, path=corrections_path)

    stored = load_corrections(path=corrections_path)
    assert len(stored) == 1
    assert stored[0].wo_id == v1_miss.wo_id
    assert stored[0].corrected_category == Category.FAILURE
