import os
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from backend.api.auth import verify_hub_password

router = APIRouter(tags=["assets"])

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static")
ASSETS_DIR = os.path.join(STATIC_DIR, "assets")

os.makedirs(ASSETS_DIR, exist_ok=True)


@router.get("", summary="List uploaded assets")
async def list_assets():
    """Return all files in the static assets directory."""
    files = []
    for f in os.listdir(ASSETS_DIR):
        if os.path.isfile(os.path.join(ASSETS_DIR, f)):
            files.append({"name": f, "url": f"/static/assets/{f}"})
    return {"assets": files}


@router.post("/upload",
             dependencies=[Depends(verify_hub_password)],
             summary="Upload an asset file")
async def upload_asset(file: UploadFile = File(...)):
    """Upload an image or other file to use in OBS overlays."""
    if not file.filename:
        raise HTTPException(400, "Invalid filename")

    filename = file.filename.replace(" ", "_")
    file_path = os.path.join(ASSETS_DIR, filename)

    try:
        with open(file_path, "wb") as f:
            f.write(await file.read())
        return {"name": filename, "url": f"/static/assets/{filename}"}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/{name}",
               dependencies=[Depends(verify_hub_password)],
               summary="Delete an asset")
async def delete_asset(name: str):
    """Remove an uploaded asset file."""
    file_path = os.path.join(ASSETS_DIR, name)
    if os.path.exists(file_path):
        os.remove(file_path)
        return {"message": "Deleted"}
    raise HTTPException(404, "Asset not found")
