"""Task 4: the failure_vs_suspension skill over sample data with a mocked model.

No real API is touched: every model call is a fake backend.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fakes import ConstantBackend, ScriptedBackend
from schema.models import Category, Classification, WORecord
from skills.base import Skill
from skills.failure_vs_suspension import FailureVsSuspensionSkill

SAMPLES_PATH = Path(__file__).resolve().parents[1] / "data" / "samples" / "work_orders.jsonl"


def _load_samples() -> list[WORecord]:
    records: list[WORecord] = []
    for line in SAMPLES_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(WORecord.model_validate(json.loads(line)))
    return records


def _failure_json() -> str:
    return json.dumps(
        {
            "category": "failure",
            "failure_mode": "Bearing Failure",
            "confidence": 0.9,
            "evidence_span": "brg seized",
        }
    )


# --------------------------------------------------------------------------- #
# Protocol conformance
# --------------------------------------------------------------------------- #

def test_skill_satisfies_protocol() -> None:
    skill = FailureVsSuspensionSkill(ConstantBackend(_failure_json()))
    assert isinstance(skill, Skill)
    assert skill.version == "failure_vs_suspension@v1"
    assert skill.metric_name == "failure_precision"
    assert skill.eval_set_path.name == "failure_vs_suspension.jsonl"


# --------------------------------------------------------------------------- #
# Runs over the sample set, returns schema-valid Classifications
# --------------------------------------------------------------------------- #

def test_runs_over_samples_returning_valid_classifications() -> None:
    records = _load_samples()
    assert len(records) >= 10  # sanity: samples actually loaded
    backend = ConstantBackend(_failure_json())
    skill = FailureVsSuspensionSkill(backend)

    results = [skill.run(r) for r in records]

    assert len(results) == len(records)
    for record, result in zip(records, results, strict=True):
        assert isinstance(result, Classification)  # already validated by pydantic
        assert result.wo_id == record.wo_id
        assert result.skill_version == "failure_vs_suspension@v1"


def test_llm_backed_result_gets_provenance_and_derived_review() -> None:
    # confidence 0.9 (>= threshold) and category failure -> needs_review False.
    backend = ConstantBackend(_failure_json())
    skill = FailureVsSuspensionSkill(backend)
    result = skill.run(WORecord(wo_id="WO-X", asset_id="PUMP-1", note="brg seized, replaced"))

    assert result.category == Category.FAILURE
    assert result.failure_mode == "Bearing Failure"
    assert result.needs_review is False
    assert result.skill_version == "failure_vs_suspension@v1"  # stamped by code
    assert len(backend.calls) == 1
    # Prompt carried the record note and the closed vocabulary.
    prompt_sent = backend.calls[0][0]
    assert "brg seized, replaced" in prompt_sent
    assert "Bearing Failure" in prompt_sent


def test_low_confidence_llm_result_flagged_for_review() -> None:
    low = json.dumps(
        {
            "category": "precautionary",
            "failure_mode": None,
            "confidence": 0.4,
            "evidence_span": "PM",
        }
    )
    skill = FailureVsSuspensionSkill(ConstantBackend(low))
    result = skill.run(WORecord(wo_id="WO-Y", asset_id="PUMP-2", note="did some PM work"))
    assert result.needs_review is True  # 0.4 < 0.6 threshold


# --------------------------------------------------------------------------- #
# Empty / near-empty note path: unclassifiable, needs_review, NO LLM call
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("note", ["", "   ", "na", "-"])
def test_empty_note_shortcuts_without_llm_call(note: str) -> None:
    # ScriptedBackend([]) raises if .complete is ever called, proving no LLM hit.
    backend = ScriptedBackend([])
    skill = FailureVsSuspensionSkill(backend)
    result = skill.run(WORecord(wo_id="WO-EMPTY", asset_id="PUMP-9", note=note))

    assert result.category == Category.UNCLASSIFIABLE
    assert result.failure_mode is None
    assert result.evidence_span == ""
    assert result.needs_review is True
    assert result.confidence == 0.0
    assert backend.calls == []  # no model call happened


def test_malformed_then_valid_llm_response_retries() -> None:
    # Skill uses call_structured, so a bad-then-good model response recovers.
    backend = ScriptedBackend(["garbage not json", _failure_json()])
    skill = FailureVsSuspensionSkill(backend)
    result = skill.run(WORecord(wo_id="WO-R", asset_id="PUMP-3", note="brg seized"))
    assert result.category == Category.FAILURE
    assert len(backend.calls) == 2
