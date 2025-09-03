from __future__ import annotations

import json
from typing import Any, Dict

from fastapi import APIRouter, Request, HTTPException

from ...core.config import settings
from ...services.state import get_state

router = APIRouter(prefix="/config", tags=["config"])


def _normalize_cfg(payload: Any) -> Dict[str, Any]:
    """
    Принимаем как { "cfg": {...} }, так и "сырой" объект {...}.
    Возвращаем словарь-конфиг.
    """
    if payload is None:
        return {}
    if isinstance(payload, dict):
        if "cfg" in payload and isinstance(payload["cfg"], dict):
            return payload["cfg"]
        return payload
    raise HTTPException(status_code=400, detail="Config must be JSON object")


@router.get("")
async def get_config():
    """
    Текущая runtime-конфигурация.
    """
    cfg = settings.runtime_cfg or {}
    return {"cfg": cfg}


@router.put("")
async def put_config(request: Request):
    """
    Обновить конфиг (idempotent). Тело: либо {"cfg":{...}}, либо просто {...}.
    """
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    new_cfg = _normalize_cfg(data)

    # Простейшая валидация (не строгая, чтобы не мешать работе UI)
    if not isinstance(new_cfg, dict):
        raise HTTPException(status_code=400, detail="Config must be object")

    # сохраняем в settings и state
    settings.runtime_cfg = new_cfg
    state = await get_state()
    state.cfg = new_cfg

    return {"ok": True, "cfg": new_cfg}


@router.post("")
async def post_config(request: Request):
    """
    Alias к PUT: принимаем POST на тот же эндпоинт для совместимости со старым фронтом.
    """
    return await put_config(request)


@router.get("/default")
async def get_default_config():
    """
    Отдать дефолтный конфиг, если есть. Если нет — возвращаем текущий как наименее удивляющий вариант.
    """
    default_cfg = getattr(settings, "default_cfg", None)
    if not isinstance(default_cfg, dict):
        default_cfg = settings.runtime_cfg or {}
    return {"cfg": default_cfg}


@router.post("/restore")
async def restore_config():
    """
    В «мягком» варианте просто возвращаем текущий runtime как подтверждение.
    Если хочешь, можно здесь перечитывать YAML/JSON с диска.
    """
    cfg = settings.runtime_cfg or {}
    # пример, если решишь считать YAML/JSON с диска:
    # settings.load_yaml()
    # cfg = settings.runtime_cfg or {}
    state = await get_state()
    state.cfg = cfg
    return {"ok": True, "cfg": cfg}
