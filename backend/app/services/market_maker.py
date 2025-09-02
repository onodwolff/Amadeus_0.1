from __future__ import annotations
import asyncio
import time
import math
import random
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, List

logger = logging.getLogger(__name__)


@dataclass
class PaperOrder:
    id: str
    side: str           # 'BUY' | 'SELL'
    price: float
    qty: float
    ts_new: float
    expires_at: float   # отмена по таймауту
    status: str = "NEW" # NEW | FILLED | CANCELED
    filled_qty: float = 0.0


class MarketMaker:
    """
    Мини-скальпер для shadow-песочницы:
    - подписывается на bookTicker,
    - держит две LIM-лимитки по краям спреда (bid/ask),
    - переустанавливает при смещении цены,
    - отменяет по таймауту,
    - симулирует исполнение при касании лучшими ценами.

    Все события отсылает через events_cb:
      - {'type':'order_event', ...}
      - {'type':'trade', ...}
      - {'type':'diag', 'text': '...'}
      - {'type':'market', ...} (если надо ретрансляция)
    """

    def __init__(self, cfg: Dict[str, Any], client_wrapper: Any, events_cb):
        self.cfg = cfg or {}
        self.client_wrap = client_wrapper
        self.events_cb = events_cb

        strat = (self.cfg.get("strategy") or {})
        self.symbol: str = str(strat.get("symbol") or "BNBUSDT").upper()
        self.loop_sleep: float = float(strat.get("loop_sleep", 0.2))

        # Параметры стратегии
        self.quote_size: float     = float(strat.get("quote_size", 10.0))   # USDT на сделку
        self.min_spread_pct: float = float(strat.get("min_spread_pct", 0.0))
        self.cancel_timeout: float = float(strat.get("cancel_timeout", 10.0))
        self.post_only: bool       = bool(strat.get("post_only", True))
        self.reorder_interval: float = float(strat.get("reorder_interval", 1.0))

        # runtime
        self.best_bid: Optional[float] = None
        self.best_ask: Optional[float] = None
        self._last_reorder_ts: float = 0.0

        # бумажные ордера в shadow
        self.orders: Dict[str, PaperOrder] = {}
        self._id_seq = 1

        # метрики
        self.ticks_total = 0
        self.orders_total = 0
        self.orders_active = 0
        self.orders_filled = 0
        self.orders_expired = 0

        # границы точности (на глаз, чтобы без обмена exchangeInfo)
        self._qty_step = 1e-6
        self._price_step = 1e-2  # 0.01$ для USDT-пар по умолчанию
    # ----------------- публичный цикл -----------------
    async def run(self):
        self._log(f"MM start for {self.symbol} (shadow={getattr(self.client_wrap, 'shadow', False)})")
        await asyncio.gather(
            self._book_ticker_loop(),
            self._mm_loop()
        )

    # ----------------- утилиты -----------------
    def _now(self) -> float:
        return time.time()

    def _log(self, msg: str):
        # человекочитаемые логи в UI
        self._emit({"type": "diag", "text": f"MM: {msg}"})

    def _emit(self, evt: Dict[str, Any]):
        # единая точка публикации
        try:
            cb = self.events_cb
            if asyncio.iscoroutinefunction(cb):
                asyncio.create_task(cb(evt))
            else:
                # on_event в state умеет и sync dict
                asyncio.create_task(self.events_cb(evt))  # type: ignore
        except Exception:
            # бэкап: не падать, хотя бы синхронно
            try:
                self.events_cb(evt)
            except Exception:
                logger.exception("Fallback events_cb execution failed")

    # округление под шаги
    def _round_price(self, p: float) -> float:
        step = self._price_step
        return math.floor(p / step) * step

    def _round_qty(self, q: float) -> float:
        step = self._qty_step
        return math.floor(q / step) * step

    def _gen_id(self) -> str:
        self._id_seq += 1
        return f"P{self._id_seq:08d}"

    # ----------------- источники рынка -----------------
    async def _book_ticker_loop(self):
        """
        Подписка на лучшую цену. Требует, чтобы client_wrap имел .bm с book_ticker_socket.
        """
        sym = self.symbol
        # ожидать появления bm
        while not getattr(self.client_wrap, "bm", None):
            await asyncio.sleep(0.2)

        self._log(f"subscribe bookTicker {sym}")
        try:
            async with self.client_wrap.bm.book_ticker_socket(sym) as stream:
                while True:
                    msg = await stream.recv()
                    if not isinstance(msg, dict):
                        continue
                    b = msg.get("b")
                    a = msg.get("a")
                    if b is not None:
                        try:
                            self.best_bid = float(b)
                        except Exception:
                            logger.exception("Failed to parse best bid")
                    if a is not None:
                        try:
                            self.best_ask = float(a)
                        except Exception:
                            logger.exception("Failed to parse best ask")
                    self.ticks_total += 1
                    # ретранслируем в UI (не обязательно, но полезно)
                    self._emit({"type": "market", "symbol": sym, "bestBid": self.best_bid, "bestAsk": self.best_ask, "ts": msg.get("E") or int(self._now()*1000)})
        except asyncio.CancelledError:
            self._log("bookTicker cancelled")
            raise
        except Exception as e:
            self._log(f"bookTicker error: {e!s}")
            await asyncio.sleep(1.0)
            asyncio.create_task(self._book_ticker_loop())

    # ----------------- основной цикл ММ -----------------
    async def _mm_loop(self):
        while True:
            try:
                await self._step_once()
            except Exception as e:
                self._log(f"step error: {e!s}")
                await asyncio.sleep(0.3)
            await asyncio.sleep(self.loop_sleep)

    async def _step_once(self):
        # нет котировок — нечего делать
        if self.best_bid is None or self.best_ask is None:
            return

        # симулируем исполнение открытых ордеров по лучшим ценам
        self._try_fill_by_touch()

        # отменить протухшие
        self._cancel_expired()

        # переустановить ордера периодически или если сдвинулся мид
        now = self._now()
        if now - self._last_reorder_ts >= max(0.3, self.reorder_interval):
            self._reseed_quotes()
            self._last_reorder_ts = now

        # обновить метрики
        self.orders_active = sum(1 for o in self.orders.values() if o.status == "NEW")

    # ----------------- логика котирования -----------------
    def _reseed_quotes(self):
        bid = float(self.best_bid or 0.0)
        ask = float(self.best_ask or 0.0)
        if bid <= 0.0 or ask <= 0.0:
            return
        mid = 0.5 * (bid + ask)
        spread_pct = 100.0 * (ask - bid) / mid if mid > 0 else 0.0

        # если спред очень узкий и у нас post_only — просто приставимся к краям
        if spread_pct < max(0.001, self.min_spread_pct):
            px_buy = self._round_price(bid)    # лучшее bid
            px_sell = self._round_price(ask)   # лучшее ask
        else:
            # поставим чуть «увереннее» внутрь спреда
            offset = max(1, int((spread_pct/2.0) // 0.01)) * self._price_step
            px_buy = self._round_price(mid - offset)
            px_sell = self._round_price(mid + offset)

        # размер по количеству из суммы в котируемой валюте
        qty_buy = self._round_qty(self.quote_size / max(px_buy, 1e-9))
        qty_sell = self._round_qty(self.quote_size / max(px_sell, 1e-9))

        # обновим/создадим по одной лимитке с каждой стороны
        self._upsert_one(side="BUY", price=px_buy, qty=qty_buy)
        self._upsert_one(side="SELL", price=px_sell, qty=qty_sell)

    def _find_open(self, side: str) -> Optional[PaperOrder]:
        # выбираем «самый свежий» активный ордер нужной стороны
        cand = [o for o in self.orders.values() if o.status == "NEW" and o.side == side]
        if not cand:
            return None
        cand.sort(key=lambda o: o.ts_new, reverse=True)
        return cand[0]

    def _upsert_one(self, side: str, price: float, qty: float):
        if qty <= 0: return
        cur = self._find_open(side)
        if cur and abs(cur.price - price) < 1e-9:
            # уже стоит по этой же цене — не дергаем
            return

        # если есть активный — отменим
        if cur:
            self._cancel(cur, reason="reseed")

        # поставим новый
        self._place(side=side, price=price, qty=qty)

    # ----------------- бумажный брокер -----------------
    def _place(self, side: str, price: float, qty: float):
        oid = self._gen_id()
        now = self._now()
        po = PaperOrder(
            id=oid, side=side, price=float(price), qty=float(qty),
            ts_new=now, expires_at=now + float(self.cancel_timeout)
        )
        self.orders[oid] = po
        self.orders_total += 1

        self._emit({
            "type": "order_event", "evt": "NEW",
            "id": oid, "symbol": self.symbol,
            "side": side, "price": po.price, "qty": po.qty,
            "ts": int(now * 1000)
        })
        self._log(f"new {side} {po.qty} @ {po.price}")

    def _cancel(self, po: PaperOrder, reason: str = "cancel"):
        if po.status != "NEW":
            return
        po.status = "CANCELED"
        now = self._now()
        self._emit({
            "type": "order_event", "evt": "CANCELED",
            "id": po.id, "symbol": self.symbol,
            "side": po.side, "price": po.price, "qty": po.qty,
            "reason": reason, "ts": int(now * 1000)
        })
        self._log(f"cancel {po.side} {po.qty} @ {po.price} ({reason})")

    def _cancel_expired(self):
        now = self._now()
        for po in list(self.orders.values()):
            if po.status == "NEW" and now >= po.expires_at:
                self._cancel(po, reason="timeout")

    def _try_fill_by_touch(self):
        """
        Простая модель: лимит BUY исполняется, если bestAsk <= наша цена.
                             лимит SELL исполняется, если bestBid >= наша цена.
        Исполняем целиком (для простоты).
        """
        b = self.best_bid
        a = self.best_ask
        if b is None or a is None:
            return
        now = self._now()

        for po in list(self.orders.values()):
            if po.status != "NEW":
                continue
            if po.side == "BUY" and a <= po.price:
                self._fill(po, px=po.price, ts=now)
            elif po.side == "SELL" and b >= po.price:
                self._fill(po, px=po.price, ts=now)

    def _fill(self, po: PaperOrder, px: float, ts: float):
        po.status = "FILLED"
        po.filled_qty = po.qty
        self.orders_filled += 1

        # ордер-событие
        self._emit({
            "type": "order_event", "evt": "FILLED",
            "id": po.id, "symbol": self.symbol,
            "side": po.side, "price": px, "qty": po.qty,
            "ts": int(ts * 1000)
        })

        # сделка (P&L считаем нулевым — без инвентаря)
        self._emit({
            "type": "trade",
            "id": f"T{po.id}",
            "symbol": self.symbol,
            "side": po.side,
            "price": px, "qty": po.qty,
            "pnl": 0.0,
            "ts": int(ts * 1000)
        })

        self._log(f"filled {po.side} {po.qty} @ {px}")
