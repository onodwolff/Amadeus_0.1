from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from ...deps import state_dep
from ...models.schemas import ScanRequest, ScanResponse
from ...services.pair_scanner import scan_best_symbol

router = APIRouter(prefix="/scanner", tags=["scanner"])

@router.post("/scan", response_model=ScanResponse)
async def scan(req: ScanRequest, state = Depends(state_dep)):
    if not state.binance or not state.binance.client:
        raise HTTPException(status_code=400, detail="Binance client not initialized. Start the bot first.")
    cfg = req.config or state.cfg
    data = await scan_best_symbol(cfg, state.binance.client)
    return ScanResponse(best=data["best"], top=data["top"])
