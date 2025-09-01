from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .core.logging import setup_logging

from .api.routers import bot
from .api.routers import scanner
from .api.routers import config as cfg_router
from .api.routers import ws as ws_router
from .api.routers import health as health_router
from .api.routers import risk as risk_router
from .api.routers import history as history_router  # ⬅ новый

setup_logging(to_console=True)

app = FastAPI(title="Amadeus Backend", version="1.0")

origins_raw = settings.app_origins or "*"
origins = [o.strip() for o in origins_raw.split(",")] if origins_raw else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router.router)
app.include_router(bot.router)
app.include_router(scanner.router)
app.include_router(cfg_router.router)
app.include_router(ws_router.router)
app.include_router(risk_router.router)
app.include_router(history_router.router)  # ⬅ добавили

@app.get("/")
def root():
    return {"ok": True, "name": "Amadeus Backend"}
