from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import time

@dataclass
class GuardResult:
    allowed: bool
    reason: Optional[str] = None
    until_ts: Optional[float] = None

@dataclass
class TradeEvent:
    ts: float
    pair: str
    pnl: float          # pnl в тех же единицах, что твой учёт
    stoploss_hit: bool = False

def _now() -> float:
    return time.time()

class BaseGuard:
    def __init__(self, cfg: Dict):
        self.cfg = cfg

    def evaluate(self, history: List[TradeEvent], equity_curve: List[Tuple[float, float]]) -> GuardResult:
        return GuardResult(True)

class StoplossGuard(BaseGuard):
    def __init__(self, cfg: Dict):
        super().__init__(cfg)
        self._locked_until: float = 0.0

    def evaluate(self, history: List[TradeEvent], equity_curve: List[Tuple[float, float]]) -> GuardResult:
        now = _now()
        if now < self._locked_until:
            return GuardResult(False, reason="StoplossGuard: cooldown", until_ts=self._locked_until)

        win = int(self.cfg.get("window_minutes", 60))
        max_sl = int(self.cfg.get("max_stoploss_count", 3))
        stop_dur = int(self.cfg.get("stop_duration_minutes", 60))

        since = now - win * 60
        count = sum(1 for e in history if e.ts >= since and e.stoploss_hit)
        if count >= max_sl:
            self._locked_until = now + stop_dur * 60
            return GuardResult(False, reason=f"StoplossGuard: {count} SL in {win}m", until_ts=self._locked_until)
        return GuardResult(True)

class MaxDrawdownGuard(BaseGuard):
    def __init__(self, cfg: Dict):
        super().__init__(cfg)
        self._locked_until: float = 0.0

    def evaluate(self, history: List[TradeEvent], equity_curve: List[Tuple[float, float]]) -> GuardResult:
        now = _now()
        if now < self._locked_until:
            return GuardResult(False, reason="MaxDrawdown: cooldown", until_ts=self._locked_until)

        lookback = int(self.cfg.get("lookback_minutes", 60))
        max_dd = float(self.cfg.get("max_allowed_drawdown", 0.1))
        stop_dur = int(self.cfg.get("stop_duration_minutes", 60))

        since = now - lookback * 60
        window = [(ts, v) for (ts, v) in equity_curve if ts >= since]
        if len(window) >= 2:
            peak = window[0][1]
            max_draw = 0.0
            for _, v in window:
                if v > peak:
                    peak = v
                dd = 0.0 if peak == 0 else (peak - v) / peak
                if dd > max_draw:
                    max_draw = dd
            if max_draw >= max_dd:
                self._locked_until = now + stop_dur * 60
                return GuardResult(False, reason=f"MaxDrawdown: {round(max_draw*100,2)}%", until_ts=self._locked_until)
        return GuardResult(True)

class CooldownGuard(BaseGuard):
    def __init__(self, cfg: Dict):
        super().__init__(cfg)
        self._locked_until: float = 0.0

    def mark_trade_closed(self):
        stop_dur = int(self.cfg.get("stop_duration_minutes", 15))
        self._locked_until = _now() + stop_dur * 60

    def evaluate(self, history: List[TradeEvent], equity_curve: List[Tuple[float, float]]) -> GuardResult:
        if _now() < self._locked_until:
            return GuardResult(False, reason="Cooldown", until_ts=self._locked_until)
        return GuardResult(True)

class LowProfitPairsGuard(BaseGuard):
    def __init__(self, cfg: Dict):
        super().__init__(cfg)
        self._pair_locked_until: Dict[str, float] = {}

    def evaluate_pair(self, pair: str, history: List[TradeEvent]) -> GuardResult:
        now = _now()
        until = self._pair_locked_until.get(pair, 0.0)
        if now < until:
            return GuardResult(False, reason=f"LowProfitPairs[{pair}]: cooldown", until_ts=until)

        min_trades = int(self.cfg.get("min_trades", 5))
        min_avg = float(self.cfg.get("min_avg_pnl", 0.0))
        stop_dur = int(self.cfg.get("stop_duration_minutes", 60))

        trades = [e for e in history if e.pair == pair]
        if len(trades) >= min_trades:
            avg = sum(t.pnl for t in trades) / len(trades)
            if avg < min_avg:
                self._pair_locked_until[pair] = now + stop_dur * 60
                return GuardResult(False, reason=f"LowProfitPairs[{pair}]: avg={avg:.4f}", until_ts=self._pair_locked_until[pair])
        return GuardResult(True)
