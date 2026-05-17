from fastapi import Request, HTTPException, Depends, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
import os
from backend.core.database import get_setting

# Support both X-Hub-Password and standard Authorization: Bearer
api_key_header = APIKeyHeader(name="X-Hub-Password", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)

async def verify_hub_password(
    request: Request, 
    password_header: str = Depends(api_key_header),
    auth: HTTPAuthorizationCredentials = Depends(bearer_scheme)
):
    # Exempt OBS overlay routes
    if request.url.path.startswith("/obs/") or request.url.path.startswith("/api/overlays/public"):
        return None

    # Get password from Bearer token first, then fallback to X-Hub-Password
    password = auth.credentials if auth else password_header

    # Get expected password from DB (try both cases)
    expected_password = await get_setting("HUB_PASSWORD") or await get_setting("hub_password")
    
    # Fallback to env if not in DB yet (for initial setup)
    if not expected_password:
        expected_password = os.getenv("HUB_PASSWORD", "admin")

    if not password or password != expected_password:
        print(f"[AUTH] Denied: received '{password}', expected '{expected_password}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Hub Password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    print(f"[AUTH] Success for request to {request.url.path}")
    return password

