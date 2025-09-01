from __future__ import annotations
from typing import Any

from fastapi import APIRouter, Query
from starlette.responses import StreamingResponse

from ...services.state import get_state

router = APIRouter(prefix="/history", tags=["history"])

def _store():
    state = get_state()
    if getattr(state, "history", None) is None:
        from ...services.history import HistoryStore
        state.history = HistoryStore()
    return state.history

@router.get("/orders")
async def history_orders(limit: int = Query(200, ge=1, le=1000), offset: int = Query(0, ge=0)):
    return {"items": await _store().list_orders(limit=limit, offset=offset)}

@router.get("/trades")
async def history_trades(limit: int = Query(200, ge=1, le=1000), offset: int = Query(0, ge=0)):
    return {"items": await _store().list_trades(limit=limit, offset=offset)}

@router.get("/stats")
async def history_stats():
    return await _store().stats()

@router.post("/clear")
async def history_clear(kind: str = Query("all", pattern="^(orders|trades|all)$")):
    return await _store().clear(kind)

@router.get("/export.csv")
async def history_export(kind: str = Query("orders", pattern="^(orders|trades)$")):
    gen = _store().export_csv_iter(kind)
    return StreamingResponse(gen, media_type="text/csv", headers={
        "Content-Disposition": f'attachment; filename="{kind}.csv"'
    })
