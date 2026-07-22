"""Task 8: version registry -- register, current pointer, history, rollback.

All tests use an explicit `tmp_path`-backed registry file; the real default
path is never touched by tests (nothing has been legitimately registered yet).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.registry import RegistryError, current_version, history, register_version, rollback
from schema.models import SkillScore, VersionRecord


def _score(version: str, *, failure_precision: float = 0.8) -> SkillScore:
    return SkillScore(
        skill_version=version,
        failure_precision=failure_precision,
        failure_recall=0.8,
        macro_f1=0.8,
        calibration_error=0.1,
        n_cases=50,
        run_id=f"run-{version}",
    )


def _record(version: str, *, is_current: bool, failure_precision: float = 0.8) -> VersionRecord:
    return VersionRecord(
        skill_version=version,
        score=_score(version, failure_precision=failure_precision),
        is_current=is_current,
    )


def test_register_first_version_becomes_current(tmp_path: Path) -> None:
    path = tmp_path / "registry.jsonl"
    register_version(_record("v1", is_current=True), path=path)

    assert current_version(path=path).skill_version == "v1"  # type: ignore[union-attr]
    assert [r.skill_version for r in history(path=path)] == ["v1"]


def test_registering_new_current_clears_prior_current(tmp_path: Path) -> None:
    path = tmp_path / "registry.jsonl"
    register_version(_record("v1", is_current=True), path=path)
    register_version(_record("v2", is_current=True, failure_precision=0.9), path=path)

    current = current_version(path=path)
    assert current is not None
    assert current.skill_version == "v2"

    all_records = history(path=path)
    assert [r.skill_version for r in all_records] == ["v1", "v2"]
    assert [r.is_current for r in all_records] == [False, True]
    # Prior record's score is untouched, only its is_current flag changed.
    assert all_records[0].score.failure_precision == 0.8


def test_registering_non_current_does_not_disturb_current(tmp_path: Path) -> None:
    path = tmp_path / "registry.jsonl"
    register_version(_record("v1", is_current=True), path=path)
    register_version(_record("v2", is_current=False), path=path)

    current = current_version(path=path)
    assert current is not None
    assert current.skill_version == "v1"


def test_rollback_to_prior_version(tmp_path: Path) -> None:
    path = tmp_path / "registry.jsonl"
    register_version(_record("v1", is_current=True), path=path)
    register_version(_record("v2", is_current=True, failure_precision=0.9), path=path)

    rolled_back = rollback("v1", path=path)
    assert rolled_back.skill_version == "v1"

    current = current_version(path=path)
    assert current is not None
    assert current.skill_version == "v1"

    all_records = history(path=path)
    assert [r.is_current for r in all_records] == [True, False]


def test_rollback_to_unknown_version_raises(tmp_path: Path) -> None:
    path = tmp_path / "registry.jsonl"
    register_version(_record("v1", is_current=True), path=path)
    with pytest.raises(RegistryError, match="unknown version"):
        rollback("v99", path=path)


def test_current_version_none_when_empty(tmp_path: Path) -> None:
    path = tmp_path / "registry.jsonl"
    assert current_version(path=path) is None
    assert history(path=path) == []
