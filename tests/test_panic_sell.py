import asyncio

import asyncio

from backend.app.services.state import AppState
from backend.app.services.risk.manager import RiskManager


class DummyOrder:
    def __init__(self, oid):
        self.id = oid
        self.status = "NEW"


class DummyStrategy:
    def __init__(self):
        self.symbol = "BTCUSDT"
        self.orders = {"1": DummyOrder("1"), "2": DummyOrder("2")}


class DummyBinance:
    def __init__(self):
        self.cancelled = []
        self.sold = []
        self.balances = {"BTC": 1.0, "ETH": 2.0, "USDT": 5.0}

    async def cancel_order(self, symbol, orderId):
        self.cancelled.append((symbol, orderId))
        return {}

    async def create_market_sell(self, symbol, quantity, **kwargs):
        self.sold.append((symbol, quantity))
        return {}

    async def get_balances(self):
        return self.balances


async def _setup_state():
    state = AppState()
    state.strategy = DummyStrategy()
    state.binance = DummyBinance()
    state._task = asyncio.create_task(asyncio.sleep(10))
    await asyncio.sleep(0)  # let task start
    return state


def test_panic_sell_manual():
    async def run():
        state = await _setup_state()
        await state.panic_sell()
        assert set(state.binance.cancelled) == {("BTCUSDT", "1"), ("BTCUSDT", "2")}
        assert ("BTCUSDT", 1.0) in state.binance.sold
        assert ("ETHUSDT", 2.0) in state.binance.sold
        assert all(sym != "USDTUSDT" for sym, _ in state.binance.sold)
        assert not state.is_running()
    asyncio.run(run())


def test_panic_sell_triggered_by_risk():
    async def run():
        state = await _setup_state()
        # configure risk manager with max_loss_pct
        cfg = {"features": {"risk_protections": True}, "risk": {"max_loss_pct": 5}}
        state.cfg = cfg
        state.risk_manager = RiskManager(cfg)
        state.risk_manager.on_position(base_qty=1.0, price=80.0, entry_price=100.0)
        state.risk_manager.on_equity(100.0)
        allowed, reason = state.check_risk(state.strategy.symbol)
        assert not allowed and reason
        await asyncio.sleep(0.01)  # allow panic_sell task to run
        assert state.binance.sold  # panic sell executed
        assert not state.is_running()
    asyncio.run(run())
