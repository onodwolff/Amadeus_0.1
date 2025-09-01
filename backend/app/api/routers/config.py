from __future__ import annotations
from fastapi import APIRouter, Depends
from ...deps import state_dep
from ...models.schemas import ConfigEnvelope
from ...core.config import settings

router = APIRouter(prefix="/config", tags=["config"])

@router.get("", response_model=ConfigEnvelope)
async def get_config(state = Depends(state_dep)):
    return {"cfg": state.cfg}

@router.put("", response_model=ConfigEnvelope)
async def update_config(env: ConfigEnvelope, state = Depends(state_dep)):
    state.cfg = env.cfg
    settings.runtime_cfg = env.cfg
    settings.dump_yaml()
    return {"cfg": state.cfg}
