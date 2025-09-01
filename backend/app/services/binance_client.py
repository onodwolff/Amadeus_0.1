from __future__ import annotations
import asyncio
import logging
from typing import Any, Dict, Optional, Callable
from binance import AsyncClient, BinanceSocketManager
from .shadow_executor import ShadowExecutor

logger = logging.getLogger(__name__)
EventCb = Callable[[dict], "asyncio.Future[Any]"] | Callable[[dict], Any]

class BinanceAsync:
    def __init__(self, api_key: Optional[str], api_secret: Optional[str],
                 paper: bool = True, shadow: bool = True, shadow_opts: Optional[dict] = None,
                 events_cb: Optional[EventCb] = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.paper = bool(paper)
        self.shadow_enabled = bool(shadow)
        self.client: Optional[AsyncClient] = None
        self.bm: Optional[BinanceSocketManager] = None
        self.events_cb = events_cb or (lambda e: None)

        shadow_opts = shadow_opts or {}
        self.shadow = ShadowExecutor(**shadow_opts)

    async def create(self):
        self.client = await AsyncClient.create(self.api_key, self.api_secret, testnet=self.paper)
        self.bm = BinanceSocketManager(self.client)
        market = "prod" if not self.paper else "testnet"
        logger.info("Binance created: market=%s testnet=%s shadow=%s", market, self.paper, self.shadow_enabled)
        return self

    async def on_book_update(self, symbol, bids, asks):
        if self.shadow_enabled:
            await self.shadow.on_book_update(symbol, bids, asks)

    async def on_trade(self, symbol, price, qty, is_buyer_maker):
        if self.shadow_enabled:
            await self.shadow.on_trade(symbol, price, qty, is_buyer_maker)
        try:
            await self.events_cb({"type": "trade", "symbol": symbol, "price": price, "qty": qty,
                                  "side": "SELL" if is_buyer_maker else "BUY"})
        except Exception:
            pass

    async def create_order(self, **kwargs):
        if self.shadow_enabled:
            o = await self.shadow.create_order(**kwargs)
        else:
            o = await self.client.create_order(**kwargs)
        try:
            await self.events_cb({"type": "order_event", **o})
        except Exception:
            pass
        return o

    async def get_order(self, **kwargs):
        if self.shadow_enabled:
            return await self.shadow.get_order(**kwargs)
        return await self.client.get_order(**kwargs)

    async def cancel_order(self, **kwargs):
        if self.shadow_enabled:
            o = await self.shadow.cancel_order(**kwargs)
        else:
            o = await self.client.cancel_order(**kwargs)
        try:
            await self.events_cb({"type": "order_event", **o})
        except Exception:
            pass
        return o

    async def close(self):
        try:
            if self.client:
                await self.client.close_connection()
        except Exception:
            pass
