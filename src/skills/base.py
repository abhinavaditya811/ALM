"""The Skill contract every v0.1+ skill implements.

A SKILL is a named, repeatable analytical procedure over one work-order record
with a fixed input/output contract, a version, and a metric. The skill boundary
is the measurement boundary: the harness scores whatever satisfies this
protocol against the frozen eval set.

This module is contract only — no classification logic lives here. The one v0.1
skill (`failure_vs_suspension`) implements it; future skills scaffold from it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from schema.models import Classification, WORecord


@runtime_checkable
class Skill(Protocol):
    """Structural contract for a skill.

    Implementers may back these with plain attributes or properties; only the
    shape matters. `run` does the language work (produces a `Classification`);
    it must never compute metrics or scores — that is the harness's job.
    """

    @property
    def version(self) -> str:
        """Version tag stamped onto every Classification for provenance."""
        ...

    @property
    def metric_name(self) -> str:
        """Name of this skill's headline metric (e.g. 'failure_precision')."""
        ...

    @property
    def eval_set_path(self) -> Path:
        """Path to the frozen eval set this skill is measured against.

        A reference only; the skill never reads or writes the eval set (that is
        the harness's read-only concern, built in a later task).
        """
        ...

    def run(self, record: WORecord) -> Classification:
        """Classify one work-order record. Pure language work."""
        ...
