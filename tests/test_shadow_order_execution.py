import asyncio
from backend.app.services.binance_client import BinanceAsync


def test_partial_fill_emits_event():
    events = []
    client = BinanceAsync(None, None, shadow=True, events_cb=lambda e: events.append(e))
    order = asyncio.run(client.create_order("TESTUSDT", "BUY", "LIMIT", quantity=1.0, price=100.0))
    asyncio.run(client.shadow_exec.on_trade("TESTUSDT", price=100.0, qty=1.0, is_buyer_maker=False))
    updated = asyncio.run(client.get_order(symbol="TESTUSDT", orderId=order["orderId"]))
    assert updated["status"] == "PARTIALLY_FILLED"
    assert any(e.get("evt") == "PARTIALLY_FILLED" for e in events if e.get("type") == "order_event")
    asyncio.run(client.close())
