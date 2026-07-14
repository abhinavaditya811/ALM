"""The one v0.1 skill: classify a work order as failure / precautionary /
unclassifiable, with a normalized failure_mode, calibrated confidence, and a
mandatory evidence_span.

Boundary discipline (CLAUDE.md invariants):
- The LLM does language only: it returns a `ClassificationDraft`.
- Code does the rest: it stamps provenance (wo_id, skill_version), derives
  `needs_review` from a threshold, and shortcuts empty notes WITHOUT an LLM call.
"""

from __future__ import annotations

from pathlib import Path

from llm.client import ModelBackend, call_structured, load_prompt
from schema.models import (
    FAILURE_MODES,
    Category,
    Classification,
    ClassificationDraft,
    WORecord,
)
from skills.failure_vs_suspension.examples import render_examples

# Below this stated confidence, or whenever the category is unclassifiable, the
# output is flagged for human review. This is a CODE decision (a threshold), not
# language — the model never sets it.
REVIEW_THRESHOLD = 0.6

# A note this short carries no usable fault information; classify as
# unclassifiable without spending an LLM call.
NEAR_EMPTY_MIN_CHARS = 3

# Reference only; the skill never reads or writes the eval set in v0.1.
DEFAULT_EVAL_SET_PATH = Path("data/evalset/failure_vs_suspension.jsonl")


class FailureVsSuspensionSkill:
    """Implements the `Skill` protocol (see skills/base.py)."""

    VERSION = "failure_vs_suspension@v1"
    METRIC_NAME = "failure_precision"
    PROMPT_FILE = "failure_vs_suspension_v1.txt"

    def __init__(
        self,
        backend: ModelBackend,
        *,
        eval_set_path: Path | None = None,
    ) -> None:
        self._backend = backend
        self._eval_set_path = eval_set_path if eval_set_path is not None else DEFAULT_EVAL_SET_PATH
        # Load the versioned prompt once; a missing prompt should fail loudly.
        self._template = load_prompt(self.PROMPT_FILE)

    # --- Skill protocol surface ------------------------------------------- #

    @property
    def version(self) -> str:
        return self.VERSION

    @property
    def metric_name(self) -> str:
        return self.METRIC_NAME

    @property
    def eval_set_path(self) -> Path:
        return self._eval_set_path

    def run(self, record: WORecord) -> Classification:
        """Classify one record. Empty/near-empty notes shortcut with no LLM call."""
        if len(record.note.strip()) < NEAR_EMPTY_MIN_CHARS:
            return self._unclassifiable(record)

        prompt = self._build_prompt(record)
        draft = call_structured(prompt, ClassificationDraft, self._backend)
        return self._assemble(record, draft)

    # --- internals -------------------------------------------------------- #

    def _build_prompt(self, record: WORecord) -> str:
        return (
            self._template
            .replace("[[FAILURE_MODES]]", ", ".join(FAILURE_MODES))
            .replace("[[EXAMPLES]]", render_examples())
            .replace("[[ASSET_TYPE]]", record.asset_type or "unknown")
            .replace("[[NOTE]]", record.note)
        )

    def _assemble(self, record: WORecord, draft: ClassificationDraft) -> Classification:
        needs_review = (
            draft.confidence < REVIEW_THRESHOLD
            or draft.category == Category.UNCLASSIFIABLE
        )
        return Classification(
            wo_id=record.wo_id,
            category=draft.category,
            failure_mode=draft.failure_mode,
            confidence=draft.confidence,
            evidence_span=draft.evidence_span,
            needs_review=needs_review,
            skill_version=self.VERSION,
        )

    def _unclassifiable(self, record: WORecord) -> Classification:
        return Classification(
            wo_id=record.wo_id,
            category=Category.UNCLASSIFIABLE,
            failure_mode=None,
            confidence=0.0,
            evidence_span="",
            needs_review=True,
            skill_version=self.VERSION,
        )
