from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class ScanRequest(BaseModel):
    config: Optional[Dict[str, Any]] = None

class PairScore(BaseModel):
    symbol: str
    bid: float
    ask: float
    spread_bps: float
    vol_usdt_24h: float
    vol_bps_1m: float
    score: float

class ScanResponse(BaseModel):
    best: PairScore
    top: List[PairScore]

class BotStatus(BaseModel):
    running: bool
    symbol: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    cfg: Dict[str, Any] = Field(default_factory=dict)

class ConfigEnvelope(BaseModel):
    cfg: Dict[str, Any]
