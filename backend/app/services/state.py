from __future__ import annotations

import asyncio
import logging
import time
import traceback
from typing import Any, Dict, Optional

import httpx  # ⬅️ REST-fallback для маркет-потока

from ..core.config import settings
from ..models.schemas import BotStatus
from .configuration import ConfigService
from .events import EventDispatcher
from .ws import WSBroadcaster

logger = logging.getLogger(__name__)


class AppState:
    """
    Глобальное состояние приложения: конфиг, клиенты, стратегия, риск-менеджер,
    история и рассылка событий по WS.
    """

    def __init__(self) -> None:
        self.config_service = ConfigService(getattr(settings, "runtime_cfg", None))
        self.cfg: Dict[str, Any] = self.config_service.cfg

        # внешние сервисы/модули (лениво создаются при старте бота)
        self.binance = None  # type: ignore
        self.strategy = None  # type: ignore
        self.history = None  # type: ignore

        # риск
        self.risk_manager = None  # type: ignore

        # фоновые таски
        self._task: Optional[asyncio.Task] = None
        self._market_task: Optional[asyncio.Task] = None

        # сервисы
        self.ws = WSBroadcaster()
        self.events = EventDispatcher(self)

        # метрики/эквити
        self.equity: Optional[float] = None

        # флаг чтобы не дёргать panic_sell повторно
        self._panic_triggered = False

        logger.info(
            "Loaded cfg type=%s keys=%s",
            type(self.cfg).__name__,
            list(self.cfg.keys())[:8],
        )

    # --------------- Config helpers ---------------
    def set_cfg(self, new_cfg: Any) -> None:
        self.cfg = self.config_service.set_cfg(new_cfg)
        if self.risk_manager is not None:
            from .risk.manager import RiskManager

            self.risk_manager = RiskManager(self.cfg or {})
        # уведомим UI о новом статусе/символе
        try:
            self.broadcast_status()
        except Exception:
            logger.exception("Failed to broadcast status after config update")
        
    # --------------- Runtime flag toggles ---------------
    async def toggle_paper(self, save: bool = False) -> bool:
        api = self.cfg.setdefault("api", {})
        was_running = self.is_running()
        if was_running:
            await self.stop_bot()
        paper = not bool(api.get("paper", True))
        api["paper"] = paper
        self.set_cfg(self.cfg)
        settings.runtime_cfg = self.cfg
        if save:
            settings.dump_yaml()
        if was_running:
            await self.start_bot()
        self.broadcast("diag", text=f"Paper mode {'ON' if paper else 'OFF'}")
        return paper

    def toggle_aggressive_take(self, save: bool = False) -> bool:
        strat_root = self.cfg.setdefault("strategy", {})
        mm = strat_root.setdefault("market_maker", {})
        aggressive = not bool(mm.get("aggressive_take", False))
        mm["aggressive_take"] = aggressive
        self.set_cfg(self.cfg)
        settings.runtime_cfg = self.cfg
        if hasattr(self.strategy, "aggressive_take"):
            try:
                self.strategy.aggressive_take = aggressive  # type: ignore
            except Exception:
                logger.exception("Failed to set strategy.aggressive_take")
        if save:
            settings.dump_yaml()
        self.broadcast("diag", text=f"Aggressive take {'ON' if aggressive else 'OFF'}")
        return aggressive

    async def toggle_quotes(self) -> bool:
        if self.is_running():
            await self.stop_bot()
            return False
        await self.start_bot()
        return True

    async def panic_sell(self) -> None:
        """Cancel all orders and liquidate all non-USDT balances."""
        if self._panic_triggered:
            return
        self._panic_triggered = True
        self.broadcast("diag", text="PANIC SELL")

        # отменяем активные ордера
        try:
            symbol = getattr(self.strategy, "symbol", None)
            if (
                self.strategy
                and hasattr(self.strategy, "orders")
                and self.binance
                and hasattr(self.binance, "cancel_order")
            ):
                for po in list(self.strategy.orders.values()):  # type: ignore[attr-defined]
                    oid = getattr(po, "id", getattr(po, "orderId", None))
                    status = getattr(po, "status", None)
                    if oid and status == "NEW":
                        try:
                            await self.binance.cancel_order(symbol=symbol, orderId=oid)
                        except Exception:
                            logger.exception("Failed to cancel order %s", oid)
        except Exception:
            logger.exception("Failed to cancel open orders")

        # продаём все не-USDT балансы
        try:
            balances: Dict[str, float] = {}
            if self.binance:
                if hasattr(self.binance, "get_balances"):
                    balances = await self.binance.get_balances()  # type: ignore[attr-defined]
                elif hasattr(self.binance, "balances"):
                    balances = getattr(self.binance, "balances")  # type: ignore[attr-defined]
            for asset, qty in (balances or {}).items():
                try:
                    if asset.upper() == "USDT" or qty <= 0:
                        continue
                    sym = f"{asset.upper()}USDT"
                    if hasattr(self.binance, "create_market_sell"):
                        await self.binance.create_market_sell(sym, quantity=qty)  # type: ignore[attr-defined]
                except Exception:
                    logger.exception("Failed to panic sell %s", asset)
        except Exception:
            logger.exception("Failed to dump balances")

        try:
            await self.stop_bot()
        finally:
            self._panic_triggered = False

    async def handle_cmd(self, cmd: str, save: bool = False) -> None:
        c = (cmd or "").lower()
        if c == "p":
            await self.toggle_paper(save=save)
        elif c == "a":
            self.toggle_aggressive_take(save=save)
        elif c == "s":
            await self.toggle_quotes()
        elif c == "x":
            await self.panic_sell()
        else:
            self.broadcast("diag", text=f"Unknown cmd: {cmd}")

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
        return self.ws.register_ws()

    def unregister_ws(self, q: asyncio.Queue[str]) -> None:
        self.ws.unregister_ws(q)

    def ws_subscribe(self, q: asyncio.Queue) -> callable:
        """Правильная интеграция с /ws: используем ИМЕННО переданную очередь q."""
        return self.ws.ws_subscribe(q)

    def _broadcast_obj(self, obj: Any) -> None:
        self.ws._broadcast_obj(obj)

    def broadcast(self, type_: str, **payload: Any) -> None:
        self.ws.broadcast(type_, **payload)

    def broadcast_status(self) -> None:
        self.ws.broadcast_status(self.status())

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
            if (
                self.risk_manager
                and self.risk_manager.max_loss_pct > 0
                and "Loss" in reason
                and "%" in reason
                and not self._panic_triggered
            ):
                asyncio.create_task(self.panic_sell())
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
        from .market_maker_strategy import MarketMakerStrategy
        from .history import HistoryStore

        cfg = self.cfg
        api = (cfg.get("api") or {})
        strategy = (cfg.get("strategy") or {})
        strategy_name = str(strategy.get("name") or "market_maker")
        strategy_cfg = strategy.get(strategy_name, {})
        shadow_cfg = (cfg.get("shadow") or {})

        paper = bool(api.get("paper", True))
        shadow_en = bool(api.get("shadow", False))

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

        # Auto-pick trading pair using scanner if enabled
        sc_cfg = (cfg.get("scanner") or {})
        if sc_cfg.get("enabled"):
            try:
                from .pair_scanner import PairScanner

                scanner = PairScanner(cfg, self.binance.client)  # type: ignore[arg-type]
                data = await scanner.pick_best()
                best_sym = str((data.get("best") or {}).get("symbol") or "").upper()
                if best_sym:
                    strategy_root = cfg.setdefault("strategy", {})
                    strategy_cfg = strategy_root.setdefault(strategy_name, {})
                    strategy_cfg["symbol"] = best_sym
                    self.broadcast("diag", text=f"Auto-selected pair: {best_sym}")
                    logger.info("Auto-selected pair: %s", best_sym)
            except Exception as e:  # pragma: no cover - network / client errors
                self.broadcast("diag", text=f"Scanner failed: {e!s}; using config symbol")
                logger.warning("Pair scanner failed: %s", e)

        if strategy_name == "market_maker":
            self.strategy = MarketMakerStrategy(
                cfg, client_wrapper=self.binance, events_cb=self.on_event
            )
        else:
            raise ValueError(f"Unknown strategy: {strategy_name}")

        await self.strategy.start()

        if self.market_widget_feed_enabled:
            sym = str(strategy_cfg.get("symbol") or "BTCUSDT")
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
                logger.info("Bot task cancelled")
            finally:
                self._task = None

        if self._market_task:
            self._market_task.cancel()
            try:
                await self._market_task
            except asyncio.CancelledError:
                logger.info("Market task cancelled")
            finally:
                self._market_task = None

        if self.strategy is not None:
            try:
                await self.strategy.stop()
            except Exception:
                logger.exception("Strategy stop failed")
        await self._close_binance()
        self.strategy = None
        self.broadcast("diag", text="STOPPED")
        self.broadcast_status()
        logger.info("bot stopped")

    async def _run_loop(self) -> None:
        cfg = self.cfg
        strat = (cfg.get("strategy") or {})
        name = str(strat.get("name") or "market_maker")
        loop_sleep = float((strat.get(name) or {}).get("loop_sleep", 0.2))
        stats_interval = 1.0
        last_stats = time.time()

        self.broadcast("stats", ws_clients=len(self.ws.clients), ws_rate=0.0)

        try:
            while True:
                try:
                    if hasattr(self.strategy, "step"):
                        await self.strategy.step()
                    elif hasattr(self.strategy, "run"):
                        await self.strategy.run()
                    else:
                        await asyncio.sleep(loop_sleep)
                except Exception as e:
                    self.broadcast("diag", text=f"ERROR: {e!s}")
                    tb = traceback.format_exc()
                    if tb and len(tb) > 5000:
                        tb = tb[-5000:]
                    for line in tb.splitlines():
                        self.broadcast("diag", text=line)
                    logger.exception("strategy loop error: %s", e)
                    await asyncio.sleep(0.5)

                now = time.time()
                if now - last_stats >= stats_interval:
                    elapsed = now - self.ws.sent_last_ts
                    rate = (self.ws.sent_counter / elapsed) if elapsed > 0 else 0.0
                    self.ws.sent_counter = 0
                    self.ws.sent_last_ts = now
                    last_stats = now
                    self.broadcast("stats", ws_clients=len(self.ws.clients), ws_rate=round(rate, 2))

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
            logger.exception("Failed to parse shadow.rest_base")

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
        await self.events.dispatch(evt)

    def status(self) -> BotStatus:
        m: Dict[str, Any] = {"ws_clients": len(self.ws.clients)}
        if self.strategy is not None:
            for key in (
                "ticks_total",
                "orders_total",
                "orders_active",
                "orders_filled",
                "orders_expired",
                "inventory_ratio",
                "funds_in_use",
                "funds_reserve",
            ):
                val = getattr(self.strategy, key, None)
                if val is not None:
                    m[key] = val
        strat = (self.cfg.get("strategy") or {})
        name = strat.get("name")
        sym = (
            getattr(self.strategy, "symbol", None)
            if self.strategy
            else (strat.get(name, {}) or {}).get("symbol")
        )
        return BotStatus(running=self.is_running(), symbol=sym, metrics=m, cfg=self.cfg)


# --- синглтон ---
_state_lock = asyncio.Lock()
_state: Optional[AppState] = None


async def get_state() -> AppState:
    global _state
    if _state is None:
        async with _state_lock:
            if _state is None:
                _state = AppState()
    return _state

__all__ = ["AppState", "get_state"]
