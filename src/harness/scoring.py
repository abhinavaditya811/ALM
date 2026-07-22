"""Scoring runner: skill output + frozen eval set -> `SkillScore`. PURE.

Design constraints (see CLAUDE.md / docs/architecture.md):
- No I/O, no LLM calls. Every function here is a deterministic computation
  over its arguments only. This is the ruler-reading, so it must be exact.
- Classifications are matched to eval cases by `wo_id`; a missing or
  duplicate match is a caller error and raises rather than being silently
  dropped from the denominator.
- "Correct" for both the confusion matrix and calibration is category
  equality (`Classification.category == EvalCase.true_category`); this module
  does not additionally credit/penalize failure_mode agreement.
"""

from __future__ import annotations

from schema.models import Category, Classification, EvalCase, SkillScore

NUM_CALIBRATION_BINS = 10


class ScoringError(ValueError):
    """Raised when classifications and eval cases cannot be matched 1:1."""


def _match(
    classifications: list[Classification], eval_cases: list[EvalCase]
) -> list[tuple[Classification, EvalCase]]:
    if not eval_cases:
        raise ScoringError("cannot score an empty eval set")

    by_wo_id: dict[str, Classification] = {}
    for classification in classifications:
        if classification.wo_id in by_wo_id:
            raise ScoringError(f"duplicate classification for wo_id={classification.wo_id!r}")
        by_wo_id[classification.wo_id] = classification

    pairs: list[tuple[Classification, EvalCase]] = []
    for eval_case in eval_cases:
        wo_id = eval_case.record.wo_id
        matched = by_wo_id.get(wo_id)
        if matched is None:
            raise ScoringError(f"no classification found for eval case wo_id={wo_id!r}")
        pairs.append((matched, eval_case))
    return pairs


def _precision_recall_f1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


def _confusion_counts(
    pairs: list[tuple[Classification, EvalCase]],
) -> dict[Category, tuple[int, int, int]]:
    """Per-category (tp, fp, fn) from one-vs-rest over the 3 categories."""
    counts: dict[Category, list[int]] = {c: [0, 0, 0] for c in Category}
    for classification, eval_case in pairs:
        predicted, truth = classification.category, eval_case.true_category
        for category in Category:
            if predicted == category and truth == category:
                counts[category][0] += 1  # tp
            elif predicted == category and truth != category:
                counts[category][1] += 1  # fp
            elif predicted != category and truth == category:
                counts[category][2] += 1  # fn
    return {c: (v[0], v[1], v[2]) for c, v in counts.items()}


def _calibration_error(pairs: list[tuple[Classification, EvalCase]]) -> float:
    """Expected Calibration Error: bin by stated confidence, compare to accuracy."""
    bins: dict[int, list[tuple[float, bool]]] = {}
    for classification, eval_case in pairs:
        confidence = classification.confidence
        bin_index = min(int(confidence * NUM_CALIBRATION_BINS), NUM_CALIBRATION_BINS - 1)
        correct = classification.category == eval_case.true_category
        bins.setdefault(bin_index, []).append((confidence, correct))

    total = len(pairs)
    error = 0.0
    for entries in bins.values():
        bin_size = len(entries)
        avg_confidence = sum(conf for conf, _ in entries) / bin_size
        accuracy = sum(1 for _, correct in entries if correct) / bin_size
        error += (bin_size / total) * abs(avg_confidence - accuracy)
    return error


def score_skill(
    classifications: list[Classification],
    eval_cases: list[EvalCase],
    *,
    skill_version: str,
    run_id: str,
) -> SkillScore:
    """Compute a `SkillScore` for one skill version over one eval set.

    Raises `ScoringError` if classifications and eval cases cannot be matched
    1:1 by `wo_id` (missing or duplicate coverage).
    """
    pairs = _match(classifications, eval_cases)
    confusion = _confusion_counts(pairs)

    failure_precision, failure_recall, _ = _precision_recall_f1(*confusion[Category.FAILURE])
    f1_scores = [_precision_recall_f1(*confusion[c])[2] for c in Category]
    macro_f1 = sum(f1_scores) / len(f1_scores)

    return SkillScore(
        skill_version=skill_version,
        failure_precision=failure_precision,
        failure_recall=failure_recall,
        macro_f1=macro_f1,
        calibration_error=_calibration_error(pairs),
        n_cases=len(pairs),
        run_id=run_id,
    )


if __name__ == "__main__":  # pragma: no cover
    from harness.cli import main

    main()
