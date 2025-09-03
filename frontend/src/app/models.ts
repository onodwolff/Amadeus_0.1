export interface RiskStatus {
  locked: boolean;
  max_drawdown_pct?: number;
  cooldown_left_sec?: number;
  min_trades_for_dd?: number;
  [key: string]: unknown;
}

export interface Config {
  api?: {
    paper?: boolean;
    shadow?: boolean;
    autostart?: boolean;
    [key: string]: unknown;
  };
  shadow?: {
    enabled?: boolean;
    alpha?: number;
    latency_ms?: number;
    post_only_reject?: boolean;
    market_slippage_bps?: number;
    rest_base?: string;
    ws_base?: string;
    [key: string]: unknown;
  };
  ui?: {
    chart?: string;
    theme?: string;
    [key: string]: unknown;
  };
  features?: {
    risk_protections?: boolean;
    market_widget_feed?: boolean;
    [key: string]: unknown;
  };
  risk?: {
    max_drawdown_pct?: number;
    dd_window_sec?: number;
    stop_duration_sec?: number;
    cooldown_sec?: number;
    min_trades_for_dd?: number;
    [key: string]: unknown;
  };
  history?: {
    db_path?: string;
    retention_days?: number;
    [key: string]: unknown;
  };
  scanner?: {
    enabled?: boolean;
    quote?: string;
    min_price?: number;
    min_vol_usdt_24h?: number;
    top_by_volume?: number;
    max_pairs?: number;
    min_spread_bps?: number;
    vol_bars?: number;
    score?: {
      w_spread?: number;
      w_vol?: number;
      [key: string]: unknown;
    };
    whitelist?: string[];
    blacklist?: string[];
    [key: string]: unknown;
  };
  strategy?: {
    name?: string;
    market_maker?: {
      symbol?: string;
      quote_size?: number;
      capital_usage?: number;
      min_spread_pct?: number;
      cancel_timeout?: number;
      reorder_interval?: number;
      loop_sleep?: number;
      depth_level?: number;
      maker_fee_pct?: number;
      taker_fee_pct?: number;
      econ?: {
        min_net_pct?: number;
        [key: string]: unknown;
      };
      post_only?: boolean;
      aggressive_take?: boolean;
      aggressive_bps?: number;
      inventory_target?: number;
      inventory_tolerance?: number;
      allow_short?: boolean;
      status_poll_interval?: number;
      stats_interval?: number;
      ws_timeout?: number;
      bootstrap_on_idle?: boolean;
      rest_bootstrap_interval?: number;
      plan_log_interval?: number;
      paper_cash?: number;
      [key: string]: unknown;
    };
    trend_follow?: Record<string, unknown>;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export interface ConfigResponse {
  cfg: Config;
  [key: string]: unknown;
}

export type ConfigGetResponse = Config | ConfigResponse;

export interface PairScore {
  symbol: string;
  bid: number;
  ask: number;
  spread_bps: number;
  vol_usdt_24h: number;
  vol_bps_1m: number;
  score: number;
}

export interface ScanResponse {
  best: PairScore;
  top: PairScore[];
}

export interface HistoryStats {
  orders: number;
  trades: number;
}

export interface OrderHistoryItem {
  id: number;
  ts: number;
  event: string;
  symbol: string;
  side: string;
  type: string;
  price: number | null;
  qty: number | null;
  status: string;
}

export interface TradeHistoryItem {
  id: number;
  ts: number;
  type: string;
  symbol: string;
  side: string;
  price: number | null;
  qty: number | null;
  pnl: number | null;
}

export interface HistoryResponse<T> {
  items: T[];
}

export interface BotStatus {
  running: boolean;
  symbol?: string;
  equity?: number;
  ts?: number;
  metrics?: Record<string, unknown>;
  cfg?: Config;
}
