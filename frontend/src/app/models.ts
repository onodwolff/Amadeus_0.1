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
    rest_base?: string;
    ws_base?: string;
    [key: string]: unknown;
  };
  ui?: {
    chart?: string;
    theme?: string;
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
  strategy?: {
    symbol?: string;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export interface ConfigResponse {
  cfg: Config;
  [key: string]: unknown;
}

export type ConfigGetResponse = Config | ConfigResponse;

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
