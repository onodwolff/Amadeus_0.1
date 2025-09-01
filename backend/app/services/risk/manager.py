from __future__ import annotations
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Optional, Tuple, Any


@dataclass
class RiskStatus:
    enabled: bool
    allowed: bool
    reason: Optional[str]
    now: float
    dd_current_pct: float
    dd_max_window_pct: float
    window_points: int
    window_sec: int
    threshold_pct: float
    stop_until: Optional[float]
    cooldown_until: Optional[float]


class RiskManager:
    """
    Простая система протекций:
    - MaxDrawdown по equity в скользящем окне (window_sec).
    - Stop duration при превышении порога MDD.
    - Cooldown после закрытия сделки.
    """

    def __init__(self, cfg: Dict[str, Any]) -> None:
        risk = (cfg or {}).get("risk", {}) or {}

        # ---- параметры из конфига ----
        self.enabled: bool = bool((cfg.get("features") or {}).get("risk_protections", True))
        self.threshold_pct: float = float(risk.get("max_drawdown_pct", 10))  # 10% по умолчанию
        # окно наблюдения для расчета MDD (сек)
        self.window_sec: int = int(risk.get("dd_window_sec", 24 * 3600))     # сутки по умолчанию
        # длительность блокировки входов после триггера MDD
        self.stop_duration_sec: int = int(risk.get("stop_duration_sec", 12 * 3600))
        # cooldown после закрытия сделки
        self.cooldown_sec: int = int(risk.get("cooldown_sec", 30 * 60))
        # минимум сделок, после которых MDD имеет смысл применять (опционально)
        self.min_trades_for_dd: int = int(risk.get("min_trades_for_dd", 0))

        # ---- состояние ----
        self._eq: Deque[Tuple[float, float]] = deque()  # (ts_sec, equity)
        self._stop_until_ts: Optional[float] = None
        self._cooldown_until_ts: Optional[float] = None
        self._closed_trades: int = 0

        # кэшируем значения
        self._dd_current_pct: float = 0.0
        self._dd_max_window_pct: float = 0.0

    # ---------------- public API ----------------
    def on_equity(self, equity_value: float, ts: Optional[float] = None) -> None:
        """Прокидывать текущее equity (в абсолютных единицах)."""
        if not self.enabled:
            return
        now = float(ts if ts is not None else time.time())
        self._eq.append((now, float(equity_value)))
        self._trim_old(now)
        self._recalc_dd()

        # Триггер блокировки по MDD
        if self._can_trigger_mdd_lock():
            if self._dd_max_window_pct >= self.threshold_pct or self._dd_current_pct >= self.threshold_pct:
                self._stop_until_ts = now + self.stop_duration_sec

    def on_trade_closed(self, pnl: float, ts: Optional[float] = None) -> None:
        """Вызывать при закрытии сделки (для cooldown)."""
        if not self.enabled:
            return
        now = float(ts if ts is not None else time.time())
        self._closed_trades += 1
        if self.cooldown_sec > 0:
            self._cooldown_until_ts = now + self.cooldown_sec

    def can_enter(self, pair: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """Разрешено ли входить в новую позицию сейчас."""
        if not self.enabled:
            return True, None

        now = time.time()
        # активная блокировка по MDD?
        if self._stop_until_ts and now < self._stop_until_ts:
            left = int(self._stop_until_ts - now)
            return False, f"MaxDrawdown lock ({left}s left)"

        # cooldown после сделки?
        if self._cooldown_until_ts and now < self._cooldown_until_ts:
            left = int(self._cooldown_until_ts - now)
            return False, f"Cooldown active ({left}s left)"

        # если окно пустое — не блокируем
        if not self._eq:
            return True, None

        # если MDD уже превышен — можно инициировать блокировку (будет поставлена on_equity)
        if self._can_trigger_mdd_lock():
            if self._dd_current_pct >= self.threshold_pct:
                return False, f"MaxDrawdown {self._dd_current_pct:.2f}% >= {self.threshold_pct:.2f}%"

        return True, None

    def unlock(self) -> None:
        """Снять блокировку MDD и cooldown принудительно."""
        self._stop_until_ts = None
        self._cooldown_until_ts = None

    def status(self) -> RiskStatus:
        now = time.time()
        allowed, reason = self.can_enter(None)
        return RiskStatus(
            enabled=self.enabled,
            allowed=allowed,
            reason=reason,
            now=now,
            dd_current_pct=round(self._dd_current_pct, 4),
            dd_max_window_pct=round(self._dd_max_window_pct, 4),
            window_points=len(self._eq),
            window_sec=self.window_sec,
            threshold_pct=self.threshold_pct,
            stop_until=self._stop_until_ts,
            cooldown_until=self._cooldown_until_ts,
        )

    # ---------------- internals ----------------
    def _trim_old(self, now: float) -> None:
        cutoff = now - self.window_sec
        while self._eq and self._eq[0][0] < cutoff:
            self._eq.popleft()

    def _recalc_dd(self) -> None:
        if not self._eq:
            self._dd_current_pct = 0.0
            self._dd_max_window_pct = 0.0
            return

        # текущий mdd — от исторического пика до текущего значения
        peak = max(v for _, v in self._eq)
        current = self._eq[-1][1]
        self._dd_current_pct = 0.0 if peak <= 0 else 100.0 * (peak - current) / peak

        # max mdd внутри окна — бежим по точкам и считаем просадку от текущего «наилучшего пика»
        best = float('-inf')
        maxdd = 0.0
        for _, v in self._eq:
            best = max(best, v)
            if best > 0:
                dd = 100.0 * (best - v) / best
                if dd > maxdd:
                    maxdd = dd
        self._dd_max_window_pct = maxdd

    def _can_trigger_mdd_lock(self) -> bool:
        if not self.enabled:
            return False
        if self.min_trades_for_dd and (self._closed_trades < self.min_trades_for_dd):
            return False
        return True
