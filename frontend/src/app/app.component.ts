import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AppMaterialModule } from './app.module';

import { ApiService } from './services/api.service';
import { WsService } from './services/ws.service';
import { MatSnackBar } from '@angular/material/snack-bar';

import { ControlsComponent } from './components/controls/controls.component';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { LogsComponent } from './components/logs/logs.component';
import { GuardsComponent } from './components/guards/guards.component';
import { TvAdvancedComponent } from './components/tv-advanced/tv-advanced.component';
import { HistoryComponent } from './components/history/history.component';
import { OrdersWidgetComponent } from './components/orders-widget/orders-widget.component';

type Theme = 'dark' | 'light';
type ChartMode = 'tv' | 'lightweight' | 'none';

interface LiveOrder {
  id: string;
  side: 'BUY'|'SELL';
  price: number;
  qty: number;
  status: 'NEW'|'FILLED'|'CANCELED'|string;
  ts: number;
}
interface LiveTrade {
  id: string;
  side: 'BUY'|'SELL';
  price: number;
  qty: number;
  pnl: number;
  ts: number;
}

interface DbRow {
  event: string;
  symbol: string;
  side: string;
  type: string;
  price: number;
  qty: number;
  status: string;
  ts: number;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    AppMaterialModule,

    ControlsComponent,
    DashboardComponent,
    LogsComponent,
    GuardsComponent,
    TvAdvancedComponent,
    HistoryComponent,
    OrdersWidgetComponent
  ],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent {
  title = 'Amadeus';

  // overlays
  showConfig = false;
  showScanner = false;
  showHistory = false;
  histTab: 'live'|'db' = 'live';

  // UI state
  chartMode: ChartMode = 'none';
  theme: Theme = 'dark';

  // risk status
  risk: any = null;
  private riskTimer?: any;

  // Live-лента
  liveOpen: Record<string, LiveOrder> = {};
  liveTrades: LiveTrade[] = [];

  // DB-история
  dbLoading = false;
  dbOrders: DbRow[] = [];
  dbTrades: DbRow[] = [];

  // текстовые поля для списков сканера
  whitelistText = '';
  blacklistText = '';

  // рабочий конфиг (дефолт)
  cfg: any = {
    features: { market_widget_feed: true, risk_protections: true },
    api: { paper: true, shadow: true },
    shadow: {
      rest_base: 'https://api.binance.com',
      ws_base: 'wss://stream.binance.com:9443/ws'
    },
    ui: { chart: 'lightweight', theme: 'dark' },
    strategy: {
      symbol: 'BNBUSDT',
      quote_size: 10.0,
      min_spread_pct: 0.0,
      cancel_timeout: 10.0,
      post_only: true,
      reorder_interval: 1.0,
      loop_sleep: 0.2
    },
    risk: {
      max_drawdown_pct: 10,
      dd_window_sec: 86400,
      stop_duration_sec: 43200,
      cooldown_sec: 1800,
      min_trades_for_dd: 0
    },
    history: { db_path: 'data/history.sqlite3', retention_days: 365 },
    scanner: {
      enabled: false,
      quote: 'USDT',
      min_vol_usd_24h: 5_000_000,
      max_pairs: 20,
      min_spread_bps: 1.0,
      interval_sec: 30,
      whitelist: [] as string[],
      blacklist: [] as string[]
    }
  };

  constructor(private api: ApiService, private ws: WsService, private snack: MatSnackBar) {}

  ngOnInit() {
    // конфиг
    this.api.getConfig().subscribe({
      next: (res: any) => {
        const incoming = res?.cfg ?? res ?? {};
        this.cfg = this.mergeWithDefaults(incoming);

        const ui = this.cfg.ui || {};
        const m = String(ui.chart || 'lightweight').toLowerCase();
        this.chartMode = (m === 'tv') ? 'tv' : (m === 'lightweight' ? 'lightweight' : 'none');
        this.theme = (ui.theme === 'light') ? 'light' : 'dark';

        this.whitelistText = (this.cfg.scanner?.whitelist || []).join(', ');
        this.blacklistText = (this.cfg.scanner?.blacklist || []).join(', ');
      },
      error: _ => {
        this.chartMode = 'lightweight';
        this.theme = 'dark';
      }
    });

    // risk summary + автообновление
    this.refreshRisk();
    this.riskTimer = setInterval(() => this.refreshRisk(), 5000);

    // WS live
    this.ws.connect();
    this.ws.messages$.subscribe((msg: any) => {
      if (!msg || typeof msg !== 'object') return;

      if (msg.type === 'order_event') {
        const id = String(msg.id || '');
        const row: LiveOrder = {
          id,
          side: String(msg.side || 'BUY').toUpperCase() as any,
          price: Number(msg.price || 0),
          qty: Number(msg.qty || 0),
          status: String(msg.evt || 'NEW') as any,
          ts: Number(msg.ts || Date.now())
        };
        if (row.status === 'NEW') {
          this.liveOpen[id] = row;
        } else {
          if (this.liveOpen[id]) this.liveOpen[id] = row;
          if (row.status === 'FILLED' || row.status === 'CANCELED') {
            delete this.liveOpen[id];
          }
        }
      } else if (msg.type === 'trade') {
        const tr: LiveTrade = {
          id: String(msg.id || ''),
          side: String(msg.side || 'BUY').toUpperCase() as any,
          price: Number(msg.price || 0),
          qty: Number(msg.qty || 0),
          pnl: Number(msg.pnl || 0),
          ts: Number(msg.ts || Date.now())
        };
        this.liveTrades.unshift(tr);
        if (this.liveTrades.length > 400) this.liveTrades.pop();
      }
    });
  }

  ngOnDestroy() {
    if (this.riskTimer) clearInterval(this.riskTimer);
  }

  private mergeWithDefaults(x: any) {
    const d = this.cfg;
    const out = { ...d, ...(x || {}) };

    out.features = { ...d.features, ...(x?.features || {}) };
    out.api = { ...d.api, ...(x?.api || {}) };
    out.shadow = { ...d.shadow, ...(x?.shadow || {}) };
    if (!out.shadow?.rest_base || /testnet|binance\.vision/i.test(out.shadow.rest_base)) {
      out.shadow.rest_base = 'https://api.binance.com';
    }
    if (!out.shadow?.ws_base || /binance\.vision/i.test(out.shadow.ws_base)) {
      out.shadow.ws_base = 'wss://stream.binance.com:9443/ws';
    }

    out.ui = { ...d.ui, ...(x?.ui || {}) };
    out.strategy = { ...d.strategy, ...(x?.strategy || {}) };
    out.risk = { ...d.risk, ...(x?.risk || {}) };
    out.history = { ...d.history, ...(x?.history || {}) };
    out.scanner = { ...d.scanner, ...(x?.scanner || {}) };
    return out;
  }

  // overlays
  openConfig() { this.showConfig = true; }
  openScanner() { this.showScanner = true; }
  openHistory() { this.showHistory = true; this.setHistTab('live'); }
  closeOverlays() { this.showConfig = false; this.showScanner = false; this.showHistory = false; }

  setHistTab(tab: 'live'|'db') {
    this.histTab = tab;
    if (tab === 'db') this.loadDbHistory();
  }

  // утилиты
  private parseList(s: string): string[] {
    return (s || '').split(',').map(t => t.trim()).filter(Boolean);
  }

  private mapOrder = (r: any): DbRow => {
    const event = String(r?.evt ?? r?.event ?? r?.status ?? r?.type ?? 'ORDER');
    const symbol = String(r?.symbol ?? r?.S ?? r?.s ?? this.cfg?.strategy?.symbol ?? '');
    const side = String(r?.side ?? r?.SIDE ?? r?.s ?? '').toUpperCase();
    const typ = String(r?.orderType ?? r?.type ?? r?.ord_type ?? 'LIMIT');
    const price = Number(r?.price ?? r?.p ?? r?.avgPrice ?? r?.stopPrice ?? r?.limitPrice ?? 0);
    const qty = Number(r?.qty ?? r?.quantity ?? r?.q ?? r?.executedQty ?? r?.origQty ?? 0);
    const status = String(r?.status ?? r?.evt ?? '').toUpperCase();
    const ts = Number(r?.ts ?? r?.time ?? r?.transactTime ?? r?.T ?? Date.now());
    return { event, symbol, side, type: typ, price, qty, status, ts };
  };

  private mapTrade = (r: any): DbRow => {
    const symbol = String(r?.symbol ?? r?.S ?? r?.s ?? this.cfg?.strategy?.symbol ?? '');
    const side = String(r?.side ?? r?.isBuyer ?? '').toUpperCase(); // isBuyer-> BUY/SELL у вас может быть true/false; если так — нормализовать на бэке
    const price = Number(r?.price ?? r?.p ?? r?.avgPrice ?? 0);
    const qty = Number(r?.qty ?? r?.q ?? r?.executedQty ?? r?.origQty ?? 0);
    const status = String(r?.status ?? 'FILLED').toUpperCase();
    const ts = Number(r?.ts ?? r?.time ?? r?.T ?? Date.now());
    return { event: 'TRADE', symbol, side, type: 'TRADE', price, qty, status, ts };
  };

  loadDbHistory() {
    this.dbLoading = true;
    let done = 0;
    const finish = () => { done++; if (done >= 2) this.dbLoading = false; };

    this.api.historyOrders(200, 0).subscribe({
      next: (res: any) => {
        const rows = Array.isArray(res?.items) ? res.items : (Array.isArray(res) ? res : []);
        this.dbOrders = rows.map(this.mapOrder);
      },
      error: _ => { this.dbOrders = []; },
      complete: finish
    });

    this.api.historyTrades(200, 0).subscribe({
      next: (res: any) => {
        const rows = Array.isArray(res?.items) ? res.items : (Array.isArray(res) ? res : []);
        this.dbTrades = rows.map(this.mapTrade);
      },
      error: _ => { this.dbTrades = []; },
      complete: finish
    });
  }

  saveConfig() {
    // нормализация чисел
    const s = this.cfg.strategy || {};
    s.quote_size = Math.max(0.000001, Number(s.quote_size || 0));
    s.cancel_timeout = Math.max(1, Number(s.cancel_timeout || 1));
    s.reorder_interval = Math.max(0.1, Number(s.reorder_interval || 0.1));
    s.loop_sleep = Math.max(0.05, Number(s.loop_sleep || 0.05));
    s.min_spread_pct = Math.max(0.0, Number(s.min_spread_pct || 0));

    const sc = this.cfg.scanner || {};
    sc.min_vol_usd_24h = Math.max(0, Number(sc.min_vol_usd_24h || 0));
    sc.max_pairs = Math.max(1, Number(sc.max_pairs || 1));
    sc.min_spread_bps = Math.max(0, Number(sc.min_spread_bps || 0));
    sc.interval_sec = Math.max(5, Number(sc.interval_sec || 5));
    sc.whitelist = this.parseList(this.whitelistText);
    sc.blacklist = this.parseList(this.blacklistText);

    // UI стейт
    const ui = this.cfg.ui || {};
    const m = String(ui.chart || 'lightweight').toLowerCase();
    this.chartMode = (m === 'tv') ? 'tv' : (m === 'lightweight' ? 'lightweight' : 'none');
    this.theme = (ui.theme === 'light') ? 'light' : 'dark';

    this.api.putConfig(this.cfg).subscribe({
      next: _ => { this.snack.open('Настройки сохранены', 'OK', { duration: 1200 }); this.closeOverlays(); },
      error: (e) => {
        const msg = e?.error?.detail || e?.message || 'Ошибка сохранения';
        this.snack.open(String(msg), 'OK', { duration: 2500 });
      }
    });
  }

  triggerScan() {
    this.api.scan().subscribe({
      next: _ => this.snack.open('Сканер запущен', 'OK', { duration: 1200 }),
      error: (e) => {
        const msg = e?.error?.detail || e?.message || 'Ошибка запуска сканера';
        this.snack.open(String(msg), 'OK', { duration: 2500 });
      }
    });
  }

  refreshRisk() {
    this.api.getRiskStatus().subscribe({
      next: (r: any) => this.risk = r || {},
      error: _ => this.risk = null
    });
  }

  isTv() { return this.chartMode === 'tv'; }

  // helpers для шаблона
  get liveOpenList(): LiveOrder[] { return Object.values(this.liveOpen).sort((a,b)=>b.ts-a.ts); }
  trackId(_i: number, r: {id: string}) { return r.id; }
}
