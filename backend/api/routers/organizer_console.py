from fastapi import APIRouter, Depends, HTTPException

from backend.api.auth import require_permission
from backend.core.workspace_auth import SessionPrincipal
from backend.core.organizer_console import read_organizer_console

router = APIRouter(tags=["organizer-console"])


@router.get("/organizer-console/{tournament_slug:path}")
async def api_organizer_console(tournament_slug: str, principal: SessionPrincipal = Depends(require_permission("workspace.read"))):
    """Local-database operational projection. It never polls a provider or bot."""
    try:
        return await read_organizer_console(tournament_slug, principal.workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
