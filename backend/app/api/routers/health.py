from __future__ import annotations
from fastapi import APIRouter

router = APIRouter(tags=["health"])

@router.get("/health")
async def health():
    return {"status": "ok"}

@router.get("/version")
async def version():
    # Подхватывается из FastAPI(title=.., version=..)
    return {"version": "1.0"}
