import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

// Материальные модули/общий модуль проекта
import { AppMaterialModule } from './app.module';

// Сервисы
import { ApiService } from './services/api.service';
import { WsService } from './services/ws.service';
import { MatSnackBar } from '@angular/material/snack-bar';

// Компоненты
import { ControlsComponent } from './components/controls/controls.component';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { LogsComponent } from './components/logs/logs.component';
import { GuardsComponent } from './components/guards/guards.component';
import { TvAdvancedComponent } from './components/tv-advanced/tv-advanced.component';
import { HistoryComponent } from './components/history/history.component';
import { OrdersWidgetComponent } from './components/orders-widget/orders-widget.component';

type Theme = 'dark' | 'light';
type ChartMode = 'tv' | 'lightweight' | 'none';

interface LiveOrder { id: string; side: 'BUY'|'SELL'; price: number; qty: number; status: string; ts: number; }
interface LiveTrade { id: string; side: 'BUY'|'SELL'; price: number; qty: number; pnl: number; ts: number; }
interface DbRow { event: string; symbol: string; side: string; type: string; price: number; qty: number; status: string; ts: number; }

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule, FormsModule, AppMaterialModule,
    ControlsComponent, DashboardComponent, LogsComponent, GuardsComponent,
    TvAdvancedComponent, HistoryComponent, OrdersWidgetComponent
  ],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent {
  title = 'Amadeus';

  // overlays
  showConfig = false;
  showHistory = false;
  histTab: 'live'|'db' = 'live';

  // UI
  chartMode: ChartMode = 'tv';
  theme: Theme = 'dark';

  // risk
  risk: any = null;
  private riskTimer?: any;

  // live lists
  liveOpen: Record<string, LiveOrder> = {};
  liveTrades: LiveTrade[] = [];

  // DB
  dbLoading = false;
  dbOrders: DbRow[] = [];
  dbTrades: DbRow[] = [];

  // cfg
  cfg: any = {
    api: { paper: true, shadow: true, autostart: false },
    shadow: { rest_base: 'https://api.binance.com', ws_base: 'wss://stream.binance.com:9443/ws' },
    ui: { chart: 'tv', theme: 'dark' }
  };

  constructor(private api: ApiService, private ws: WsService, private snack: MatSnackBar) {}

  ngOnInit() {
    // первичная подгрузка конфига
    this.api.getConfig().subscribe({
      next: (res: any) => {
        const incoming = res?.cfg ?? res ?? {};
        this.cfg = { ...this.cfg, ...incoming };
        const ui = this.cfg.ui || {};
        const m = String(ui.chart || 'tv').toLowerCase();
        this.chartMode = (m === 'tv') ? 'tv' : (m === 'lightweight' ? 'lightweight' : 'none');
        this.theme = (ui.theme === 'light') ? 'light' : 'dark';
      },
      error: _ => {}
    });

    // риск — периодически
    this.refreshRisk();
    this.riskTimer = setInterval(() => this.refreshRisk(), 5000);

    // WS (live-история)
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
          status: String(msg.evt || msg.status || 'NEW').toUpperCase(),
          ts: Number(msg.ts || Date.now())
        };
        if (row.status === 'NEW') this.liveOpen[id] = row;
        else {
          if (this.liveOpen[id]) this.liveOpen[id] = row;
          if (row.status === 'FILLED' || row.status === 'CANCELED') delete this.liveOpen[id];
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
        // ограничение live буфера до 100
        if (this.liveTrades.length > 100) this.liveTrades.splice(100);
      }
    });
  }

  ngOnDestroy() { if (this.riskTimer) clearInterval(this.riskTimer); }

  // overlays
  openConfig() { this.showConfig = true; }
  openHistory() { this.showHistory = true; this.setHistTab('live'); }
  closeOverlays() { this.showConfig = false; this.showHistory = false; }

  setHistTab(tab: 'live'|'db') { this.histTab = tab; if (tab === 'db') this.loadDbHistory(); }

  // DB history — лимиты ↓ 100
  private boolToSide(v: any): string {
    if (typeof v === 'boolean') return v ? 'BUY' : 'SELL';
    const s = String(v || '').toUpperCase();
    if (s === 'TRUE')  return 'BUY';
    if (s === 'FALSE') return 'SELL';
    return s || '';
  }
  private mapOrder = (r: any): DbRow => {
    const event = String(r?.event ?? r?.evt ?? r?.kind ?? r?.status ?? 'ORDER').toUpperCase();
    const symbol = String(r?.symbol ?? r?.S ?? r?.s ?? this.cfg?.strategy?.symbol ?? '');
    const side = this.boolToSide(r?.side ?? r?.SIDE ?? r?.buyer ?? r?.isBuyer ?? '');
    const typ = String(r?.orderType ?? r?.type ?? r?.ord_type ?? 'LIMIT').toUpperCase();
    const price = Number(r?.price ?? r?.p ?? r?.avgPrice ?? r?.stopPrice ?? r?.limitPrice ?? 0);
    const qty = Number(r?.qty ?? r?.quantity ?? r?.q ?? r?.executedQty ?? r?.origQty ?? 0);
    const status = String(r?.status ?? r?.evt ?? '').toUpperCase();
    const ts = Number(r?.ts ?? r?.time ?? r?.transactTime ?? r?.T ?? Date.now());
    return { event, symbol, side, type: typ, price, qty, status, ts };
  };
  private mapTrade = (r: any): DbRow => {
    const symbol = String(r?.symbol ?? r?.S ?? r?.s ?? this.cfg?.strategy?.symbol ?? '');
    const side = this.boolToSide(r?.side ?? r?.isBuyer ?? '');
    const price = Number(r?.price ?? r?.p ?? r?.avgPrice ?? 0);
    const qty = Number(r?.qty ?? r?.q ?? r?.executedQty ?? r?.origQty ?? 0);
    const status = String(r?.status ?? 'FILLED').toUpperCase();
    const ts = Number(r?.ts ?? r?.time ?? r?.T ?? Date.now());
    return { event: 'TRADE', symbol, side, type: 'TRADE', price, qty, status, ts };
  };
  loadDbHistory() {
    this.dbLoading = true;
    let done = 0; const finish = () => { done++; if (done >= 2) this.dbLoading = false; };
    this.api.historyOrders(100, 0).subscribe({
      next: (res: any) => {
        const rows = Array.isArray(res?.items) ? res.items : (Array.isArray(res) ? res : []);
        this.dbOrders = rows.map(this.mapOrder);
      }, error: _ => this.dbOrders = [], complete: finish
    });
    this.api.historyTrades(100, 0).subscribe({
      next: (res: any) => {
        const rows = Array.isArray(res?.items) ? res.items : (Array.isArray(res) ? res : []);
        this.dbTrades = rows.map(this.mapTrade);
      }, error: _ => this.dbTrades = [], complete: finish
    });
  }

  // Риск
  refreshRisk() { this.api.getRiskStatus().subscribe({ next: r => this.risk = r || {}, error: _ => this.risk = null }); }

  // Chart toggle (сохраняем в конфиге)
  toggleChart() {
    this.chartMode = this.chartMode === 'tv' ? 'lightweight' : 'tv';
    this.cfg.ui = this.cfg.ui || {};
    this.cfg.ui.chart = this.chartMode;
    this.api.putConfig(this.cfg).subscribe({ next: _ => {}, error: _ => {} });
  }

  isTv() { return this.chartMode === 'tv'; }
  get liveOpenList(): LiveOrder[] { return Object.values(this.liveOpen).sort((a,b)=>b.ts-a.ts); }
  trackId(_i: number, r: {id: string}) { return r.id; }
}
