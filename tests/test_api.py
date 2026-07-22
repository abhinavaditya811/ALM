"""Tests for the batch-classify API (src/api/service.py, src/api/app.py).

Mocked backend only; no real network calls. Mirrors the split used in
tests/test_harness_cli.py: pure orchestration tested directly, then the
HTTP surface tested through FastAPI's TestClient.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.service import classify_batch
from fakes import ConstantBackend, ScriptedBackend
from schema.models import BatchClassifyResponse, WORecord
from skills.failure_vs_suspension.skill import FailureVsSuspensionSkill

_GOOD_RESPONSE = (
    '{"category": "failure", "failure_mode": "Bearing Failure", '
    '"confidence": 0.9, "evidence_span": "bearing noise"}'
)
_MALFORMED_RESPONSE = "not valid json"

_RECORD_A = WORecord(wo_id="WO-1", asset_id="PUMP-01", note="bearing noise then seized")
_RECORD_B = WORecord(wo_id="WO-2", asset_id="PUMP-02", note="mech seal leaking product")


def test_classify_batch_isolates_a_failing_record() -> None:
    # WO-1 gets a valid response; WO-2's response never becomes schema-valid
    # even after the client's retries, so it must land in `errors`, not raise.
    backend = ScriptedBackend([_GOOD_RESPONSE, *([_MALFORMED_RESPONSE] * 3)])
    skill = FailureVsSuspensionSkill(backend=backend)

    result = classify_batch(skill, [_RECORD_A, _RECORD_B])

    assert isinstance(result, BatchClassifyResponse)
    assert result.n_requested == 2
    assert [c.wo_id for c in result.classifications] == ["WO-1"]
    assert [e.wo_id for e in result.errors] == ["WO-2"]


def _client(api_key: str = "test-key") -> TestClient:
    app = create_app(backend=ConstantBackend(_GOOD_RESPONSE), api_key=api_key)
    return TestClient(app)


def test_batch_classify_endpoint_success() -> None:
    client = _client()
    response = client.post(
        "/skills/failure_vs_suspension/batch-classify",
        json={"records": [_RECORD_A.model_dump(mode="json")]},
        headers={"x-api-key": "test-key"},
    )

    assert response.status_code == 200
    body = BatchClassifyResponse.model_validate(response.json())
    assert body.n_requested == 1
    assert body.classifications[0].wo_id == "WO-1"


def test_batch_classify_endpoint_rejects_missing_api_key() -> None:
    client = _client()
    response = client.post(
        "/skills/failure_vs_suspension/batch-classify",
        json={"records": [_RECORD_A.model_dump(mode="json")]},
    )

    assert response.status_code == 401


def test_batch_classify_endpoint_rejects_malformed_payload() -> None:
    client = _client()
    response = client.post(
        "/skills/failure_vs_suspension/batch-classify",
        json={"records": [{"wo_id": "WO-3"}]},  # missing required asset_id/note
        headers={"x-api-key": "test-key"},
    )

    assert response.status_code == 422


def test_create_app_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANALYTIXLLM_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        create_app(backend=ConstantBackend(_GOOD_RESPONSE), api_key=None)
