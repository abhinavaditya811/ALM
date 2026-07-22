"""Batch classification orchestration — the logic behind the API route.

Design constraints (see CLAUDE.md / docs/architecture.md):
- No FastAPI import here. This is independently unit-testable with a fake
  `ModelBackend`-backed skill, the same way `harness.cli.run_scoring` is.
- One bad record must never sink an entire batch: any exception from
  `skill.run()` is isolated as a `ClassificationError`, not raised.
"""

from __future__ import annotations

import logging

from schema.models import BatchClassifyResponse, Classification, ClassificationError, WORecord
from skills.base import Skill

logger = logging.getLogger("api.service")


def classify_batch(skill: Skill, records: list[WORecord]) -> BatchClassifyResponse:
    """Classify each record with `skill`, isolating per-record failures.

    Any exception raised by `skill.run()` for one record (e.g. a
    `StructuredCallError` after retries exhausted, or a transient
    provider/network error) is caught and logged rather than aborting the
    rest of the batch.
    """
    classifications: list[Classification] = []
    errors: list[ClassificationError] = []
    for record in records:
        try:
            classifications.append(skill.run(record))
        except Exception as exc:  # deliberately broad, see module docstring
            logger.warning("batch_classify record_failed wo_id=%s error=%s", record.wo_id, exc)
            errors.append(ClassificationError(wo_id=record.wo_id, error=str(exc)))

    return BatchClassifyResponse(
        classifications=classifications,
        errors=errors,
        skill_version=skill.version,
        n_requested=len(records),
    )
