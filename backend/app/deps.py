from __future__ import annotations
import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .services.state import AppState, get_state
from .core.config import settings


async def state_dep() -> AppState:
    return await get_state()

security = HTTPBearer(auto_error=False)

def auth_dep(credentials: HTTPAuthorizationCredentials = Depends(security)) -> None:
    token = credentials.credentials if credentials else None
    if not token or not secrets.compare_digest(token, settings.api_token or ""):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing token")
