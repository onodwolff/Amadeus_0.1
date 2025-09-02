from __future__ import annotations
import asyncio
import json
import logging
import time
import traceback
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Optional, Set
from collections.abc import Mapping

import yaml
import httpx  # ⬅️ REST-fallback для маркет-потока

from ..core.config import settings
from ..models.schemas import BotStatus

logger = logging.getLogger(__name__)


class AppState:
    """
    Глобальное состояние приложения: конфиг, клиенты, стратегия, риск-менеджер,
    история и рассылка событий по WS.
    """

    def __init__(self) -> None:
        self.cfg: Dict[str, Any] = self._coerce_cfg(getattr(settings, "runtime_cfg", None))

        # внешние сервисы/модули (лениво создаются при старте бота)
        self.binance = None   # type: ignore
        self.mm = None        # type: ignore
        self.history = None   # type: ignore

        # риск
        self.risk_manager = None  # type: ignore

        # фоновые таски
        self._task: Optional[asyncio.Task] = None
        self._market_task: Optional[asyncio.Task] = None

        # WS клиенты — кладём ровно те очереди, которые слушает /ws
        self._clients: Set[asyncio.Queue[str]] = set()
        self._sent_counter = 0
        self._sent_last_ts = time.time()

        # метрики/эквити
        self.equity: Optional[float] = None

        logger.info("Loaded cfg type=%s keys=%s", type(self.cfg).__name__, list(self.cfg.keys())[:8])

    # --------------- Config helpers ---------------
    @staticmethod
    def _coerce_cfg(raw: Any) -> Dict[str, Any]:
        if raw is None:
            return {}
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, Mapping):
            return dict(raw)
        if isinstance(raw, str):
            try:
                data = yaml.safe_load(raw) or {}
                if isinstance(data, dict):
                    return data
                return {"_raw": raw, "_parsed": data}
            except Exception as e:
                logger.warning("cfg safe_load failed: %s", e)
                return {"_raw": raw}
        return {}

    def set_cfg(self, new_cfg: Any) -> None:
        self.cfg = self._coerce_cfg(new_cfg)
        logger.info("Config updated. keys=%s", list(self.cfg.keys())[:8])
        if self.risk_manager is not None:
            from .risk.manager import RiskManager
            self.risk_manager = RiskManager(self.cfg or {})
        # уведомим UI о новом статусе/символе
        try:
            self.broadcast_status()
        except Exception:
            pass

    # --------------- Feature toggles ---------------
    @property
    def risk_enabled(self) -> bool:
        features = (self.cfg or {}).get("features") or {}
        return bool(features.get("risk_protections", True))

    @property
    def market_widget_feed_enabled(self) -> bool:
        features = (self.cfg or {}).get("features") or {}
        return bool(features.get("market_widget_feed", True))

    # --------------- WS helpers ---------------
    def register_ws(self) -> asyncio.Queue[str]:
        """Старая механика (оставлена для совместимости)."""
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=1000)
        self._clients.add(q)
        logger.info("WS connected. total=%d", len(self._clients))
        return q

    def unregister_ws(self, q: asyncio.Queue[str]) -> None:
        self._clients.discard(q)
        logger.info("WS disconnected. total=%d", len(self._clients))

    def ws_subscribe(self, q: asyncio.Queue) -> callable:
        """
        Правильная интеграция с /ws: используем ИМЕННО переданную очередь q.
        """
        self._clients.add(q)  # type: ignore
        logger.info("WS connected (ext). total=%d", len(self._clients))

        def _unsub():
            try:
                self._clients.discard(q)  # type: ignore
                logger.info("WS disconnected (ext). total=%d", len(self._clients))
            except Exception:
                pass
        return _unsub

    def _broadcast_obj(self, obj: Any) -> None:
        try:
            if isinstance(obj, dict):
                data = json.dumps(obj, ensure_ascii=False)
            elif isinstance(obj, str):
                data = obj
            else:
                if hasattr(obj, "model_dump"):
                    data = json.dumps(obj.model_dump(), ensure_ascii=False)
                elif hasattr(obj, "dict"):
                    data = json.dumps(obj.dict(), ensure_ascii=False)
                elif is_dataclass(obj):
                    data = json.dumps(asdict(obj), ensure_ascii=False)
                elif isinstance(obj, Mapping):
                    data = json.dumps(dict(obj), ensure_ascii=False)
                else:
                    data = str(obj)
        except Exception:
            logger.exception("Failed to serialize broadcast obj, sending as text")
            data = str(obj)

        for q in list(self._clients):
            try:
                q.put_nowait(data)
                self._sent_counter += 1
            except asyncio.QueueFull:
                self._clients.discard(q)

    def broadcast(self, type_: str, **payload: Any) -> None:
        self._broadcast_obj({"type": type_, **payload})

    def broadcast_status(self) -> None:
        m = self.status()
        try:
            payload = m.model_dump()  # pydantic v2
        except Exception:
            payload = {
                "running": m.running,
                "symbol": m.symbol,
                "metrics": m.metrics,
                "cfg": m.cfg,
            }
        payload["type"] = "status"
        self._broadcast_obj(payload)

    # --------------- Risk hooks ---------------
    def _ensure_risk(self):
        if self.risk_manager is None:
            from .risk.manager import RiskManager
            self.risk_manager = RiskManager(self.cfg or {})

    def check_risk(self, symbol: Optional[str]) -> tuple[bool, Optional[str]]:
        if not self.risk_enabled:
            return True, None
        self._ensure_risk()
        allowed, reason = self.risk_manager.can_enter(pair=symbol or None)
        if not allowed and reason:
            self.broadcast("diag", text=f"ENTRY BLOCKED: {reason}")
        return allowed, reason

    def on_trade_closed(self, pair: str, pnl: float, stoploss_hit: bool = False):
        if not self.risk_enabled:
            return
        self._ensure_risk()
        self.risk_manager.on_trade_closed(pnl=pnl)

    def on_equity(self, equity_value: float):
        if not self.risk_enabled:
            return
        self._ensure_risk()
        self.risk_manager.on_equity(equity_value=float(equity_value))

    # --------------- Runtime ---------------
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def _close_binance(self) -> None:
        try:
            if self.binance and hasattr(self.binance, "close"):
                await self.binance.close()
        except Exception as e:
            logger.warning("binance close error: %s", e)

    async def start_bot(self) -> None:
        if self.is_running():
            return

        from .binance_client import BinanceAsync
        from .market_maker import MarketMaker
        from .history import HistoryStore

        cfg = self.cfg
        api = (cfg.get("api") or {})
        strategy = (cfg.get("strategy") or {})
        shadow_cfg = (cfg.get("shadow") or {})

        paper = bool(api.get("paper", True))
        shadow_en = bool(api.get("shadow", True))

        self._ensure_risk()
        self.history = HistoryStore()
        await self.history.init()

        self.binance = BinanceAsync(
            api_key=getattr(settings, "binance_api_key", None),
            api_secret=getattr(settings, "binance_api_secret", None),
            paper=paper,
            shadow=shadow_en,
            shadow_opts=shadow_cfg,
            events_cb=self.on_event,
            state=self,
        )

        self.mm = MarketMaker(cfg, client_wrapper=self.binance, events_cb=self.on_event)

        if self.market_widget_feed_enabled:
            sym = str(strategy.get("symbol") or "BTCUSDT")
            self._market_task = asyncio.create_task(self._market_widget_loop(sym))

        self._task = asyncio.create_task(self._run_loop())
        self.broadcast("diag", text="STARTED")
        self.broadcast_status()
        logger.info("bot started")

    async def stop_bot(self) -> None:
        if not self.is_running():
            return
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            finally:
                self._task = None

        if self._market_task:
            self._market_task.cancel()
            try:
                await self._market_task
            except asyncio.CancelledError:
                pass
            finally:
                self._market_task = None

        await self._close_binance()
        self.mm = None
        self.broadcast("diag", text="STOPPED")
        self.broadcast_status()
        logger.info("bot stopped")

    async def _run_loop(self) -> None:
        cfg = self.cfg
        loop_sleep = float((cfg.get("strategy") or {}).get("loop_sleep", 0.2))
        stats_interval = 1.0
        last_stats = time.time()

        self.broadcast("stats", ws_clients=len(self._clients), ws_rate=0.0)

        try:
            while True:
                try:
                    if hasattr(self.mm, "step"):
                        await self.mm.step()
                    elif hasattr(self.mm, "run"):
                        await self.mm.run()
                    else:
                        await asyncio.sleep(loop_sleep)
                except Exception as e:
                    self.broadcast("diag", text=f"ERROR: {e!s}")
                    tb = traceback.format_exc()
                    if tb and len(tb) > 5000:
                        tb = tb[-5000:]
                    for line in tb.splitlines():
                        self.broadcast("diag", text=line)
                    logger.exception("mm loop error: %s", e)
                    await asyncio.sleep(0.5)

                now = time.time()
                if now - last_stats >= stats_interval:
                    elapsed = now - self._sent_last_ts
                    rate = (self._sent_counter / elapsed) if elapsed > 0 else 0.0
                    self._sent_counter = 0
                    self._sent_last_ts = now
                    last_stats = now
                    self.broadcast("stats", ws_clients=len(self._clients), ws_rate=round(rate, 2))

                await asyncio.sleep(loop_sleep)
        finally:
            await self._close_binance()

    async def _market_widget_loop(self, symbol: str):
        """
        Устойчивый фид для виджета Маркета:
        1) Пытаемся слушать WS через binance.bm.book_ticker_socket(symbol)
        2) Если bm нет или WS падает — REST-fallback к /api/v3/ticker/bookTicker
        """
        await asyncio.sleep(0)
        sym = (symbol or "BTCUSDT").upper()

        # базовый REST-хост: из конфига shadow.rest_base или официальный
        rest_base = "https://api.binance.com"
        try:
            rest_cfg = ((self.cfg.get("shadow") or {}).get("rest_base") or "").strip()
            if rest_cfg:
                rest_base = rest_cfg
        except Exception:
            pass

        self.broadcast("diag", text=f"MarketBridge start: {sym}")

        last_diag = 0.0

        while True:
            # 1) Попытка через WS
            try:
                if self.binance and getattr(self.binance, "bm", None):
                    async with self.binance.bm.book_ticker_socket(sym) as stream:
                        if time.time() - last_diag > 15:
                            self.broadcast("diag", text=f"MarketBridge WS connected: {sym}")
                            last_diag = time.time()
                        while True:
                            msg = await stream.recv()
                            if not isinstance(msg, dict):
                                continue
                            s = str(msg.get("s") or sym)
                            b = msg.get("b")
                            a = msg.get("a")
                            p_last = msg.get("c") or msg.get("p")
                            ts = msg.get("E") or int(time.time() * 1000)
                            self.broadcast("market", symbol=s, bestBid=b, bestAsk=a, lastPrice=p_last, ts=ts)
                else:
                    # нет bm — падаем на REST-фолбэк
                    raise RuntimeError("WS bridge not ready (bm is None)")
            except asyncio.CancelledError:
                self.broadcast("diag", text="MarketBridge: cancelled")
                break
            except Exception as e:
                # 2) REST fallback
                msg = str(e)
                if time.time() - last_diag > 5:
                    self.broadcast("diag", text=f"MarketBridge WS error → REST: {msg}")
                    last_diag = time.time()

                try:
                    async with httpx.AsyncClient(timeout=3.0) as http:
                        while True:
                            # bookTicker — bid/ask
                            r = await http.get(f"{rest_base}/api/v3/ticker/bookTicker", params={"symbol": sym})
                            if r.status_code == 200:
                                j = r.json()
                                s = str(j.get("symbol") or sym)
                                b = j.get("bidPrice")
                                a = j.get("askPrice")
                                ts = int(time.time() * 1000)
                                self.broadcast("market", symbol=s, bestBid=b, bestAsk=a, ts=ts)
                            else:
                                if time.time() - last_diag > 10:
                                    self.broadcast("diag", text=f"REST bookTicker {r.status_code}: {r.text[:160]}")
                                    last_diag = time.time()
                            await asyncio.sleep(1.0)
                except asyncio.CancelledError:
                    self.broadcast("diag", text="MarketBridge (REST): cancelled")
                    break
                except Exception as e2:
                    if time.time() - last_diag > 5:
                        self.broadcast("diag", text=f"MarketBridge REST error: {e2!s}")
                        last_diag = time.time()
                    await asyncio.sleep(1.5)

    async def on_event(self, evt: Any) -> None:
        try:
            if isinstance(evt, str):
                try:
                    parsed = json.loads(evt)
                    if isinstance(parsed, dict):
                        evt = parsed
                    else:
                        self.broadcast("diag", text=str(evt))
                        return
                except Exception:
                    self.broadcast("diag", text=str(evt))
                    return
            elif not isinstance(evt, dict):
                try:
                    if hasattr(evt, "model_dump"):
                        evt = evt.model_dump()
                    elif hasattr(evt, "dict"):
                        evt = evt.dict()
                    elif is_dataclass(evt):
                        evt = asdict(evt)
                    elif isinstance(evt, Mapping):
                        evt = dict(evt)
                    else:
                        self.broadcast("diag", text=str(evt))
                        return
                except Exception:
                    self.broadcast("diag", text=str(evt))
                    return

            # equity → RiskManager
            try:
                t_tmp = evt.get("type")
                eq_val = evt.get("equity", None)
                if t_tmp == "equity" and eq_val is None:
                    eq_val = evt.get("value", None)
                if eq_val is not None:
                    self.on_equity(float(eq_val))
            except Exception:
                pass

            t = evt.get("type")

            # история
            try:
                if t == "order_event" and getattr(self, "history", None):
                    await self.history.log_order_event(evt)
                elif t in {"trade", "fill"} and getattr(self, "history", None):
                    await self.history.log_trade(evt)
                    pnl = float(evt.get("pnl") or 0.0) if isinstance(evt.get("pnl"), (int, float, str)) else 0.0
                    self.on_trade_closed(pair=str(evt.get("symbol") or ""), pnl=pnl)
            except Exception:
                logger.exception("history log failed")

            # прямая трансляция + статус
            if t in {"market", "bank", "trade", "fill", "order_event", "stats", "diag", "plan", "status"}:
                self._broadcast_obj(evt)
                return

            # «сырой» бинанс → market
            if not t and "e" in evt and "s" in evt:
                etype = str(evt.get("e"))
                s = str(evt.get("s"))
                ts = evt.get("E") or int(time.time() * 1000)
                if etype == "bookTicker" and ("b" in evt or "a" in evt):
                    self.broadcast("market", symbol=s, bestBid=evt.get("b"), bestAsk=evt.get("a"), ts=ts)
                    return
                if etype in ("24hrTicker", "24hrMiniTicker"):
                    self.broadcast("market", symbol=s, lastPrice=evt.get("c"), ts=ts)
                    return
                if etype in ("trade", "aggTrade"):
                    self.broadcast("market", symbol=s, lastPrice=evt.get("p"), ts=ts)
                    return
                if etype == "depthUpdate" and (isinstance(evt.get("b"), list) or isinstance(evt.get("a"), list)):
                    try:
                        b0 = evt.get("b")[0][0] if evt.get("b") else None
                    except Exception:
                        b0 = None
                    try:
                        a0 = evt.get("a")[0][0] if evt.get("a") else None
                    except Exception:
                        a0 = None
                    self.broadcast("market", symbol=s, bestBid=b0, bestAsk=a0, ts=ts)
                    return

            if not t:
                self.broadcast("diag", text=json.dumps(evt, ensure_ascii=False))
                return

            # прочее
            if t in {"ticker", "book", "depth"}:
                self.broadcast("market", **{k: v for k, v in evt.items() if k != "type"})
            elif t in {"balance", "pnl", "equity"}:
                self.broadcast("bank", **{k: v for k, v in evt.items() if k != "type"})
            elif t in {"log", "debug"}:
                self.broadcast("diag", text=str(evt.get("msg") or evt.get("text") or ""))
            else:
                self._broadcast_obj(evt)

        except Exception:
            logger.exception("on_event failed")
            try:
                self.broadcast("diag", text="on_event: internal exception")
            except Exception:
                pass

    def status(self) -> BotStatus:
        m: Dict[str, Any] = {"ws_clients": len(self._clients)}
        if self.mm is not None:
            for key in ("ticks_total", "orders_total", "orders_active", "orders_filled", "orders_expired"):
                val = getattr(self.mm, key, None)
                if val is not None:
                    m[key] = val
        sym = getattr(self.mm, "symbol", None) if self.mm else (self.cfg.get("strategy") or {}).get("symbol")
        return BotStatus(running=self.is_running(), symbol=sym, metrics=m, cfg=self.cfg)


# --- синглтон ---
_state: Optional[AppState] = None

def get_state() -> AppState:
    global _state
    if _state is None:
        _state = AppState()
    return _state

__all__ = ["AppState", "get_state"]