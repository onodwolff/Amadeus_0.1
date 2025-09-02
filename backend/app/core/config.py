from __future__ import annotations
import os
import yaml
from typing import Any, Dict, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_YAML = {
    "api": {"paper": True},
    "shadow": {"enabled": True, "alpha": 0.85, "latency_ms": 120, "post_only_reject": True, "market_slippage_bps": 1.0},
    "scanner": {
        "enabled": False,
        "quote": "USDT",
        "min_price": 0.0001,
        "min_vol_usdt_24h": 3_000_000,
        "top_by_volume": 120,
        "max_pairs": 60,
        "min_spread_bps": 5.0,
        "vol_bars": 0,
        "score": {"w_spread": 1.0, "w_vol": 0.3},
        "whitelist": [],
        "blacklist": [],
    },
    "strategy": {
        "symbol": "BNBUSDT",
        "quote_size": 10.0,
        "target_pct": 0.5,
        "min_spread_pct": 0.0,
        "cancel_timeout": 10.0,
        "reorder_interval": 1.0,
        "depth_level": 5,
        "maker_fee_pct": 0.1,
        "taker_fee_pct": 0.1,
        "econ": {"min_net_pct": 0.10},
        "post_only": True,
        "aggressive_take": False,
        "aggressive_bps": 0.0,
        "allow_short": False,
        "status_poll_interval": 2.0,
        "stats_interval": 30.0,
        "ws_timeout": 2.0,
        "bootstrap_on_idle": True,
        "rest_bootstrap_interval": 3.0,
        "plan_log_interval": 5.0,
        "paper_cash": 1000,
    },
}

class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    app_host: str = Field("0.0.0.0", alias="APP_HOST")
    app_port: int = Field(8000, alias="APP_PORT")
    app_reload: bool = Field(False, alias="APP_RELOAD")
    app_origins: str = Field("*", alias="APP_ORIGINS")

    api_token: str = Field("secret-token", alias="API_TOKEN")

    binance_api_key: Optional[str] = Field(None, alias="BINANCE_API_KEY")
    binance_api_secret: Optional[str] = Field(None, alias="BINANCE_API_SECRET")

    app_config_file: Optional[str] = Field(None, alias="APP_CONFIG_FILE")

    runtime_cfg: Dict[str, Any] = DEFAULT_YAML.copy()

    def load_yaml(self):
        path = self.app_config_file or os.getenv("APP_CONFIG_FILE") or "./config.yaml"
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8-sig") as f:
                    y = yaml.safe_load(f) or {}
                def deep_merge(a, b):
                    for k, v in b.items():
                        if isinstance(v, dict) and isinstance(a.get(k), dict):
                            deep_merge(a[k], v)
                        else:
                            a[k] = v
                cfg = DEFAULT_YAML.copy()
                deep_merge(cfg, y)
                self.runtime_cfg = cfg
            except Exception:
                self.runtime_cfg = DEFAULT_YAML.copy()
        else:
            self.runtime_cfg = DEFAULT_YAML.copy()

    def dump_yaml(self, path: Optional[str] = None):
        p = path or self.app_config_file or "./config.yaml"
        with open(p, "w", encoding="utf-8") as f:
            yaml.safe_dump(self.runtime_cfg, f, allow_unicode=True, sort_keys=False)

settings = AppSettings()
settings.load_yaml()
