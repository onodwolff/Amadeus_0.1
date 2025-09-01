from __future__ import annotations
import asyncio
import itertools
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple

@dataclass
class ShadowConfig:
    alpha: float = 0.85
    latency_ms: int = 120
    post_only_reject: bool = True
    simulate_market_fills: bool = True
    market_slippage_bps: float = 1.0
    market_latency_ms: int = 20
    partial_fills: bool = True

class ShadowExecutor:
    def __init__(self, **opts):
        cfg = ShadowConfig(**{
            k: opts.get(k, getattr(ShadowConfig, k))
            for k in ShadowConfig().__dict__.keys()
        })
        a = float(opts.get("maker_queue_alpha", cfg.alpha))
        cfg.alpha = max(0.0, min(1.0, float(opts.get("alpha", a))))
        self.cfg = cfg

        self._oid = itertools.count(start=1)
        self._orders: Dict[int, Dict[str, Any]] = {}
        self._by_symbol: Dict[str, set[int]] = {}
        self._best: Dict[str, Tuple[Optional[float], Optional[float]]] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _dec(x) -> Decimal:
        return Decimal(str(x))

    @staticmethod
    def _now() -> float:
        return time.time()

    def _best_of(self, symbol: str) -> Tuple[Optional[float], Optional[float]]:
        return self._best.get(symbol, (None, None))

    @staticmethod
    def _crosses(side: str, price: float, bid: Optional[float], ask: Optional[float]) -> bool:
        if bid is None or ask is None:
            return False
        return (side == "BUY" and price >= ask) or (side == "SELL" and price <= bid)

    async def on_book_update(self, symbol: str, bids, asks):
        try:
            best_bid = float(bids[0][0]) if bids else None
            best_ask = float(asks[0][0]) if asks else None
            self._best[symbol] = (best_bid, best_ask)
        except Exception:
            pass

    async def on_trade(self, symbol: str, price: float, qty: float, is_buyer_maker: bool):
        if qty <= 0:
            return
        async with self._lock:
            for oid in list(self._by_symbol.get(symbol, [])):
                o = self._orders.get(oid)
                if not o or o["status"] in {"CANCELED", "FILLED", "REJECTED", "EXPIRED"}:
                    continue
                if o["type"] not in {"LIMIT", "LIMIT_MAKER"}:
                    continue
                side = o["side"]; px = float(o["price"])
                remain = float(Decimal(str(o["origQty"])) - Decimal(str(o["executedQty"])))
                if remain <= 0:
                    o["status"] = "FILLED"; continue
                touched = (side == "BUY" and price <= px) or (side == "SELL" and price >= px)
                if not touched:
                    continue
                take_qty = qty * self.cfg.alpha
                if not self.cfg.partial_fills:
                    take_qty = remain
                fill_qty = float(min(remain, max(0.0, take_qty)))
                if fill_qty <= 0:
                    continue
                o["executedQty"] = float(Decimal(str(o["executedQty"])) + Decimal(str(fill_qty)))
                o["cummulativeQuoteQty"] = float(
                    Decimal(str(o["cummulativeQuoteQty"])) + Decimal(str(fill_qty)) * Decimal(str(price))
                )
                o["liquidity"] = "MAKER"
                o["updateTime"] = self._now()
                if abs(Decimal(str(o["executedQty"])) - Decimal(str(o["origQty"]))) <= Decimal("1e-12"):
                    o["status"] = "FILLED"
                else:
                    o["status"] = "PARTIALLY_FILLED"

    async def create_order(self, **params):
        symbol = params["symbol"]; side = params["side"].upper()
        otype = params["type"].upper()
        tif = params.get("timeInForce") or "GTC"
        qty = float(params["quantity"]); price = float(params.get("price") or 0.0)
        await asyncio.sleep(self.cfg.latency_ms / 1000.0)

        async with self._lock:
            bid, ask = self._best.get(symbol, (None, None))

            def _exec_taker(exec_px: float) -> Dict[str, Any]:
                oid = next(self._oid)
                o = {"symbol": symbol, "orderId": oid, "side": side, "type": otype,
                     "timeInForce": tif, "status": "FILLED",
                     "price": price if otype != "MARKET" else exec_px,
                     "origQty": qty, "executedQty": qty,
                     "cummulativeQuoteQty": qty * exec_px,
                     "liquidity": "TAKER", "transactTime": int(self._now() * 1000)}
                self._orders[oid] = o
                self._by_symbol.setdefault(symbol, set()).add(oid)
                return o

            if otype == "MARKET" and self.cfg.simulate_market_fills and bid and ask:
                slip = self.cfg.market_slippage_bps / 10000.0
                exec_px = (ask * (1.0 + slip)) if side == "BUY" else (bid * (1.0 - slip))
                await asyncio.sleep(self.cfg.market_latency_ms / 1000.0)
                return _exec_taker(exec_px)

            if otype == "LIMIT_MAKER" and self._crosses(side, price, bid, ask) and self.cfg.post_only_reject:
                oid = next(self._oid)
                o = {"symbol": symbol, "orderId": oid, "side": side, "type": otype,
                     "timeInForce": tif, "status": "REJECTED",
                     "price": price, "origQty": qty, "executedQty": 0.0,
                     "cummulativeQuoteQty": 0.0, "liquidity": None, "transactTime": int(self._now() * 1000)}
                self._orders[oid] = o
                self._by_symbol.setdefault(symbol, set()).add(oid)
                return o

            if otype == "LIMIT" and self.cfg.simulate_market_fills and bid and ask and self._crosses(side, price, bid, ask):
                slip = self.cfg.market_slippage_bps / 10000.0
                exec_px = (ask * (1.0 + slip)) if side == "BUY" else (bid * (1.0 - slip))
                await asyncio.sleep(self.cfg.market_latency_ms / 1000.0)
                return _exec_taker(exec_px)

            oid = next(self._oid)
            o = {"symbol": symbol, "orderId": oid, "side": side, "type": otype,
                 "timeInForce": tif, "status": "NEW",
                 "price": price, "origQty": qty, "executedQty": 0.0,
                 "cummulativeQuoteQty": 0.0, "liquidity": None, "transactTime": int(self._now() * 1000)}
            self._orders[oid] = o
            self._by_symbol.setdefault(symbol, set()).add(oid)
            return o

    async def get_order(self, *, symbol, orderId):
        await asyncio.sleep(self.cfg.latency_ms / 1000.0)
        oid = int(orderId); o = self._orders.get(oid)
        if not o:
            return {"symbol": symbol, "orderId": oid, "status": "EXPIRED",
                    "executedQty": 0.0, "cummulativeQuoteQty": 0.0,
                    "price": None, "side": None, "liquidity": None,
                    "transactTime": int(self._now() * 1000)}
        return dict(o)

    async def cancel_order(self, *, symbol, orderId):
        await asyncio.sleep(self.cfg.latency_ms / 1000.0)
        oid = int(orderId); o = self._orders.get(oid)
        if not o:
            return {"symbol": symbol, "orderId": oid, "status": "CANCELED"}
        if o["status"] in {"FILLED", "CANCELED", "REJECTED", "EXPIRED"}:
            return dict(o)
        o["status"] = "CANCELED"; o["updateTime"] = self._now()
        return dict(o)
