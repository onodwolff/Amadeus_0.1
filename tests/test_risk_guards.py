import time
from backend.app.services.risk import guards


def test_stoploss_guard(monkeypatch):
    base = time.time()
    monkeypatch.setattr(guards, "_now", lambda: base)
    guard = guards.StoplossGuard({"window_minutes": 60, "max_stoploss_count": 1, "stop_duration_minutes": 60})
    history = [guards.TradeEvent(ts=base - 10, pair="BTC", pnl=-1, stoploss_hit=True)]
    res = guard.evaluate(history, [])
    assert not res.allowed and "StoplossGuard" in res.reason
    res2 = guard.evaluate(history, [])
    assert not res2.allowed and "cooldown" in (res2.reason or "").lower()


def test_max_drawdown_guard(monkeypatch):
    base = time.time()
    monkeypatch.setattr(guards, "_now", lambda: base)
    guard = guards.MaxDrawdownGuard({"lookback_minutes": 60, "max_allowed_drawdown": 0.1, "stop_duration_minutes": 60})
    equity_curve = [(base - 10, 100.0), (base, 80.0)]
    res = guard.evaluate([], equity_curve)
    assert not res.allowed and "MaxDrawdown" in res.reason


def test_cooldown_guard(monkeypatch):
    base = time.time()
    monkeypatch.setattr(guards, "_now", lambda: base)
    guard = guards.CooldownGuard({"stop_duration_minutes": 1})
    guard.mark_trade_closed()
    res = guard.evaluate([], [])
    assert not res.allowed
    monkeypatch.setattr(guards, "_now", lambda: base + 61)
    res2 = guard.evaluate([], [])
    assert res2.allowed


def test_low_profit_pairs_guard(monkeypatch):
    base = time.time()
    monkeypatch.setattr(guards, "_now", lambda: base)
    guard = guards.LowProfitPairsGuard({"min_trades": 2, "min_avg_pnl": 0.1, "stop_duration_minutes": 60})
    history = [
        guards.TradeEvent(ts=base - 10, pair="BTC", pnl=-1.0),
        guards.TradeEvent(ts=base - 20, pair="BTC", pnl=-0.5),
    ]
    res = guard.evaluate_pair("BTC", history)
    assert not res.allowed and "LowProfitPairs" in res.reason
    res2 = guard.evaluate_pair("BTC", history)
    assert not res2.allowed
    monkeypatch.setattr(guards, "_now", lambda: base + 61 * 60)
    positive_history = [
        guards.TradeEvent(ts=base + 61 * 60 - 10, pair="BTC", pnl=1.0),
        guards.TradeEvent(ts=base + 61 * 60 - 5, pair="BTC", pnl=1.0),
    ]
    res3 = guard.evaluate_pair("BTC", positive_history)
    assert res3.allowed
