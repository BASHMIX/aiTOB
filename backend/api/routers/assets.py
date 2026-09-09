import os
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.concurrency import run_in_threadpool
from backend.api.auth import require_permission
from backend.core.workspace_auth import SessionPrincipal

router = APIRouter(tags=["assets"])

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
ASSETS_DIR = os.path.join(STATIC_DIR, "assets")

os.makedirs(ASSETS_DIR, exist_ok=True)


@router.get("", summary="List uploaded assets")
async def list_assets(principal: SessionPrincipal = Depends(require_permission("workspace.read"))):
    """Return all files in the static assets directory."""
    files = []
    for f in os.listdir(ASSETS_DIR):
        if os.path.isfile(os.path.join(ASSETS_DIR, f)):
            files.append({"name": f, "url": f"/static/assets/{f}"})
    from backend.core.database import list_media_assets
    return {"assets": files, "managed_assets": await list_media_assets(principal.workspace_id)}


@router.post("/upload", summary="Upload an asset file")
async def upload_asset(
    file: UploadFile = File(...),
    principal: SessionPrincipal = Depends(require_permission("overlay.manage")),
):
    """Upload an image or other file to use in OBS overlays."""
    if not file.filename:
        raise HTTPException(400, "Invalid filename")

    from backend.core.workspace_auth import enforce_auth_rate_limit
    try:
        await enforce_auth_rate_limit(
            "asset_upload", principal.workspace_id, limit=60, window_seconds=3600,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=429, detail="Upload rate limit exceeded") from exc

    # Preserve the requested name when it is unused (legacy UI behavior), but
    # avoid overwriting a file owned by another workspace when a collision is
    # detected. Existing static URLs are untouched.
    import uuid
    safe_name = os.path.basename(file.filename).replace(" ", "_")
    filename = safe_name
    if os.path.exists(os.path.join(ASSETS_DIR, filename)):
        filename = f"{principal.workspace_id[:8]}_{uuid.uuid4().hex[:12]}_{safe_name}"
    file_path = os.path.join(ASSETS_DIR, filename)

    try:
        content = await file.read(10 * 1024 * 1024 + 1)
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(413, "Asset exceeds the 10 MB limit")
        def write_file():
            with open(file_path, "wb") as f:
                f.write(content)
        await run_in_threadpool(write_file)
        from backend.core.database import record_media_asset
        await record_media_asset(
            workspace_id=principal.workspace_id,
            asset_type="overlay_asset",
            owner_type="workspace",
            owner_id=principal.workspace_id,
            storage_url=f"/static/assets/{filename}",
            storage_key=filename,
            mime_type=file.content_type,
            byte_size=len(content),
        )
        return {"name": filename, "url": f"/static/assets/{filename}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/{name}", summary="Delete an asset")
async def delete_asset(
    name: str,
    principal: SessionPrincipal = Depends(require_permission("overlay.manage")),
):
    """Remove an uploaded asset only through its workspace-owned record.

    Legacy static files may still be referenced by existing overlays, so this
    compatibility endpoint must never delete an arbitrary path from the shared
    directory. New uploads have a managed record and use the same guarded soft
    deletion path as the explicit ``/managed`` endpoint.
    """
    from backend.core.database import list_media_assets, delete_media_asset
    matches = [asset for asset in await list_media_assets(principal.workspace_id)
               if asset.get("storage_key") == name or str(asset.get("storage_url", "")).rstrip("/").endswith("/" + name)]
    if not matches:
        raise HTTPException(404, "Asset not found or not owned by this workspace")
    try:
        deleted = await delete_media_asset(matches[0]["id"], principal.workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(404, "Asset not found")
    file_path = os.path.join(ASSETS_DIR, os.path.basename(name))
    if os.path.isfile(file_path):
        os.remove(file_path)
    return {"message": "Deleted"}


@router.delete("/managed/{asset_id}", summary="Delete an owned managed asset")
async def delete_managed_asset(asset_id: str, principal: SessionPrincipal = Depends(require_permission("tournament.manage"))):
    from backend.core.database import delete_media_asset
    try:
        deleted = await delete_media_asset(asset_id, principal.workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"deleted": True}
