from __future__ import annotations
from fastapi import APIRouter, Depends
from ...deps import state_dep
from ...models.schemas import BotStatus

router = APIRouter(prefix="/bot", tags=["bot"])

@router.post("/start", response_model=BotStatus)
async def start_bot(state = Depends(state_dep)):
    await state.start_bot()
    return state.status()

@router.post("/stop", response_model=BotStatus)
async def stop_bot(state = Depends(state_dep)):
    await state.stop_bot()
    return state.status()

@router.get("/status", response_model=BotStatus)
async def get_status(state = Depends(state_dep)):
    return state.status()


@router.post("/cmd/{cmd}", response_model=BotStatus)
async def handle_cmd(cmd: str, save: bool = False, state = Depends(state_dep)):
    await state.handle_cmd(cmd, save=save)
    return state.status()
