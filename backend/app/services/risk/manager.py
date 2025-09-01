from __future__ import annotations
from typing import Dict, List, Tuple, Optional
from .guards import (
    BaseGuard, StoplossGuard, MaxDrawdownGuard, CooldownGuard, LowProfitPairsGuard,
    GuardResult, TradeEvent
)

METHODS = {
    "StoplossGuard": StoplossGuard,
    "MaxDrawdown": MaxDrawdownGuard,
    "CooldownPeriod": CooldownGuard,
    "LowProfitPairs": LowProfitPairsGuard,
}

class RiskManager:
    """
    Управляет набором протекций и решает: можно ли открывать новую позицию/ордер.
    Ожидает конфиг вида:
    {
      "features": { "risk_protections": true },
      "protections": [ { "method": "StoplossGuard", ... }, ... ]
    }
    """
    def __init__(self, cfg: Dict):
        plist = (cfg or {}).get("protections", []) or []
        self.guards: List[BaseGuard] = []
        for p in plist:
            m = p.get("method")
            cls = METHODS.get(m)
            if cls:
                self.guards.append(cls(p))
        self.history: List[TradeEvent] = []
        self.equity_curve: List[Tuple[float, float]] = []

    def can_enter(self, pair: Optional[str] = None) -> GuardResult:
        # pair-specific
        for g in self.guards:
            if isinstance(g, LowProfitPairsGuard) and pair:
                r = g.evaluate_pair(pair, self.history)
                if not r.allowed:
                    return r
        # common guards
        for g in self.guards:
            if isinstance(g, LowProfitPairsGuard):
                continue
            r = g.evaluate(self.history, self.equity_curve)
            if not r.allowed:
                return r
        return GuardResult(True)

    def on_trade_closed(self, pair: str, pnl: float, stoploss_hit: bool = False):
        from time import time as _now
        ev = TradeEvent(ts=_now(), pair=pair, pnl=pnl, stoploss_hit=stoploss_hit)
        self.history.append(ev)
        # уведомим cooldown-guard
        for g in self.guards:
            if isinstance(g, CooldownGuard):
                g.mark_trade_closed()

    def on_equity(self, equity_value: float):
        from time import time as _now
        self.equity_curve.append((_now(), equity_value))

    def dump_state(self) -> Dict:
        locks = []
        for g in self.guards:
            if hasattr(g, "_locked_until"):
                until = getattr(g, "_locked_until")
                if until and until > 0:
                    locks.append({"guard": g.__class__.__name__, "until_ts": until})
            if hasattr(g, "_pair_locked_until"):
                for pair, until in getattr(g, "_pair_locked_until").items():
                    if until and until > 0:
                        locks.append({"guard": g.__class__.__name__, "pair": pair, "until_ts": until})
        return {
            "guards": [g.__class__.__name__ for g in self.guards],
            "locks": locks,
            "history_len": len(self.history),
            "equity_points": len(self.equity_curve),
        }
