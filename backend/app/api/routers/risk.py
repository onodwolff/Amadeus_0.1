from __future__ import annotations
import time
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from ...services.state import get_state

router = APIRouter(prefix="/risk", tags=["risk"])
logger = logging.getLogger(__name__)


def _build_risk_manager() -> Any:
    """
    Возвращаем/создаём экземпляр RiskManager в глобальном стейте.
    Не предполагаем точную сигнатуру конструктора — пробуем безопасно.
    """
    state = get_state()
    if getattr(state, "risk_manager", None) is not None:
        return state.risk_manager

    try:
        from ...services.risk.manager import RiskManager  # твой класс
    except Exception as e:
        # Без RiskManager дальше не поедем
        raise HTTPException(status_code=500, detail=f"RiskManager import failed: {e}")

    cfg = state.cfg or {}
    risk_cfg = (cfg.get("risk") or {}) if isinstance(cfg, dict) else {}

    # Пытаемся сконструировать максимально совместимо с твоим кодом
    inst = None
    try:
        inst = RiskManager(cfg)              # как было у тебя
    except TypeError:
        try:
            inst = RiskManager(risk_cfg)     # только секция risk
        except TypeError:
            try:
                inst = RiskManager(**risk_cfg)  # распаковка полей
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"RiskManager init failed: {e}")

    state.risk_manager = inst
    return inst


def _safe_dump_state(rm: Any) -> Dict[str, Any]:
    """
    Универсальное получение статуса риска:
    1) Если есть rm.dump_state() и он возвращает dict — используем его.
    2) Иначе аккуратно собираем статус из известных полей, чтобы фронт не падал.
    """
    try:
        if hasattr(rm, "dump_state"):
            data = rm.dump_state()
            if isinstance(data, dict):
                return data
    except Exception:
        # если своя реализация что-то бросила — сваливаемся на ручную сборку
        logger.exception("Risk manager dump_state failed")

    now = time.time()
    locked_until = float(getattr(rm, "_locked_until", 0.0) or 0.0)
    cooldown_left = max(0, int(locked_until - now))

    return {
        # признак блокировки: явный флаг или активный таймер блокировки
        "locked": bool(getattr(rm, "locked", False)) or (cooldown_left > 0),
        "cooldown_left_sec": cooldown_left,
        # популярные параметры риска — берём если есть
        "max_drawdown_pct": getattr(rm, "max_drawdown_pct", None),
        "min_trades_for_dd": getattr(rm, "min_trades_for_dd", None),
        # для отладки — тип менеджера
        "manager": type(rm).__name__,
    }


@router.get("/status")
async def risk_status(rm: Any = Depends(_build_risk_manager)):
    """Возвращает текущий статус RiskManager (устойчиво к разным реализациям)."""
    return _safe_dump_state(rm)


@router.post("/unlock")
async def risk_unlock(rm: Any = Depends(_build_risk_manager)):
    """
    Сбрасываем все блокировки:
    - если у менеджера есть метод unlock_all() — используем его;
    - иначе сбрасываем таймеры в самих гуардах и в менеджере.
    """
    # 1) идеальный кейс
    if hasattr(rm, "unlock_all"):
        try:
            rm.unlock_all()
            return {"ok": True, "mode": "unlock_all()"}
        except Exception as e:
            # провалимся на ручной сброс
            logger.exception("unlock_all() failed: %s", e)

    # 2) ручной сброс
    unlocked = 0

    # Попробуем пройтись по гуардам
    guards = getattr(rm, "guards", None)
    if guards:
        for g in guards:
            try:
                if hasattr(g, "unlock"):
                    g.unlock()
                    unlocked += 1
                if hasattr(g, "_locked_until"):
                    setattr(g, "_locked_until", 0.0)
                    unlocked += 1
                if hasattr(g, "_pair_locked_until"):
                    try:
                        getattr(g, "_pair_locked_until").clear()
                        unlocked += 1
                    except Exception:
                        logger.exception("Failed to clear pair lock state")
            except Exception:
                # не даём падать — продолжаем сбрасывать всё, что можно
                continue

    # Сбросим таймеры на уровне менеджера
    if hasattr(rm, "_locked_until"):
        try:
            setattr(rm, "_locked_until", 0.0)
        except Exception:
            logger.exception("Failed to reset _locked_until on risk manager")
    if hasattr(rm, "locked"):
        try:
            setattr(rm, "locked", False)
        except Exception:
            logger.exception("Failed to reset locked flag on risk manager")

    return {"ok": True, "unlocked": unlocked}
