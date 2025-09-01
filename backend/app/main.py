from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .core.logging import setup_logging
from .api.routers import bot, scanner, config as cfg_router, ws as ws_router

setup_logging(to_console=True)

app = FastAPI(title="Amadeus Backend", version="1.0")

origins = [o.strip() for o in (settings.app_origins or "*").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(bot.router)
app.include_router(scanner.router)
app.include_router(cfg_router.router)
app.include_router(ws_router.router)

@app.get("/")
def root():
    return {"ok": True, "name": "Amadeus Backend"}
