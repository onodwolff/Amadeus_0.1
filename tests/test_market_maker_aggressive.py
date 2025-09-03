import asyncio
import pytest
from backend.app.services.market_maker_strategy import MarketMakerStrategy


class DummyClient:
    pass


def test_aggressive_take_places_taker_orders():
    events = []
    cfg = {
        "strategy": {
            "name": "market_maker",
            "market_maker": {
                "symbol": "TESTUSDT",
                "quote_size": 10.0,
                "min_spread_pct": 1.0,
                "reorder_interval": 0.0,
                "aggressive_take": True,
                "aggressive_bps": 1000.0,
            },
        }
    }
    mm = MarketMakerStrategy(cfg, DummyClient(), lambda evt: events.append(evt))
    mm.best_bid = 100.0
    mm.best_ask = 100.05
    asyncio.run(mm._step_once())
    buys = [o for o in mm.orders.values() if o.side == "BUY" and o.status == "NEW"]
    sells = [o for o in mm.orders.values() if o.side == "SELL" and o.status == "NEW"]
    assert buys and sells
    assert buys[0].price == pytest.approx(mm.best_ask)
    assert sells[0].price == pytest.approx(mm.best_bid)
    taker_quote = mm.quote_size * mm.aggressive_bps / 10000.0
    assert buys[0].qty == pytest.approx(mm._round_qty(taker_quote / mm.best_ask))
    assert sells[0].qty == pytest.approx(mm._round_qty(taker_quote / mm.best_bid))
    asyncio.run(mm._step_once())
    assert all(o.status == "FILLED" for o in buys + sells)


def test_aggressive_take_runtime_toggle():
    events = []
    cfg = {
        "strategy": {
            "name": "market_maker",
            "market_maker": {
                "symbol": "TESTUSDT",
                "quote_size": 10.0,
                "min_spread_pct": 1.0,
                "reorder_interval": 0.0,
                "aggressive_take": True,
                "aggressive_bps": 1000.0,
            },
        }
    }
    mm = MarketMakerStrategy(cfg, DummyClient(), lambda evt: events.append(evt))
    mm.best_bid = 100.0
    mm.best_ask = 100.05
    asyncio.run(mm._step_once())
    assert any(o.side == "BUY" and o.price == pytest.approx(mm.best_ask) and o.status == "NEW" for o in mm.orders.values())
    mm.cfg["strategy"]["market_maker"]["aggressive_take"] = False
    mm._last_reorder_ts = 0.0
    asyncio.run(mm._step_once())
    new_orders = [o for o in mm.orders.values() if o.status == "NEW"]
    assert any(o.side == "BUY" and o.price == pytest.approx(mm.best_bid) for o in new_orders)
    assert any(o.side == "SELL" and o.price == pytest.approx(mm.best_ask) for o in new_orders)
    assert not any(o.side == "BUY" and o.price == pytest.approx(mm.best_ask) for o in new_orders)
    assert not any(o.side == "SELL" and o.price == pytest.approx(mm.best_bid) for o in new_orders)
