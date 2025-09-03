from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from binance import AsyncClient

from ...deps import state_dep
from ...models.schemas import ScanRequest, ScanResponse
from ...services.pair_scanner import scan_best_symbol
from ...core.config import settings

router = APIRouter(prefix="/scanner", tags=["scanner"])


@router.post("/scan", response_model=ScanResponse)
async def scan(req: ScanRequest, state = Depends(state_dep)):
    cfg = req.config or state.cfg

    client: AsyncClient
    close_client = False

    if state.binance and getattr(state.binance, "client", None):
        client = state.binance.client
    else:
        api_cfg = cfg.get("api", {}) if isinstance(cfg, dict) else {}
        paper = bool(api_cfg.get("paper", True))
        client = await AsyncClient.create(
            settings.binance_api_key,
            settings.binance_api_secret,
            testnet=paper,
        )
        close_client = True

    try:
        data = await scan_best_symbol(cfg, client)
    except RuntimeError:
        raise HTTPException(status_code=404, detail="no pairs found")
    finally:
        if close_client:
            try:
                await client.close_connection()
            except Exception:
                pass

    return ScanResponse(best=data["best"], top=data["top"])
