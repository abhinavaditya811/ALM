"""Task 3: the Skill protocol type-checks and a trivial dummy satisfies it."""

from __future__ import annotations

from pathlib import Path

from schema.models import Category, Classification, WORecord
from skills.base import Skill


class DummySkill:
    """Minimal implementation used only to prove the contract is satisfiable."""

    @property
    def version(self) -> str:
        return "dummy@v0"

    @property
    def metric_name(self) -> str:
        return "failure_precision"

    @property
    def eval_set_path(self) -> Path:
        return Path("data/evalset/dummy.jsonl")

    def run(self, record: WORecord) -> Classification:
        return Classification(
            wo_id=record.wo_id,
            category=Category.UNCLASSIFIABLE,
            confidence=0.1,
            evidence_span="",
            needs_review=True,
            skill_version=self.version,
        )


def _accepts_skill(skill: Skill) -> str:
    # If DummySkill did not satisfy the protocol structurally, mypy would fail
    # at the call site below.
    return skill.version


def test_dummy_satisfies_protocol_at_runtime() -> None:
    dummy = DummySkill()
    assert isinstance(dummy, Skill)


def test_dummy_type_checks_as_skill() -> None:
    dummy = DummySkill()
    assert _accepts_skill(dummy) == "dummy@v0"


def test_dummy_run_returns_valid_classification() -> None:
    dummy = DummySkill()
    result = dummy.run(WORecord(wo_id="WO-9", asset_id="PUMP-1", note=""))
    assert isinstance(result, Classification)
    assert result.category == Category.UNCLASSIFIABLE
    assert result.skill_version == "dummy@v0"
