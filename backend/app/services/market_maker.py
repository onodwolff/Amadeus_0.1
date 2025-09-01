from __future__ import annotations
import asyncio
import logging
import time
from decimal import Decimal, InvalidOperation
from binance.enums import *
from .utils import round_step, round_step_up
logger = logging.getLogger(__name__)

class MarketMaker:
    def __init__(self, cfg, client_wrapper, events_cb=None):
        self.cfg = cfg
        self.client_wrap = client_wrapper
        self.events_cb = events_cb or (lambda e: None)

        s = cfg.get('strategy', {})
        econ = cfg.get('econ', {})

        self.symbol = s.get('symbol', 'BNBUSDT')
        self.quote_asset = self._infer_quote_asset(self.symbol)
        self.base_asset = self._infer_base_asset(self.symbol)

        self.quote_size = Decimal(str(s.get('quote_size', 10.0)))
        self.target_pct = float(s.get('target_pct', 0.5))
        self.min_spread_pct = float(s.get('min_spread_pct', 0.0))
        self.cancel_timeout = float(s.get('cancel_timeout', 10.0))
        self.reorder_interval = float(s.get('reorder_interval', 1.0))
        self.depth_level = int(s.get('depth_level', 5))

        self.maker_fee_pct = float(econ.get('maker_fee_pct', s.get('maker_fee_pct', 0.1)))
        self.taker_fee_pct = float(econ.get('taker_fee_pct', s.get('taker_fee_pct', self.maker_fee_pct)))
        self.econ_min_net = float(econ.get('min_net_pct', 0.10))
        self.enforce_post_only = bool(econ.get('enforce_post_only', s.get('post_only', True)))
        self.aggressive_take = bool(s.get('aggressive_take', False))
        self.aggressive_bps = float(s.get('aggressive_bps', 0.0))
        self.allow_short = bool(s.get('allow_short', False))

        self.status_poll_interval = float(s.get('status_poll_interval', 2.0))
        self.stats_interval = float(s.get('stats_interval', 30.0))
        self.ws_timeout = float(s.get('ws_timeout', 2.0))
        self.bootstrap_on_idle = bool(s.get('bootstrap_on_idle', True))
        self.rest_bootstrap_interval = float(s.get('rest_bootstrap_interval', 3.0))
        self.plan_log_interval = float(s.get('plan_log_interval', 5.0))

        self.start_cash = Decimal(str(s.get('paper_cash', 1000)))
        self.cash = Decimal(self.start_cash)
        self.base = Decimal('0')
        self.equity = Decimal(self.start_cash)
        self.start_equity = Decimal(self.start_cash)
        self.realized_pnl = Decimal('0')
        self.inv_cost_quote = Decimal('0')

        self.step_size = None
        self.tick_size = None
        self.min_notional = None
        self.min_qty = None
        self.min_price = None

        self.state = "INIT"
        self.open_orders = {}
        self._last_bid = None
        self._last_ask = None
        self._last_mid = None

        self._ws_msg_count = 0
        self._rest_count = {"get_order": 0, "create_order": 0, "cancel_order": 0}
        self._rate_last_ts = time.time()
        self._rate_last_ws = 0
        self._computed_ws_rate = 0.0

        self.trades_total = 0
        self.trades_buy = 0
        self.trades_sell = 0
        self.trades_maker = 0
        self.trades_taker = 0

        self.orders_created_total = 0
        self.orders_canceled_total = 0
        self.orders_rejected_total = 0
        self.orders_filled_total = 0
        self.orders_expired_total = 0

    @staticmethod
    def _infer_quote_asset(symbol: str) -> str:
        return symbol[-4:] if symbol.endswith("USDT") else symbol[-3:]

    @staticmethod
    def _infer_base_asset(symbol: str) -> str:
        return symbol[:-4] if symbol.endswith("USDT") else symbol[:-3]

    async def init_symbol_info(self):
        info = await self.client_wrap.client.get_symbol_info(self.symbol)
        if info is None:
            logger.error("Symbol '%s' not found.", self.symbol)
            raise ValueError(f"Symbol {self.symbol} unavailable.")
        for f in info['filters']:
            ft = f.get('filterType')
            if ft == 'LOT_SIZE':
                self.step_size = float(f['stepSize']); self.min_qty = float(f.get('minQty', 0.0))
            elif ft == 'PRICE_FILTER':
                self.tick_size = float(f['tickSize']); self.min_price = float(f.get('minPrice', 0.0))
            elif ft in ('MIN_NOTIONAL', 'NOTIONAL'):
                self.min_notional = float(f.get('minNotional') or f.get('notional') or 0.0)
        if self.step_size is None or self.tick_size is None:
            raise RuntimeError("Required filters missing: LOT_SIZE/PRICE_FILTER.")
        await self.events_cb({"type":"symbol_info","symbol":self.symbol,"step":self.step_size,"tick":self.tick_size})

    def _diagnose_qty(self, price: float):
        if price <= 0:
            return {"qty": 0.0, "reason": "price<=0"}
        initial_qty = float(self.quote_size) / float(price)
        qty = initial_qty
        if self.min_notional:
            min_qty_by_notional = float(self.min_notional) / float(price)
            if qty < min_qty_by_notional:
                qty = min_qty_by_notional
        rounded = round_step(qty, self.step_size, precision=8)
        if self.min_qty and rounded < float(self.min_qty):
            return {"qty": 0.0, "reason": f"rounded {rounded} < MIN_QTY {self.min_qty}",
                    "initial": initial_qty, "rounded": rounded,
                    "min_qty": self.min_qty, "min_notional": self.min_notional,
                    "notional": rounded * price}
        return {"qty": rounded, "initial": initial_qty, "notional": rounded * price}

    def _compute_prices(self, bid: float, ask: float):
        mid = (float(bid) + float(ask)) / 2.0
        half = self.target_pct / 200.0
        raw_buy = mid * (1.0 - half)
        raw_sell = mid * (1.0 + half)
        buy_p = round_step(raw_buy, self.tick_size, precision=8)
        sell_p = round_step_up(raw_sell, self.tick_size, precision=8)
        if buy_p > float(bid):  buy_p = round_step(bid, self.tick_size, precision=8)
        if sell_p < float(ask): sell_p = round_step_up(ask, self.tick_size, precision=8)
        if self.aggressive_take:
            if self.aggressive_bps > 0:
                bump = 1.0 + (self.aggressive_bps / 10000.0)
                buy_p = max(buy_p, round_step_up(ask * bump, self.tick_size, precision=8))
                sell_p = min(sell_p, round_step(bid / bump, self.tick_size, precision=8))
            else:
                buy_p = max(buy_p, round_step_up(ask, self.tick_size, precision=8))
                sell_p = min(sell_p, round_step(bid, self.tick_size, precision=8))
        exp_gross = ((sell_p - buy_p) / buy_p) * 100 if buy_p > 0 else 0.0
        fee_total = (self.maker_fee_pct + self.taker_fee_pct) if self.aggressive_take else (2.0 * self.maker_fee_pct)
        exp_net = exp_gross - fee_total
        return buy_p, sell_p, mid, exp_gross, exp_net

    def _recalc_equity(self, mid: float):
        try:
            self.equity = (self.cash + self.base * Decimal(str(mid))).quantize(Decimal("0.00000001"))
        except InvalidOperation:
            self.equity = self.cash + self.base * Decimal(str(mid))

    async def _rest_bootstrap_once(self):
        try:
            t = await self.client_wrap.client.get_orderbook_ticker(symbol=self.symbol)
            best_bid = float(t['bidPrice']); best_ask = float(t['askPrice'])
            await self._on_market(best_bid, best_ask, source="REST")
        except Exception:
            pass

    async def _bootstrap_loop(self):
        first_done = False
        while True:
            if not first_done and self._ws_msg_count == 0:
                await self._rest_bootstrap_once()
                first_done = True
            elif self.bootstrap_on_idle:
                await self._rest_bootstrap_once()
            await asyncio.sleep(self.rest_bootstrap_interval)
            if self._ws_msg_count > 0 and not self.bootstrap_on_idle:
                break

    async def _stats_loop(self):
        self._computed_ws_rate = 0.0
        while True:
            now = time.time()
            dt = max(1e-6, now - self._rate_last_ts)
            dws = self._ws_msg_count - self._rate_last_ws
            self._computed_ws_rate = dws / dt
            self._rate_last_ts = now
            self._rate_last_ws = self._ws_msg_count
            try:
                await self.events_cb({"type":"stats","ws_rate":self._computed_ws_rate,
                                      "rest":self._rest_count})
            except Exception:
                pass
            await asyncio.sleep(1.0)

    async def _market_depth_loop(self):
        bm = self.client_wrap.bm
        while True:
            try:
                async with bm.depth_socket(self.symbol, depth=self.depth_level) as stream:
                    while True:
                        try:
                            msg = await asyncio.wait_for(stream.recv(), timeout=self.ws_timeout)
                            self._ws_msg_count += 1
                            bids = msg.get('bids', []); asks = msg.get('asks', [])
                            if not bids or not asks:
                                self.state = "WAIT: empty book"
                                await asyncio.sleep(self.reorder_interval); continue
                            await self.client_wrap.on_book_update(self.symbol, bids, asks)
                            best_bid = float(bids[0][0]); best_ask = float(asks[0][0])
                            await self._on_market(best_bid, best_ask, source="WS")
                            await asyncio.sleep(self.reorder_interval)
                        except asyncio.TimeoutError:
                            if self._last_mid is not None:
                                self._recalc_equity(self._last_mid)
                            await self._refresh_open_orders()
                            await asyncio.sleep(self.reorder_interval)
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(1.0)

    async def _aggtrade_loop(self):
        bm = self.client_wrap.bm
        while True:
            try:
                async with bm.aggtrade_socket(self.symbol) as stream:
                    while True:
                        try:
                            tmsg = await stream.recv()
                            price = float(tmsg.get('p', 0.0))
                            qty = float(tmsg.get('q', 0.0))
                            is_buyer_maker = bool(tmsg.get('m', False))
                            await self.client_wrap.on_trade(self.symbol, price, qty, is_buyer_maker)
                            await self._refresh_open_orders(force=True)
                        except asyncio.TimeoutError:
                            pass
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(1.0)

    async def _on_market(self, best_bid: float, best_ask: float, source: str):
        mid = (best_bid + best_ask) / 2.0
        self._last_bid, self._last_ask, self._last_mid = best_bid, best_ask, mid
        mkt_spread = ((best_ask - best_bid) / max(1e-12, best_bid)) * 100.0

        buy_p, sell_p, _, exp_gross, exp_net = self._compute_prices(best_bid, best_ask)
        await self.events_cb({"type":"market","bid":best_bid,"ask":best_ask,"mid":mid,
                              "spread_pct":mkt_spread,"buy":buy_p,"sell":sell_p,
                              "exp_gross":exp_gross,"exp_net":exp_net})
        self._recalc_equity(mid)
        await self.events_cb({"type":"bank","cash":str(self.cash),"base":str(self.base),
                              "equity":str(self.equity),"realized":str(self.realized_pnl)})
        diag = []
        if mkt_spread < self.min_spread_pct:
            diag.append(f"SPREAD {mkt_spread:.5f}% < min {self.min_spread_pct:.5f}%")
        if (exp_net) < self.econ_min_net:
            diag.append(f"ECON net≈{exp_net:.5f}% < {self.econ_min_net:.5f}%")
        await self.events_cb({"type":"diag","text":" | ".join(diag) if diag else "OK"})
        if diag:
            self.state = "WAIT"; return
        self.state = "QUOTE"
        now = time.time()
        stale_sides = [side for side, d in self.open_orders.items() if now - d['ts'] > self.cancel_timeout]
        for side in stale_sides:
            try:
                await self.client_wrap.cancel_order(symbol=self.symbol, orderId=self.open_orders[side]['orderId'])
                self._rest_count["cancel_order"] += 1
            except Exception:
                pass
            self.open_orders.pop(side, None)
        await self._refresh_open_orders()
        ordertype = ORDER_TYPE_LIMIT_MAKER if (self.enforce_post_only and not self.aggressive_take) else ORDER_TYPE_LIMIT
        if 'BUY' not in self.open_orders:
            diagq = self._diagnose_qty(buy_p); qty = diagq["qty"]
            if qty > 0:
                try:
                    order = await self.client_wrap.create_order(
                        symbol=self.symbol, side=SIDE_BUY, type=ordertype,
                        quantity=str(qty), price=str(buy_p), timeInForce=TIME_IN_FORCE_GTC
                    )
                    self._rest_count["create_order"] += 1
                    status = order.get('status', 'NEW')
                    exec_qty = float(order.get('executedQty') or 0.0)
                    cum_quote = float(order.get('cummulativeQuoteQty') or 0.0)
                    if status in ('NEW', 'PARTIALLY_FILLED'):
                        self.open_orders['BUY'] = {'orderId': order['orderId'], 'ts': now, 'status': status,
                                                   'executedQty': exec_qty, 'cummulativeQuoteQty': cum_quote,
                                                   'price': float(buy_p)}
                except Exception as e:
                    pass
        if 'SELL' not in self.open_orders:
            diagq = self._diagnose_qty(sell_p); qty = diagq["qty"]
            if not self.allow_short:
                max_sell = float(self.base)
                qty = min(qty, max_sell) if max_sell > 0 else 0.0
            if qty > 0:
                try:
                    order = await self.client_wrap.create_order(
                        symbol=self.symbol, side=SIDE_SELL, type=ordertype,
                        quantity=str(qty), price=str(sell_p), timeInForce=TIME_IN_FORCE_GTC
                    )
                    self._rest_count["create_order"] += 1
                    status = order.get('status', 'NEW')
                    exec_qty = float(order.get('executedQty') or 0.0)
                    cum_quote = float(order.get('cummulativeQuoteQty') or 0.0)
                    if status in ('NEW', 'PARTIALLY_FILLED'):
                        self.open_orders['SELL'] = {'orderId': order['orderId'], 'ts': now, 'status': status,
                                                    'executedQty': exec_qty, 'cummulativeQuoteQty': cum_quote,
                                                    'price': float(sell_p)}
                except Exception as e:
                    pass

    async def _refresh_open_orders(self, force: bool = False):
        if not self.open_orders:
            return
        to_drop = []
        for side, d in list(self.open_orders.items()):
            try:
                o = await self.client_wrap.get_order(symbol=self.symbol, orderId=d['orderId'])
                self._rest_count["get_order"] += 1
                status = o.get('status')
                from decimal import Decimal
                exec_qty = Decimal(str(o.get('executedQty') or 0))
                cum_quote = Decimal(str(o.get('cummulativeQuoteQty') or 0))
                liq = o.get('liquidity')
                prev_exec = Decimal(str(d.get('executedQty') or 0))
                prev_cum_quote = Decimal(str(d.get('cummulativeQuoteQty') or 0))
                if exec_qty != prev_exec or cum_quote != prev_cum_quote:
                    await self._apply_fill_delta(side, prev_exec, prev_cum_quote, exec_qty, cum_quote, liq)
                d['status'] = status; d['executedQty'] = float(exec_qty); d['cummulativeQuoteQty'] = float(cum_quote)
                if status not in ('NEW', 'PARTIALLY_FILLED'):
                    to_drop.append(side)
            except Exception:
                pass
        for s in to_drop:
            self.open_orders.pop(s, None)

    async def _apply_fill_delta(self, side: str, prev_exec, prev_cum_quote, exec_qty, cum_quote, liquidity):
        from decimal import Decimal
        d_exec = exec_qty - prev_exec
        d_quote = cum_quote - prev_cum_quote
        if d_exec <= 0:
            return
        avg_px = (d_quote / d_exec) if d_exec != 0 else Decimal('0')
        side_u = (side or "").upper()
        if side_u == "BUY":
            self.cash -= d_quote; self.base += d_exec; self.inv_cost_quote += d_quote; self.trades_buy += 1
        elif side_u == "SELL":
            avg_cost = (self.inv_cost_quote / self.base) if self.base > 0 else Decimal('0')
            cost_part = avg_cost * d_exec
            realized = d_quote - cost_part
            self.realized_pnl += realized
            self.cash += d_quote; self.base -= d_exec; self.inv_cost_quote -= cost_part; self.trades_sell += 1
        self.trades_total += 1
        if liquidity:
            l = (liquidity or "").strip().upper()
            if l in ("MAKER","M"): self.trades_maker += 1
            elif l in ("TAKER","T"): self.trades_taker += 1
        if self._last_mid is not None:
            self._recalc_equity(self._last_mid)
        try:
            await self.events_cb({"type":"fill","side":side_u,"qty":float(d_exec),
                                  "quote":float(d_quote),"avg":float(avg_px),"liq":liquidity})
            await self.events_cb({"type":"bank","cash":str(self.cash),"base":str(self.base),
                                  "equity":str(self.equity),"realized":str(self.realized_pnl)})
        except Exception:
            pass

    async def run(self):
        await self.init_symbol_info()
        tasks = [self._market_depth_loop(), self._aggtrade_loop(), self._stats_loop(), self._bootstrap_loop()]
        await asyncio.gather(*tasks)
