from __future__ import annotations
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .services.state import AppState, get_state
from .core.config import settings

def state_dep() -> AppState:
    return get_state()

security = HTTPBearer(auto_error=False)

def auth_dep(credentials: HTTPAuthorizationCredentials = Depends(security)) -> None:
    token = credentials.credentials if credentials else None
    if not token or token != settings.api_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing token")
