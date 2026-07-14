"""Regression gate: candidate `SkillScore` vs. the registry's current best. PURE.

Design constraints (see CLAUDE.md / docs/architecture.md):
- No I/O, no LLM calls. Deterministic function of its two arguments only.
- A version ships only if it does not regress any tracked metric beyond
  tolerance. No baseline (first version ever scored) always PASSes.
"""

from __future__ import annotations

from schema.models import GateResult, SkillScore

# Tolerance for each tracked metric, applied per-metric (not just the
# headline). Higher-is-better metrics may drop by up to this much vs. the
# baseline and still PASS; calibration_error (lower is better) may rise by
# up to this much. A judgment call, not derived from data.
METRIC_TOLERANCE = 0.02

_HIGHER_IS_BETTER: tuple[str, ...] = ("failure_precision", "failure_recall", "macro_f1")
_LOWER_IS_BETTER: tuple[str, ...] = ("calibration_error",)


def evaluate_gate(candidate: SkillScore, baseline: SkillScore | None) -> GateResult:
    """PASS/FAIL `candidate` against `baseline` (the registry's current best).

    PASSes if `baseline` is None (nothing registered yet) or if every tracked
    metric is within `METRIC_TOLERANCE` of the baseline. Otherwise FAILs with
    the first offending metric named in `reason`.
    """
    if baseline is None:
        return GateResult(
            candidate_version=candidate.skill_version,
            baseline_version=None,
            decision="PASS",
            reason="no baseline registered yet; first version always passes",
        )

    for metric in _HIGHER_IS_BETTER:
        cand_value: float = getattr(candidate, metric)
        base_value: float = getattr(baseline, metric)
        if cand_value < base_value - METRIC_TOLERANCE:
            return GateResult(
                candidate_version=candidate.skill_version,
                baseline_version=baseline.skill_version,
                decision="FAIL",
                reason=(
                    f"{metric} regressed: candidate={cand_value:.4f} < "
                    f"baseline={base_value:.4f} - tolerance={METRIC_TOLERANCE}"
                ),
            )

    for metric in _LOWER_IS_BETTER:
        cand_value = getattr(candidate, metric)
        base_value = getattr(baseline, metric)
        if cand_value > base_value + METRIC_TOLERANCE:
            return GateResult(
                candidate_version=candidate.skill_version,
                baseline_version=baseline.skill_version,
                decision="FAIL",
                reason=(
                    f"{metric} regressed: candidate={cand_value:.4f} > "
                    f"baseline={base_value:.4f} + tolerance={METRIC_TOLERANCE}"
                ),
            )

    return GateResult(
        candidate_version=candidate.skill_version,
        baseline_version=baseline.skill_version,
        decision="PASS",
        reason="all tracked metrics within tolerance of baseline",
    )
