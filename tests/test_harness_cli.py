"""Tests for the `harness.scoring` CLI entrypoint (src/harness/cli.py).

Mocked backend only; no real network calls. Mirrors the fake-injection
pattern from tests/test_harness_loop.py.
"""

from __future__ import annotations

import json

import pytest

from fakes import ConstantBackend
from harness import cli
from schema.models import SkillScore

_RESPONSE = (
    '{"category": "failure", "failure_mode": "Bearing Failure", '
    '"confidence": 0.9, "evidence_span": "bearing noise"}'
)


def test_run_scoring_with_fake_backend() -> None:
    score = cli.run_scoring("failure_vs_suspension", ConstantBackend(_RESPONSE))

    assert isinstance(score, SkillScore)
    assert score.skill_version == "failure_vs_suspension@v1"
    assert score.n_cases == 50


def test_run_scoring_unknown_skill_raises() -> None:
    with pytest.raises(SystemExit):
        cli.run_scoring("nope", ConstantBackend(_RESPONSE))


def test_main_prints_score_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setitem(cli.BACKENDS, "deepseek", lambda: ConstantBackend(_RESPONSE))

    cli.main(["--skill", "failure_vs_suspension"])

    printed = json.loads(capsys.readouterr().out)
    score = SkillScore.model_validate(printed)
    assert score.skill_version == "failure_vs_suspension@v1"
    assert score.n_cases == 50


def test_main_unknown_backend_choice_rejected_by_argparse() -> None:
    with pytest.raises(SystemExit):
        cli.main(["--skill", "failure_vs_suspension", "--backend", "not-a-backend"])
