"""HTTP route for batch classification. Thin transport layer only.

Design constraints (see CLAUDE.md / docs/architecture.md):
- All business logic lives in `api.service.classify_batch`; this module only
  translates HTTP <-> that call.
- The skill (and thus its backend) is server-configured, read from
  `app.state` — never from the request body or headers, so a caller can
  never smuggle in their own model/backend choice.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from api.service import classify_batch
from schema.models import BatchClassifyRequest, BatchClassifyResponse
from skills.base import Skill


def get_skill(request: Request) -> Skill:
    skill: Skill = request.app.state.skill
    return skill


def verify_api_key(request: Request, x_api_key: str | None = Header(default=None)) -> None:
    if x_api_key != request.app.state.api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or missing API key")


router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.post("/skills/failure_vs_suspension/batch-classify", response_model=BatchClassifyResponse)
def batch_classify(
    body: BatchClassifyRequest, skill: Skill = Depends(get_skill)
) -> BatchClassifyResponse:
    """Classify a batch of work orders. See `api.service.classify_batch`."""
    return classify_batch(skill, body.records)
