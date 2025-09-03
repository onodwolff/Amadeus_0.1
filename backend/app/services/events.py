from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, is_dataclass
from typing import Any, Mapping

logger = logging.getLogger(__name__)


class EventDispatcher:
    """Dispatch incoming events to dedicated handlers."""

    def __init__(self, state: "AppState") -> None:
        self.state = state
        self._handlers = [
            self._handle_risk,
            self._handle_history,
            self._handle_market,
            self._handle_misc,
        ]

    async def dispatch(self, evt: Any) -> None:
        try:
            if not isinstance(evt, dict):
                if hasattr(evt, "dict"):
                    evt = evt.dict()
                elif is_dataclass(evt):
                    evt = asdict(evt)
                elif isinstance(evt, Mapping):
                    evt = dict(evt)
                else:
                    self.state.broadcast("diag", text=str(evt))
                    return
        except Exception:
            self.state.broadcast("diag", text=str(evt))
            return

        for handler in self._handlers:
            if await handler(evt):
                return

    # --- handlers ----------------------------------------------------------
    async def _handle_risk(self, evt: dict) -> bool:
        try:
            t_tmp = evt.get("type")
            eq_val = evt.get("equity", None)
            if t_tmp == "equity" and eq_val is None:
                eq_val = evt.get("value", None)
            if eq_val is not None:
                self.state.on_equity(float(eq_val))
        except Exception:
            logger.exception("Failed to handle equity value from event")
        return False

    async def _handle_history(self, evt: dict) -> bool:
        t = evt.get("type")
        try:
            if t == "order_event" and getattr(self.state, "history", None):
                await self.state.history.log_order_event(evt)
            elif t in {"trade", "fill"} and getattr(self.state, "history", None):
                await self.state.history.log_trade(evt)
                pnl = float(evt.get("pnl") or 0.0) if isinstance(evt.get("pnl"), (int, float, str)) else 0.0
                self.state.on_trade_closed(pair=str(evt.get("symbol") or ""), pnl=pnl)
        except Exception:
            logger.exception("history log failed")
        return False

    async def _handle_market(self, evt: dict) -> bool:
        t = evt.get("type")
        if t in {"market", "bank", "trade", "fill", "order_event", "stats", "diag", "plan", "status"}:
            self.state._broadcast_obj(evt)
            return True
        if not t and "e" in evt and "s" in evt:
            etype = str(evt.get("e"))
            s = str(evt.get("s"))
            ts = evt.get("E") or int(time.time() * 1000)
            if etype == "bookTicker" and ("b" in evt or "a" in evt):
                self.state.broadcast("market", symbol=s, bestBid=evt.get("b"), bestAsk=evt.get("a"), ts=ts)
                return True
            if etype in ("24hrTicker", "24hrMiniTicker"):
                self.state.broadcast("market", symbol=s, lastPrice=evt.get("c"), ts=ts)
                return True
            if etype in ("trade", "aggTrade"):
                self.state.broadcast("market", symbol=s, lastPrice=evt.get("p"), ts=ts)
                return True
            if etype == "depthUpdate" and (isinstance(evt.get("b"), list) or isinstance(evt.get("a"), list)):
                try:
                    b0 = evt.get("b")[0][0] if evt.get("b") else None
                except Exception:
                    b0 = None
                try:
                    a0 = evt.get("a")[0][0] if evt.get("a") else None
                except Exception:
                    a0 = None
                self.state.broadcast("market", symbol=s, bestBid=b0, bestAsk=a0, ts=ts)
                return True
        return False

    async def _handle_misc(self, evt: dict) -> bool:
        t = evt.get("type")
        if not t:
            self.state.broadcast("diag", text=json.dumps(evt, ensure_ascii=False))
            return True
        if t in {"ticker", "book", "depth"}:
            self.state.broadcast("market", **{k: v for k, v in evt.items() if k != "type"})
            return True
        if t in {"balance", "pnl", "equity"}:
            self.state.broadcast("bank", **{k: v for k, v in evt.items() if k != "type"})
            return True
        if t in {"log", "debug"}:
            self.state.broadcast("diag", text=str(evt.get("msg") or evt.get("text") or ""))
            return True
        self.state._broadcast_obj(evt)
        return True
