from __future__ import annotations
from fastapi import APIRouter, Depends
from ...services.state import get_state
from ...services.risk.manager import RiskManager

router = APIRouter(prefix="/risk", tags=["risk"])

def _risk() -> RiskManager:
    state = get_state()
    if getattr(state, "risk_manager", None) is None:
        from ...services.risk.manager import RiskManager
        state.risk_manager = RiskManager(state.cfg or {})
    return state.risk_manager  # type: ignore

@router.get("/status")
async def risk_status(rm: RiskManager = Depends(_risk)):
    return rm.dump_state()

@router.post("/unlock")
async def risk_unlock(rm: RiskManager = Depends(_risk)):
    # Сброс всех блокировок (осторожно в лайве)
    for g in rm.guards:
        if hasattr(g, "_locked_until"):
            setattr(g, "_locked_until", 0.0)
        if hasattr(g, "_pair_locked_until"):
            getattr(g, "_pair_locked_until").clear()
    return {"ok": True}
