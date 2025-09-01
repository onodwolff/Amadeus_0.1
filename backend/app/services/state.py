from __future__ import annotations
import asyncio
import json
import logging
from typing import Any, Dict, Optional, Set
from ..core.config import settings
from ..models.schemas import BotStatus

logger = logging.getLogger(__name__)

class AppState:
    def __init__(self):
        self.cfg: Dict[str, Any] = settings.runtime_cfg
        self.binance = None
        self.mm = None
        self._task: Optional[asyncio.Task] = None
        self._ws_clients: Set[asyncio.Queue[str]] = set()
        self._events: asyncio.Queue[dict] = asyncio.Queue()

    def register_ws(self) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue()
        self._ws_clients.add(q)
        return q

    def unregister_ws(self, q: asyncio.Queue[str]):
        self._ws_clients.discard(q)

    async def publish(self, event: dict):
        await self._events.put(event)

    async def _broadcast_loop(self):
        while True:
            evt = await self._events.get()
            data = json.dumps(evt, ensure_ascii=False)
            for q in list(self._ws_clients):
                try:
                    await q.put(data)
                except Exception:
                    pass

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start_bot(self):
        if self.is_running():
            return
        from .binance_client import BinanceAsync
        from .market_maker import MarketMaker

        shadow_cfg = self.cfg.get("shadow", {}) or {}
        api = self.cfg.get("api", {}) or {}
        paper = bool(api.get("paper", True))

        self.binance = await BinanceAsync(
            None, None,
            paper=paper, shadow=bool(shadow_cfg.get("enabled", True)),
            shadow_opts=shadow_cfg, events_cb=self.publish
        ).create()

        self.mm = MarketMaker(self.cfg, self.binance, events_cb=self.publish)
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self.mm.run())
        loop.create_task(self._broadcast_loop())

    async def stop_bot(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except Exception:
                pass
            self._task = None
        try:
            if self.binance:
                await self.binance.close()
        finally:
            self.binance = None
            self.mm = None

    def status(self) -> BotStatus:
        m = {}
        if self.mm:
            m = {
                "ws_rate": getattr(self.mm, "_computed_ws_rate", 0.0),
                "trades": {
                    "total": self.mm.trades_total,
                    "buy": self.mm.trades_buy,
                    "sell": self.mm.trades_sell,
                    "maker": self.mm.trades_maker,
                    "taker": self.mm.trades_taker,
                },
                "orders": {
                    "created": self.mm.orders_created_total,
                    "canceled": self.mm.orders_canceled_total,
                    "rejected": self.mm.orders_rejected_total,
                    "filled": self.mm.orders_filled_total,
                    "expired": self.mm.orders_expired_total,
                    "active": len(self.mm.open_orders),
                },
            }
        sym = self.mm.symbol if self.mm else (self.cfg.get("strategy", {}) or {}).get("symbol")
        return BotStatus(running=self.is_running(), symbol=sym, metrics=m, cfg=self.cfg)

_state: Optional[AppState] = None

def get_state() -> AppState:
    global _state
    if _state is None:
        _state = AppState()
    return _state
