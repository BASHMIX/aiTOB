"""Small organizer review API; intentionally no AI route imports this module."""
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.auth import require_permission
from backend.core.workspace_auth import SessionPrincipal
from backend.api.schemas import CreateActionProposalRequest, RejectActionProposalRequest
from backend.core.action_proposals import (
    ProposalError, approve_action_proposal, create_action_proposal,
    list_action_proposals, reject_action_proposal,
)

router = APIRouter(tags=["action-proposals"])


def _error(exc: ProposalError) -> HTTPException:
    text = str(exc)
    return HTTPException(status_code=404 if text == "Proposal not found" else 400, detail=text)


@router.get("/action-proposals")
async def api_list_action_proposals(tournament_slug: str = Query(min_length=1), principal: SessionPrincipal = Depends(require_permission("workspace.read"))):
    return {"proposals": await list_action_proposals(tournament_slug, principal.workspace_id)}


@router.post("/action-proposals", status_code=201)
async def api_create_action_proposal(body: CreateActionProposalRequest, principal: SessionPrincipal = Depends(require_permission("proposal.review"))):
    try:
        proposal = await create_action_proposal(
            tournament_slug=body.tournament_slug, action_type=body.action_type,
            match_id=body.match_id, payload=body.payload, reason=body.reason,
            expires_in_seconds=body.expires_in_seconds,
            actor=principal.user_id, workspace_id=principal.workspace_id,
        )
    except ProposalError as exc:
        raise _error(exc) from exc
    return {"proposal": proposal}


@router.post("/action-proposals/{proposal_id}/approve")
async def api_approve_action_proposal(proposal_id: str, principal: SessionPrincipal = Depends(require_permission("proposal.review"))):
    try:
        proposal = await approve_action_proposal(proposal_id, actor=principal.user_id, workspace_id=principal.workspace_id)
    except ProposalError as exc:
        raise _error(exc) from exc
    return {"proposal": proposal}


@router.post("/action-proposals/{proposal_id}/reject")
async def api_reject_action_proposal(proposal_id: str, body: RejectActionProposalRequest, principal: SessionPrincipal = Depends(require_permission("proposal.review"))):
    try:
        proposal = await reject_action_proposal(proposal_id, reason=body.reason, actor=principal.user_id, workspace_id=principal.workspace_id)
    except ProposalError as exc:
        raise _error(exc) from exc
    return {"proposal": proposal}
