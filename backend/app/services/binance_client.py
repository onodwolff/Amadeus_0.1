from __future__ import annotations
import asyncio
import json
import logging
from typing import Any, Dict, Optional, Callable, List, Iterable

import httpx  # async HTTP client
import websockets  # websockets client
from websockets.legacy.client import WebSocketClientProtocol  # type hints

logger = logging.getLogger(__name__)


class OrderBlockedByRisk(RuntimeError):
    """Создание ордера заблокировано RiskManager'ом."""
    pass


# --------------------------- Simple WS manager ---------------------------

class _WSContext:
    """Простейший async context manager, совместимый с интерфейсом python-binance:
    async with bm.depth_socket('BTCUSDT') as stream: msg = await stream.recv()
    """
    def __init__(self, manager: "SimpleBinanceSocketManager", url: str):
        self._manager = manager
        self._url = url
        self._ws: Optional[WebSocketClientProtocol] = None

    async def __aenter__(self) -> "_WSContext":
        # ping_interval/timeout — умеренные дефолты
        self._ws = await websockets.connect(self._url, ping_interval=20, ping_timeout=20, close_timeout=5)
        self._manager._register(self)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        try:
            if self._ws is not None:
                await self._ws.close()
        finally:
            self._manager._unregister(self)
            self._ws = None

    async def recv(self) -> Any:
        if self._ws is None:
            raise RuntimeError("WebSocket is not connected")
        msg = await self._ws.recv()
        try:
            return json.loads(msg)
        except Exception:
            return msg

    async def aclose(self):
        if self._ws is not None:
            try:
                await self._ws.close()
            finally:
                self._manager._unregister(self)
                self._ws = None


class SimpleBinanceSocketManager:
    """
    Мини WS-менеджер с интерфейсом, схожим с python-binance BinanceSocketManager:
    .depth_socket(), .trade_socket(), .aggtrade_socket(), .kline_socket(), .symbol_ticker_socket(), .book_ticker_socket()
    и .multiplex_socket().

    Spot testnet base: wss://stream.testnet.binance.vision/ws
    Spot mainnet base: wss://stream.binance.com:9443/ws
    Ровно как в официальной документации по WebSocket Streams. :contentReference[oaicite:2]{index=2}
    """
    WEBSOCKET_DEPTH_5 = 5
    WEBSOCKET_DEPTH_10 = 10
    WEBSOCKET_DEPTH_20 = 20

    def __init__(self, paper: bool = True, user_timeout: Optional[int] = None):
        base = "wss://stream.testnet.binance.vision" if paper else "wss://stream.binance.com:9443"
        self._base = f"{base}/ws"
        self._active: set[_WSContext] = set()
        self._user_timeout = user_timeout

    def _url(self, stream: str) -> str:
        # stream должен быть в нижнем регистре (требование Binance) :contentReference[oaicite:3]{index=3}
        return f"{self._base}/{stream}"

    # регистрация активных контекстов для аккуратного закрытия при stop()
    def _register(self, ctx: _WSContext):
        self._active.add(ctx)

    def _unregister(self, ctx: _WSContext):
        self._active.discard(ctx)

    async def close(self):
        # Закрываем все открытые сокеты
        for ctx in list(self._active):
            try:
                await ctx.aclose()
            except Exception:
                logger.warning("WS context close failed", exc_info=True)
        self._active.clear()

    # --------------- Sockets (совместимые имена) ---------------
    def depth_socket(self, symbol: str, depth: Optional[int] = None, interval: Optional[Any] = None) -> _WSContext:
        """
        Diff depth: <symbol>@depth
        Partial book (5/10/20): <symbol>@depth5/10/20
        Доп. суффикс скорости 100ms (если указан): @100ms (поддерживается Binance). :contentReference[oaicite:4]{index=4}
        """
        sym = symbol.lower()
        stream = f"{sym}@depth"
        if depth in (5, 10, 20):
            stream += str(int(depth))
        # некоторые реализации прокидывают interval='100ms' — поддержим
        if str(interval).lower() in {"100", "100ms"}:
            stream += "@100ms"
        return _WSContext(self, self._url(stream))

    def trade_socket(self, symbol: str) -> _WSContext:
        return _WSContext(self, self._url(f"{symbol.lower()}@trade"))

    def aggtrade_socket(self, symbol: str) -> _WSContext:
        return _WSContext(self, self._url(f"{symbol.lower()}@aggTrade"))

    def kline_socket(self, symbol: str, interval: str = "1m") -> _WSContext:
        # stream формат: <symbol>@kline_<interval>
        return _WSContext(self, self._url(f"{symbol.lower()}@kline_{interval}"))

    def symbol_ticker_socket(self, symbol: str) -> _WSContext:
        # 24hr ticker for a symbol
        return _WSContext(self, self._url(f"{symbol.lower()}@ticker"))

    def book_ticker_socket(self, symbol: Optional[str] = None) -> _WSContext:
        # best bid/ask — одиночный символ или все ('!bookTicker')
        stream = f"{symbol.lower()}@bookTicker" if symbol else "!bookTicker"
        return _WSContext(self, self._url(stream))

    def miniticker_socket(self, update_interval_ms: Optional[int] = None) -> _WSContext:
        # общий мини-тикер по всем символам
        stream = "!miniTicker@arr"
        if update_interval_ms in (1000, 5000):
            stream = f"{stream}@{update_interval_ms}ms"
        return _WSContext(self, self._url(stream))

    def multiplex_socket(self, streams: Iterable[str]) -> _WSContext:
        # Combined streams: wss://.../stream?streams=<s1>/<s2>...
        # Оставляем как совместимость — большинство стратегий используют depth_socket напрямую.
        path = "/stream?streams=" + "/".join(s.lower() for s in streams)
        base = self._base.rsplit("/ws", 1)[0]  # получаем корень без /ws
        url = f"{base}{path}"
        return _WSContext(self, url)


# --------------------------- REST клиент ---------------------------

class BinanceRestClient:
    """
    Минимальный REST-клиент.
    /api/v3/exchangeInfo для получения торговых фильтров символа (PRICE_FILTER, LOT_SIZE, MIN_NOTIONAL и др.). :contentReference[oaicite:5]{index=5}
    """
    def __init__(self, api_key: Optional[str], api_secret: Optional[str], paper: bool = True):
        base = "https://testnet.binance.vision" if paper else "https://api.binance.com"
        self.base_url = f"{base}/api"
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=10.0)
        self.api_key = api_key
        self.api_secret = api_secret

    async def aclose(self):
        try:
            await self._client.aclose()
        except Exception:
            logger.exception("Failed to close httpx.AsyncClient")

    async def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        # /api/v3/exchangeInfo?symbol=BTCUSDT — Spot/Testnet одинаковы по схеме. :contentReference[oaicite:6]{index=6}
        r = await self._client.get("/v3/exchangeInfo", params={"symbol": symbol.upper()})
        r.raise_for_status()
        data = r.json()
        symbols: List[Dict[str, Any]] = data.get("symbols") or []
        if not symbols:
            raise ValueError(f"Symbol not found: {symbol}")

        s = symbols[0]
        filters_list: List[Dict[str, Any]] = s.get("filters", []) or []
        filters_by_type: Dict[str, Dict[str, Any]] = {}
        for f in filters_list:
            if isinstance(f, dict) and "filterType" in f:
                ft = f.get("filterType")
                if isinstance(ft, str):
                    filters_by_type[ft] = f

        def _to_float(d: Dict[str, Any], key: str, default: float = 0.0) -> float:
            try:
                return float(d.get(key))
            except Exception:
                return default

        price_f = filters_by_type.get("PRICE_FILTER", {})
        lot_f = filters_by_type.get("LOT_SIZE", {})
        min_notional_f = filters_by_type.get("MIN_NOTIONAL", {})

        tick_size = _to_float(price_f, "tickSize", 0.0)
        min_price = _to_float(price_f, "minPrice", 0.0)
        step_size = _to_float(lot_f, "stepSize", 0.0)
        min_qty = _to_float(lot_f, "minQty", 0.0)
        min_notional = _to_float(min_notional_f, "minNotional", 0.0)

        return {
            "symbol": s.get("symbol"),
            "baseAsset": s.get("baseAsset"),
            "quoteAsset": s.get("quoteAsset"),
            "tick_size": tick_size,
            "step_size": step_size,
            "min_price": min_price,
            "min_qty": min_qty,
            "min_notional": min_notional,
            "filters": filters_list,                   # как в Binance
            "filters_by_type": filters_by_type,        # удобная мапа
            "raw": s,
        }


# --------------------------- Высокоуровневая обёртка ---------------------------

class BinanceAsync:
    """
    Обёртка клиента Binance: REST (.client), WS-менеджер (.bm) и риск-перехват.
    `.bm` реализован в стиле python-binance BinanceSocketManager (async context manager). :contentReference[oaicite:7]{index=7}
    """
    def __init__(
            self,
            api_key: Optional[str],
            api_secret: Optional[str],
            paper: bool = True,
            shadow: bool = False,
            shadow_opts: Optional[Dict[str, Any]] = None,
            events_cb: Optional[Callable[[Dict[str, Any]], Any]] = None,
            state: Optional["AppState"] = None,
    ) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.paper = paper
        self.shadow = shadow
        self.shadow_opts = shadow_opts or {}
        self.events_cb = events_cb
        self.state = state

        # REST клиент
        self.client = BinanceRestClient(api_key=self.api_key, api_secret=self.api_secret, paper=self.paper)
        # WS менеджер, ожидаемый стратегией как .bm
        self.bm = SimpleBinanceSocketManager(paper=self.paper)

    async def close(self):
        # закрыть WS и REST
        try:
            await self.bm.close()
        except Exception:
            logger.exception("bm close error")
        try:
            await self.client.aclose()
        except Exception:
            logger.exception("client close error")

    # -------------------- events helper --------------------
    def _emit(self, obj: Dict[str, Any]):
        try:
            if self.events_cb:
                coro = self.events_cb(obj)
                if asyncio.iscoroutine(coro):
                    asyncio.create_task(coro)
        except Exception:
            logger.exception("events_cb failed")

    # -------------------- risk pre-check --------------------
    def _pre_order(self, symbol: Optional[str]):
        if not self.state:
            return
        allowed, reason = self.state.check_risk(symbol or None)
        if not allowed:
            logger.warning("Order blocked by risk: %s (%s)", symbol, reason)
            self._emit({"type": "diag", "text": f"ORDER BLOCKED [{symbol}]: {reason}"})
            raise OrderBlockedByRisk(reason or "risk")

    # -------------------- orders API (заглушка) --------------------
    async def create_order(
            self,
            symbol: str,
            side: str,
            type_: str,
            quantity: Optional[float] = None,
            price: Optional[float] = None,
            **kwargs: Any,
    ) -> Dict[str, Any]:
        self._pre_order(symbol)
        order = {
            "symbol": symbol,
            "side": side.upper(),
            "type": type_.upper(),
            "qty": quantity,
            "price": price,
            "status": "NEW",
        }
        self._emit({"type": "order_event", "event": "NEW", "order": order})
        return order

    # удобные врапперы — если используются
    async def create_limit_buy(self, symbol: str, quantity: float, price: float, **kwargs) -> Dict[str, Any]:
        self._pre_order(symbol)
        return await self.create_order(symbol, "BUY", "LIMIT", quantity=quantity, price=price, **kwargs)

    async def create_limit_sell(self, symbol: str, quantity: float, price: float, **kwargs) -> Dict[str, Any]:
        self._pre_order(symbol)
        return await self.create_order(symbol, "SELL", "LIMIT", quantity=quantity, price=price, **kwargs)

    async def create_market_buy(self, symbol: str, quantity: float, **kwargs) -> Dict[str, Any]:
        self._pre_order(symbol)
        return await self.create_order(symbol, "BUY", "MARKET", quantity=quantity, **kwargs)

    async def create_market_sell(self, symbol: str, quantity: float, **kwargs) -> Dict[str, Any]:
        self._pre_order(symbol)
        return await self.create_order(symbol, "SELL", "MARKET", quantity=quantity, **kwargs)

    # совместимость: вдруг где-то вызывается client_wrap.get_symbol_info(...)
    async def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        return await self.client.get_symbol_info(symbol)
