from __future__ import annotations
import os
import yaml
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ValidationError, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiConfig(BaseModel):
    paper: bool = True
    autostart: bool = False
    shadow: bool = False
    model_config = ConfigDict(extra="forbid")


class ShadowConfig(BaseModel):
    enabled: bool = True
    alpha: float = 0.85
    latency_ms: int = 120
    post_only_reject: bool = True
    market_slippage_bps: float = 1.0
    model_config = ConfigDict(extra="forbid")


class UiConfig(BaseModel):
    chart: str = "tv"
    theme: str = "dark"
    model_config = ConfigDict(extra="forbid")


class FeaturesConfig(BaseModel):
    risk_protections: bool = True
    market_widget_feed: bool = True
    model_config = ConfigDict(extra="forbid")


class RiskConfig(BaseModel):
    max_drawdown_pct: float = 10.0
    dd_window_sec: int = 24 * 3600
    stop_duration_sec: int = 12 * 3600
    cooldown_sec: int = 30 * 60
    min_trades_for_dd: int = 0
    model_config = ConfigDict(extra="forbid")


class HistoryConfig(BaseModel):
    db_path: str = "data/history.db"
    retention_days: int = 365
    model_config = ConfigDict(extra="forbid")


class ScannerScoreConfig(BaseModel):
    w_spread: float = 1.0
    w_vol: float = 0.3
    model_config = ConfigDict(extra="forbid")


class ScannerConfig(BaseModel):
    enabled: bool = False
    quote: str = "USDT"
    min_price: float = 0.0001
    min_vol_usdt_24h: int = 3_000_000
    top_by_volume: int = 120
    max_pairs: int = 60
    min_spread_bps: float = 5.0
    vol_bars: int = 0
    score: ScannerScoreConfig = ScannerScoreConfig()
    whitelist: List[str] = Field(default_factory=list)
    blacklist: List[str] = Field(default_factory=list)
    model_config = ConfigDict(extra="forbid")


class StrategyEconConfig(BaseModel):
    min_net_pct: float = 0.10
    model_config = ConfigDict(extra="forbid")


class MarketMakerStrategyConfig(BaseModel):
    symbol: str = "BNBUSDT"
    quote_size: float = 10.0
    capital_usage: float = Field(1.0, ge=0.0, le=1.0)
    min_spread_pct: float = 0.0
    cancel_timeout: float = 10.0
    reorder_interval: float = 1.0
    loop_sleep: float = 0.2
    depth_level: int = 5
    maker_fee_pct: float = 0.1
    taker_fee_pct: float = 0.1
    econ: StrategyEconConfig = StrategyEconConfig()
    post_only: bool = True
    aggressive_take: bool = False
    aggressive_bps: float = 0.0
    inventory_target: float = 0.5
    inventory_tolerance: float = 0.5
    allow_short: bool = False
    status_poll_interval: float = 2.0
    stats_interval: float = 30.0
    ws_timeout: float = 2.0
    bootstrap_on_idle: bool = True
    rest_bootstrap_interval: float = 3.0
    plan_log_interval: float = 5.0
    paper_cash: float = 1000
    model_config = ConfigDict(extra="forbid")


class StrategyConfig(BaseModel):
    name: str = "market_maker"
    market_maker: MarketMakerStrategyConfig = MarketMakerStrategyConfig()
    trend_follow: Dict[str, Any] = Field(default_factory=dict)
    model_config = ConfigDict(extra="forbid")


class RuntimeConfig(BaseModel):
    api: ApiConfig = ApiConfig()
    shadow: ShadowConfig = ShadowConfig()
    ui: UiConfig = UiConfig()
    features: FeaturesConfig = FeaturesConfig()
    risk: RiskConfig = RiskConfig()
    history: HistoryConfig = HistoryConfig()
    scanner: ScannerConfig = ScannerConfig()
    strategy: StrategyConfig = StrategyConfig()
    model_config = ConfigDict(extra="forbid")


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="", extra="ignore", populate_by_name=True
    )

    app_host: str = Field("0.0.0.0", alias="APP_HOST")
    app_port: int = Field(8000, alias="APP_PORT")
    app_reload: bool = Field(False, alias="APP_RELOAD")
    app_origins: str = Field("*", alias="APP_ORIGINS")

    api_token: str = Field(
        "b1a7528e92de0ce1e456b7afad435b47ce870dcb41688de2af9e815a5a65372c",
        alias="API_TOKEN",
    )

    binance_api_key: Optional[str] = Field(None, alias="BINANCE_API_KEY")
    binance_api_secret: Optional[str] = Field(None, alias="BINANCE_API_SECRET")

    app_config_file: Optional[str] = Field(None, alias="APP_CONFIG_FILE")

    default_cfg: Dict[str, Any] = Field(
        default_factory=lambda: RuntimeConfig().model_dump()
    )
    runtime_cfg: Dict[str, Any] = Field(
        default_factory=lambda: RuntimeConfig().model_dump()
    )

    def load_yaml(self):
        env_file = os.getenv("APP_CONFIG_FILE")
        path = self.app_config_file or env_file or "./config.yaml"
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8-sig") as f:
                    data = yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML: {e}") from e
            # Backward compatibility: legacy strategy fields at top level
            strat_section = data.get("strategy")
            if isinstance(strat_section, dict):
                # Detect legacy format with flattened strategy fields
                if (
                    "symbol" in strat_section or "quote_size" in strat_section
                ) and "market_maker" not in strat_section:
                    name = strat_section.pop("name", "market_maker")
                    strat_section = {
                        "name": name,
                        "market_maker": strat_section,
                    }
                    data["strategy"] = strat_section

                mm_cfg = strat_section.get("market_maker")
                if isinstance(mm_cfg, dict):
                    if "target_pct" in mm_cfg:
                        mm_cfg.setdefault("inventory_target", mm_cfg.pop("target_pct"))
                    if "target_range" in mm_cfg:
                        mm_cfg.setdefault(
                            "inventory_tolerance", mm_cfg.pop("target_range")
                        )

            try:
                cfg = RuntimeConfig.model_validate(data)
            except ValidationError as e:
                raise ValueError(f"Invalid configuration: {e}") from e
            self.runtime_cfg = cfg.model_dump()
        else:
            self.runtime_cfg = RuntimeConfig().model_dump()

    def dump_yaml(self, path: Optional[str] = None):
        p = path or self.app_config_file or "./config.yaml"
        with open(p, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                self.runtime_cfg,
                f,
                allow_unicode=True,
                sort_keys=False,
            )


settings = AppSettings()
