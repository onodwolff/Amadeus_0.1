# backend/app/main.py
from __future__ import annotations

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .core.logging import setup_logging
from .services.state import get_state

# Базовое логирование
setup_logging(to_console=True)
log = logging.getLogger("amadeus.main")

app = FastAPI(title="Amadeus Backend", version="1.0")

# ---- CORS ----
origins = [o.strip() for o in (settings.app_origins or "http://127.0.0.1:4400,http://localhost:4400").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- REST роутеры (/api/...) ----
from .api.routers import config as cfg_router
from .api.routers import bot
from .api.routers import scanner

app.include_router(cfg_router.router, prefix="/api")
app.include_router(bot.router,        prefix="/api")
app.include_router(scanner.router,    prefix="/api")

# Дополнительные роутеры: risk, history
try:
    from .api.routers import risk
    app.include_router(risk.router,   prefix="/api")
    log.info("Router /api/risk подключён")
except Exception as e:
    log.warning("Router /api/risk недоступен: %s", e)

try:
    from .api.routers import history
    app.include_router(history.router, prefix="/api")
    log.info("Router /api/history подключён")
except Exception as e:
    log.warning("Router /api/history недоступен: %s", e)

# ---- WebSocket (/ws) ----
from .api.routers import ws as ws_router
app.include_router(ws_router.router)  # путь /ws

# ---- Старт/стоп хуки ----
@app.on_event("startup")
async def on_startup():
    """
    Никакого state.load_config(): конфиг уже прочитан в core.config при импорте.
    Здесь только синхронизируем cfg и НЕ автозапускаем бота,
    если явно не указан api.autostart=true.
    """
    state = get_state()
    state.cfg = settings.runtime_cfg or {}
    log.info("Config синхронизирован: ui.chart=%s, api.paper=%s, api.shadow=%s",
             state.cfg.get("ui", {}).get("chart"),
             state.cfg.get("api", {}).get("paper"),
             state.cfg.get("api", {}).get("shadow"))

    # НЕ автозапуск по умолчанию
    autostart = bool(state.cfg.get("api", {}).get("autostart", False))
    if autostart:
        log.warning("autostart=true — запускаю бота по конфигу…")
        try:
            await state.start()
            log.info("Бот запущен (autostart).")
        except Exception as e:
            log.exception("Не удалось автозапустить бота: %s", e)

@app.on_event("shutdown")
async def on_shutdown():
    state = get_state()
    try:
        if getattr(state, "running", False):
            await state.stop()
            log.info("Бот остановлен на shutdown.")
    except Exception:
        log.exception("Ошибка остановки бота на shutdown")

# ---- Root ----
@app.get("/")
def root():
    return {"ok": True, "name": "Amadeus Backend", "routers": [
        "/api/config", "/api/bot", "/api/scanner", "/api/risk", "/api/history", "/ws"
    ]}
