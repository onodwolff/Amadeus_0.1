import { Component, OnInit, OnDestroy, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

// Материальные модули/общий модуль проекта
import { AppMaterialModule } from './app.module';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

// Сервисы
import { ApiService } from './services/api.service';
import { WsService } from './services/ws.service';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Subscription } from 'rxjs';
import {
  Config,
  ConfigGetResponse,
  ConfigResponse,
  HistoryResponse,
  OrderHistoryItem,
  TradeHistoryItem,
  BotStatus,
} from './models';

// Компоненты
import { ControlsComponent } from './components/controls/controls.component';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { LogsComponent } from './components/logs/logs.component';
import { RiskWidgetComponent } from './components/risk-widget/risk-widget.component';
import { TvAdvancedComponent } from './components/tv-advanced/tv-advanced.component';
import { TvLightweightComponent } from './components/tv-lightweight/tv-lightweight.component';
import { HistoryComponent } from './components/history/history.component';
import { OrdersWidgetComponent } from './components/orders-widget/orders-widget.component';
import { ConfigComponent } from './components/config/config.component';
import { ScannerComponent } from './components/scanner/scanner.component';

type Theme = 'dark' | 'light';
type ChartMode = 'tv' | 'lightweight' | 'none';

interface LiveOrder { id: string; side: 'BUY'|'SELL'; price: number; qty: number; status: string; ts: number; }
interface LiveTrade { id: string; side: 'BUY'|'SELL'; price: number; qty: number; pnl: number; ts: number; }
interface DbRow { event: string; symbol: string; side: string; type: string; price: number; qty: number; status: string; ts: number; }

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    // Материальные модули
    AppMaterialModule, MatTooltipModule, MatButtonModule, MatIconModule,
    // Наши компоненты
    ControlsComponent, DashboardComponent, LogsComponent,
    TvAdvancedComponent, TvLightweightComponent,
    HistoryComponent, OrdersWidgetComponent, ConfigComponent, ScannerComponent,
    RiskWidgetComponent
  ],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent implements OnInit, OnDestroy {
  title = 'Amadeus';

  // overlays
  showConfig = false;
  showHistory = false;
  showScanner = false;
  histTab: 'live'|'db' = 'live';

  // UI
  chartMode: ChartMode = 'tv';
  theme: Theme = 'dark';

  // live lists
  liveOpen: Record<string, LiveOrder> = {};
  liveTrades: LiveTrade[] = [];

  // DB
  dbLoading = false;
  dbOrders: DbRow[] = [];
  dbTrades: DbRow[] = [];

  // cfg
  cfg: Config = {
    api: { paper: true, shadow: true, autostart: false },
    shadow: { rest_base: 'https://api.binance.com', ws_base: 'wss://stream.binance.com:9443/ws' },
    ui: { chart: 'tv', theme: 'dark' }
  };

  wsSub?: Subscription;

  constructor(private api: ApiService, private ws: WsService, private snack: MatSnackBar) {}

  ngOnInit() {
    // первичная подгрузка конфига
    const isConfigResp = (r: ConfigGetResponse): r is ConfigResponse => (r as ConfigResponse).cfg !== undefined;
    this.api.getConfig().subscribe({
      next: (res: ConfigGetResponse) => {
        const incoming: Config = isConfigResp(res) ? res.cfg : res;
        this.cfg = { ...this.cfg, ...incoming };
        const ui = this.cfg.ui || {};
        const m = String(ui.chart || 'tv').toLowerCase();
        this.chartMode = (m === 'tv') ? 'tv' : (m === 'lightweight' ? 'lightweight' : 'none');
        this.theme = (ui.theme === 'light') ? 'light' : 'dark';
      },
      error: _ => {}
    });

    // WS (live-история)
    this.ws.connect();
    this.wsSub = this.ws.messages$.subscribe((msg: unknown) => {
      if (!msg || typeof msg !== 'object') return;
      const data = msg as Record<string, unknown>;

      if (data['type'] === 'order_event') {
        const id = String(data['id'] ?? '');
        const row: LiveOrder = {
          id,
          side: String(data['side'] ?? 'BUY').toUpperCase() as 'BUY' | 'SELL',
          price: Number(data['price'] ?? 0),
          qty: Number(data['qty'] ?? 0),
          status: String(data['evt'] ?? data['status'] ?? 'NEW').toUpperCase(),
          ts: Number(data['ts'] ?? Date.now())
        };
        if (row.status === 'NEW') this.liveOpen[id] = row;
        else {
          if (this.liveOpen[id]) this.liveOpen[id] = row;
          if (row.status === 'FILLED' || row.status === 'CANCELED') delete this.liveOpen[id];
        }
      } else if (data['type'] === 'trade') {
        const tr: LiveTrade = {
          id: String(data['id'] ?? ''),
          side: String(data['side'] ?? 'BUY').toUpperCase() as 'BUY' | 'SELL',
          price: Number(data['price'] ?? 0),
          qty: Number(data['qty'] ?? 0),
          pnl: Number(data['pnl'] ?? 0),
          ts: Number(data['ts'] ?? Date.now())
        };
        this.liveTrades.unshift(tr);
        // ограничение live буфера до 100
        if (this.liveTrades.length > 100) this.liveTrades.splice(100);
      }
    });
  }

  ngOnDestroy(): void {
    this.wsSub?.unsubscribe();
  }

  // overlays
  openConfig() { this.showConfig = true; }
  openHistory() { this.showHistory = true; this.setHistTab('live'); }
  openScanner() { this.showScanner = true; }
  closeOverlays() { this.showConfig = false; this.showHistory = false; this.showScanner = false; }

  setHistTab(tab: 'live'|'db') { this.histTab = tab; if (tab === 'db') this.loadDbHistory(); }

  @HostListener('window:keydown', ['$event'])
  handleKey(event: KeyboardEvent) {
    const tag = (event.target as HTMLElement)?.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA') return;
    if (event.key === 'p') this.togglePaper();
    else if (event.key === 'a') this.toggleAggressive();
    else if (event.key === 's') this.toggleQuotes();
  }

  togglePaper() {
    const save = window.confirm('Сохранить новое значение paper в config.yaml?');
    this.api.cmd('p', save).subscribe({
      next: (res: BotStatus) => {
        this.cfg = res.cfg || this.cfg;
        this.api.setRunning(!!res.running);
        this.snack.open(`Paper mode: ${this.cfg.api?.paper ? 'ON' : 'OFF'}`, 'OK', { duration: 2000 });
      },
      error: err => {
        this.snack.open(`Ошибка: ${err?.error?.error || err?.message || 'unknown'}`, 'OK', { duration: 2500 });
      }
    });
  }

  toggleAggressive() {
    const save = window.confirm('Сохранить aggressive_take в config.yaml?');
    this.api.cmd('a', save).subscribe({
      next: (res: BotStatus) => {
        this.cfg = res.cfg || this.cfg;
        const on = this.cfg?.strategy?.market_maker?.aggressive_take;
        this.snack.open(`Aggressive take: ${on ? 'ON' : 'OFF'}`, 'OK', { duration: 2000 });
      },
      error: err => {
        this.snack.open(`Ошибка: ${err?.error?.error || err?.message || 'unknown'}`, 'OK', { duration: 2500 });
      }
    });
  }

  toggleQuotes() {
    this.api.cmd('s').subscribe({
      next: (res: BotStatus) => {
        this.api.setRunning(!!res.running);
        this.snack.open(res.running ? 'Старт' : 'Стоп', 'OK', { duration: 1200 });
      },
      error: err => {
        this.snack.open(`Ошибка: ${err?.error?.error || err?.message || 'unknown'}`, 'OK', { duration: 2500 });
      }
    });
  }

  // DB history — лимиты ↓ 100
  private boolToSide(v: unknown): string {
    if (typeof v === 'boolean') return v ? 'BUY' : 'SELL';
    const s = String(v || '').toUpperCase();
    if (s === 'TRUE')  return 'BUY';
    if (s === 'FALSE') return 'SELL';
    return s || '';
  }
  private mapOrder = (r: Record<string, unknown> | OrderHistoryItem): DbRow => {
    const rec = r as Record<string, unknown>;
    const event = String(rec['event'] ?? rec['evt'] ?? rec['kind'] ?? rec['status'] ?? 'ORDER').toUpperCase();
    const symbol = String(rec['symbol'] ?? rec['S'] ?? rec['s'] ?? this.cfg?.strategy?.symbol ?? '');
    const side = this.boolToSide(rec['side'] ?? rec['SIDE'] ?? rec['buyer'] ?? rec['isBuyer'] ?? '');
    const typ = String(rec['orderType'] ?? rec['type'] ?? rec['ord_type'] ?? 'LIMIT').toUpperCase();
    const price = Number(rec['price'] ?? rec['p'] ?? rec['avgPrice'] ?? rec['stopPrice'] ?? rec['limitPrice'] ?? 0);
    const qty = Number(rec['qty'] ?? rec['quantity'] ?? rec['q'] ?? rec['executedQty'] ?? rec['origQty'] ?? 0);
    const status = String(rec['status'] ?? rec['evt'] ?? '').toUpperCase();
    const ts = Number(rec['ts'] ?? rec['time'] ?? rec['transactTime'] ?? rec['T'] ?? Date.now());
    return { event, symbol, side, type: typ, price, qty, status, ts };
  };
  private mapTrade = (r: Record<string, unknown> | TradeHistoryItem): DbRow => {
    const rec = r as Record<string, unknown>;
    const symbol = String(rec['symbol'] ?? rec['S'] ?? rec['s'] ?? this.cfg?.strategy?.symbol ?? '');
    const side = this.boolToSide(rec['side'] ?? rec['isBuyer'] ?? '');
    const price = Number(rec['price'] ?? rec['p'] ?? rec['avgPrice'] ?? 0);
    const qty = Number(rec['qty'] ?? rec['q'] ?? rec['executedQty'] ?? rec['origQty'] ?? 0);
    const status = String(rec['status'] ?? 'FILLED').toUpperCase();
    const ts = Number(rec['ts'] ?? rec['time'] ?? rec['T'] ?? Date.now());
    return { event: 'TRADE', symbol, side, type: 'TRADE', price, qty, status, ts };
  };
  loadDbHistory() {
    this.dbLoading = true;
    let done = 0; const finish = () => { done++; if (done >= 2) this.dbLoading = false; };
    this.api.historyOrders(100, 0).subscribe({
      next: (res: HistoryResponse<OrderHistoryItem>) => {
        const rows = Array.isArray(res?.items) ? res.items : [];
        this.dbOrders = rows.map(this.mapOrder);
      }, error: _ => this.dbOrders = [], complete: finish
    });
    this.api.historyTrades(100, 0).subscribe({
      next: (res: HistoryResponse<TradeHistoryItem>) => {
        const rows = Array.isArray(res?.items) ? res.items : [];
        this.dbTrades = rows.map(this.mapTrade);
      }, error: _ => this.dbTrades = [], complete: finish
    });
  }

  // Chart toggle (сохраняем в конфиге)
  toggleChart() {
    this.chartMode = this.chartMode === 'tv' ? 'lightweight' : 'tv';
    this.cfg.ui = this.cfg.ui || {};
    this.cfg.ui.chart = this.chartMode;
    this.api.putConfig(this.cfg).subscribe({ next: _ => {}, error: _ => {} });
  }

  isTv() { return this.chartMode === 'tv'; }
  get liveOpenList(): LiveOrder[] { return Object.values(this.liveOpen).sort((a,b)=>b.ts-a.ts); }
  trackId(_i: number, r: LiveOrder) { return r.id; }
}
