from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Dict, Tuple

import yaml
from fastapi import APIRouter, Body, HTTPException
from ...services.state import get_state

router = APIRouter(prefix="/config", tags=["config"])

DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
CFG_FILE = DATA_DIR / "runtime_config.json"
CFG_BAK  = DATA_DIR / "runtime_config.bak.json"

DEFAULT_CFG: Dict[str, Any] = {
    "features": {"market_widget_feed": True, "risk_protections": True},
    "api": {"paper": True, "shadow": True},
    "shadow": {"rest_base": "https://testnet.binance.vision", "ws_base": "wss://testnet.binance.vision/ws"},
    "ui": {"chart": "lightweight", "theme": "dark"},
    "strategy": {"symbol": "BNBUSDT", "loop_sleep": 0.2},
    "risk": {
        "max_drawdown_pct": 10, "dd_window_sec": 86400,
        "stop_duration_sec": 43200, "cooldown_sec": 1800, "min_trades_for_dd": 0
    },
    "history": {"db_path": "data/history.sqlite3", "retention_days": 365},
}

def _to_dict_maybe(s: Any) -> Tuple[Dict[str, Any], str]:
    """
    Преобразуем вход в dict:
    - если уже dict — ок;
    - если str — пробуем JSON, затем YAML; иначе 400.
    Возвращаем (dict, canonical_json).
    """
    if isinstance(s, dict):
        return s, json.dumps(s, ensure_ascii=False)
    if isinstance(s, str):
        txt = s.strip()
        if not txt:
            raise HTTPException(status_code=400, detail="Empty config")
        # JSON сначала
        try:
            obj = json.loads(txt)
            if isinstance(obj, dict):
                return obj, json.dumps(obj, ensure_ascii=False)
        except Exception:
            pass
        # затем YAML
        try:
            obj = yaml.safe_load(txt)
            if isinstance(obj, dict):
                return obj, json.dumps(obj, ensure_ascii=False)
        except Exception:
            pass
        raise HTTPException(status_code=400, detail="Config must be a JSON/YAML object")
    raise HTTPException(status_code=400, detail="Unsupported config payload")

def _save_with_backup(js: str) -> None:
    if CFG_FILE.exists():
        try:
            CFG_BAK.write_text(CFG_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception:
            pass
    CFG_FILE.write_text(js, encoding="utf-8")

def _load_from_disk() -> Dict[str, Any]:
    if not CFG_FILE.exists():
        return {}
    try:
        txt = CFG_FILE.read_text(encoding="utf-8")
        return json.loads(txt)
    except Exception:
        return {}

@router.get("")
async def get_config():
    """Всегда отдаём валидный JSON-объект."""
    st = get_state()
    cfg = st.cfg or {}
    # если в памяти пусто — пробуем диск, иначе дефолт
    if not cfg:
        disk = _load_from_disk()
        cfg = disk if isinstance(disk, dict) and disk else DEFAULT_CFG
        st.set_cfg(cfg)
    return {"cfg": cfg}

@router.put("")
async def put_config(body: Any = Body(..., media_type="application/json")):
    """
    Принимаем строку или объект.
    - Строка: парсим как JSON, потом YAML.
    - Объект: валидируем что это dict.
    Сохраняем на диск (с бэкапом), применяем в State.
    """
    # FastAPI сам валидирует JSON-тело; если пришла пустота — вернёт 422. :contentReference[oaicite:4]{index=4}
    cfg_dict, canonical_json = _to_dict_maybe(body)
    _save_with_backup(canonical_json)
    st = get_state()
    st.set_cfg(cfg_dict)
    return {"ok": True, "cfg": cfg_dict}

@router.post("/restore")
async def restore_config():
    """Откат к последнему бэкапу (если есть)."""
    if not CFG_BAK.exists():
        raise HTTPException(status_code=404, detail="No backup config")
    try:
        txt = CFG_BAK.read_text(encoding="utf-8")
        obj = json.loads(txt)
        if not isinstance(obj, dict):
            raise ValueError("backup not dict")
        CFG_FILE.write_text(txt, encoding="utf-8")
        st = get_state()
        st.set_cfg(obj)
        return {"ok": True, "cfg": obj}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Restore failed: {e}")

@router.get("/default")
async def get_default():
    """Вернуть дефолтный конфиг (для кнопки 'Сброс')."""
    return {"cfg": DEFAULT_CFG}
