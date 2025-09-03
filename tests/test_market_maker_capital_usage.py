import asyncio
import pytest
from backend.app.services.market_maker_strategy import MarketMakerStrategy


class DummyClient:
    pass


def test_capital_usage_limits_order_size():
    events = []
    cfg = {
        "strategy": {
            "name": "market_maker",
            "market_maker": {
                "symbol": "TESTUSDT",
                "quote_size": 10.0,
                "capital_usage": 0.5,
                "reorder_interval": 0.0,
            },
        }
    }
    mm = MarketMakerStrategy(cfg, DummyClient(), lambda evt: events.append(evt))
    mm.cash = 10.0
    mm.position = 1.0
    mm.best_bid = 10.0
    mm.best_ask = 10.2
    asyncio.run(mm._step_once())
    buy = next(o for o in mm.orders.values() if o.side == "BUY")
    sell = next(o for o in mm.orders.values() if o.side == "SELL")
    assert buy.qty * buy.price <= mm.cash * mm.capital_usage + 1e-9
    assert sell.qty <= mm.position * mm.capital_usage + 1e-9
    total_funds = 1.0 * 10.1 + 10.0
    used = buy.qty * buy.price + sell.qty * sell.price
    assert mm.funds_in_use == pytest.approx(used)
    assert mm.funds_reserve == pytest.approx(total_funds - used)
