from __future__ import annotations
from typing import Any, Dict

import yaml
from fastapi import APIRouter, Body

from ...services.state import get_state

router = APIRouter(prefix="/config", tags=["config"])

@router.get("")
async def get_config():
    state = get_state()
    # всегда возвращаем dict
    return {"cfg": state.cfg}

@router.put("")
async def put_config(body: Any = Body(...)):
    """
    Принимает dict/JSON или строку (YAML/JSON). Всегда приводит к dict.
    """
    state = get_state()
    new_cfg: Dict[str, Any]

    if isinstance(body, dict):
        new_cfg = body
    elif isinstance(body, str):
        try:
            parsed = yaml.safe_load(body) or {}
            if isinstance(parsed, dict):
                new_cfg = parsed
            else:
                new_cfg = {"_raw": body, "_parsed": parsed}
        except Exception:
            new_cfg = {"_raw": body}
    else:
        # попробуем JSON-серилизацию/десериализацию в последнюю очередь
        try:
            text = json.dumps(body, ensure_ascii=False)  # type: ignore
            parsed = yaml.safe_load(text) or {}
            new_cfg = parsed if isinstance(parsed, dict) else {"_raw": text, "_parsed": parsed}
        except Exception:
            new_cfg = {}

    state.set_cfg(new_cfg)
    return {"ok": True, "cfg_keys": list(state.cfg.keys())[:16]}
