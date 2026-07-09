"""Data contracts for the skill + harness system.

SOURCE OF TRUTH for every data shape in the project. Extend shapes here; never
redefine them inline in a module. See docs/architecture.md for how they fit.

Design rules encoded in these models:
- The LLM produces `Classification`; code produces every `*Score` and metric.
- `evidence_span` is mandatory provenance on every classification.
- `unclassifiable` is a first-class category, not an error.
- The frozen eval set (`EvalCase`) is the ruler; it is never mutated by code.
- `Correction` is captured and stored only in v0.1 (no promotion).
"""

from __future__ import annotations

from datetime import date as _date
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

# --------------------------------------------------------------------------- #
# Enums / closed vocabularies
# --------------------------------------------------------------------------- #

class Category(str, Enum):
    """The three possible classifications of a work order."""
    FAILURE = "failure"              # unplanned; fixed because something broke
    PRECAUTIONARY = "precautionary"  # planned/scheduled, no fault implied
    UNCLASSIFIABLE = "unclassifiable"  # no fault information present


# Closed failure-mode vocabulary for v0.1 (pump-class starter set).
# Keep CLOSED: an open vocabulary defeats the vocabulary-collapse value.
# Extend deliberately, per asset class, not ad hoc inside a skill.
FAILURE_MODES: tuple[str, ...] = (
    "Bearing Failure",
    "Seal/Packing Leak",
    "Coupling/Alignment",
    "Motor/Electrical",
    "Lubrication",
    "Other",
)


# --------------------------------------------------------------------------- #
# Skill input
# --------------------------------------------------------------------------- #

class WORecord(BaseModel):
    """One raw work-order record — the skill input.

    Fields may be missing (real CMMS data is incomplete). Do not fabricate
    missing values; keep them None and let downstream logic handle the gap.
    """
    wo_id: str
    asset_id: str
    note: str = Field(description="Free-text maintenance note; may be terse/empty.")
    date: _date | None = None
    asset_type: str | None = None
    cost: float | None = Field(default=None, ge=0)


# --------------------------------------------------------------------------- #
# Skill output
# --------------------------------------------------------------------------- #

class Classification(BaseModel):
    """The output of the failure_vs_suspension skill for one record.

    Produced by the LLM (language work). Code must never invent these values.
    """
    wo_id: str
    category: Category
    failure_mode: str | None = Field(
        default=None,
        description="From FAILURE_MODES; must be None unless category==failure.",
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Calibrated 0-1.")
    evidence_span: str = Field(
        description="Substring of the note that drove the decision. Mandatory; "
        "if empty, confidence must be low.",
    )
    needs_review: bool = Field(
        description="True if confidence < derived threshold OR unclassifiable.",
    )
    skill_version: str = Field(description="Provenance: which skill version ran.")

    @model_validator(mode="after")
    def _check_mode_consistency(self) -> Classification:
        if self.category == Category.FAILURE:
            if self.failure_mode is None:
                raise ValueError("failure category requires a failure_mode")
            if self.failure_mode not in FAILURE_MODES:
                raise ValueError(f"failure_mode must be one of {FAILURE_MODES}")
        else:
            if self.failure_mode is not None:
                raise ValueError("failure_mode must be None unless category==failure")
        if not self.evidence_span and self.confidence > 0.5:
            raise ValueError("empty evidence_span requires low confidence")
        return self


# --------------------------------------------------------------------------- #
# Frozen eval set (the ruler) — READ ONLY in all code paths
# --------------------------------------------------------------------------- #

class EvalCase(BaseModel):
    """One human-labeled benchmark case. Ground truth. Never mutated by code.

    Sourced from the calibration experiment's labeling. Two independent labelers
    + adjudication produced `true_category` / `true_failure_mode`.
    """
    record: WORecord
    true_category: Category
    true_failure_mode: str | None = None
    labeler_notes: str | None = None

    @model_validator(mode="after")
    def _check_truth_consistency(self) -> EvalCase:
        if self.true_category == Category.FAILURE:
            if self.true_failure_mode not in FAILURE_MODES:
                raise ValueError("failure eval case needs a valid true_failure_mode")
        elif self.true_failure_mode is not None:
            raise ValueError("non-failure eval case must have true_failure_mode None")
        return self


# --------------------------------------------------------------------------- #
# Harness outputs (produced by CODE, never the LLM)
# --------------------------------------------------------------------------- #

class SkillScore(BaseModel):
    """Result of scoring one skill version against the frozen eval set.

    Every number here is computed by the scoring runner. The LLM never
    produces a SkillScore.
    """
    skill_version: str
    failure_precision: float = Field(ge=0.0, le=1.0)  # headline metric
    failure_recall: float = Field(ge=0.0, le=1.0)
    macro_f1: float = Field(ge=0.0, le=1.0)
    calibration_error: float = Field(ge=0.0, le=1.0, description="ECE; lower better.")
    n_cases: int = Field(ge=0)
    run_id: str
    scored_at: datetime = Field(default_factory=datetime.utcnow)


class GateResult(BaseModel):
    """Output of the regression gate comparing a candidate to the best-so-far."""
    candidate_version: str
    baseline_version: str | None
    decision: Literal["PASS", "FAIL"]
    reason: str = Field(description="Human-readable specific reason for the decision.")


class Correction(BaseModel):
    """A captured human override of a skill output.

    v0.1: STORE ONLY. Never auto-promoted into the eval set or few-shot pool.
    Full provenance so a later, careful human promotion step can use it.
    """
    wo_id: str
    model_output: Classification
    corrected_category: Category
    corrected_failure_mode: str | None = None
    corrected_by: str
    corrected_at: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="after")
    def _check_correction_consistency(self) -> Correction:
        if self.corrected_category == Category.FAILURE:
            if self.corrected_failure_mode not in FAILURE_MODES:
                raise ValueError("failure correction needs a valid failure_mode")
        elif self.corrected_failure_mode is not None:
            raise ValueError("non-failure correction must have failure_mode None")
        return self


class VersionRecord(BaseModel):
    """One entry in the skill version registry: a version and how it scored."""
    skill_version: str
    score: SkillScore
    is_current: bool = False
    registered_at: datetime = Field(default_factory=datetime.utcnow)