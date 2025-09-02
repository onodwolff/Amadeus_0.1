import { Component, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AppMaterialModule } from '../../app.module';
import { ApiService } from '../../services/api.service';
import { BotStatus } from '../../models';
import { WsService } from '../../services/ws.service';
import { Subscription } from 'rxjs';
import { EquitySparklineComponent } from '../equity-sparkline/equity-sparkline.component'; // ⬅️ импорт спарклайна

interface WsStats { ws_clients: number; ws_rate: number; }
interface MarketSnap { symbol?: string; bid?: number; ask?: number; last?: number; ts?: number; raw?: any; }

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, AppMaterialModule, EquitySparklineComponent], // ⬅️ добавить в imports
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.css']
})
export class DashboardComponent implements OnDestroy {
  running = false;
  symbol = '';
  metrics: any = {};
  cfg: any = {};

  ws: WsStats = { ws_clients: 0, ws_rate: 0 };
  lastDiag = '';
  market: MarketSnap = {};

  private sub = new Subscription();

  constructor(private api: ApiService, private wsSvc: WsService) {
    this.refreshStatus();
    this.bindWs();
  }

  ngOnDestroy(): void { this.sub.unsubscribe(); }

  refreshStatus() {
    this.api.status().subscribe({
      next: (s: BotStatus) => {
        this.running = !!s?.running;
        this.symbol = s?.symbol || '';
        this.metrics = s?.metrics || {};
        this.cfg = s?.cfg || {};
      }
    });
  }

  private bindWs() {
    this.sub.add(
        this.wsSvc.messages$.subscribe((msg: any) => {
          if (!msg) return;

          const t = typeof msg === 'object' && msg.type ? msg.type : null;

          if (t === 'stats') {
            const c = Number(msg.ws_clients ?? 0);
            const r = Number(msg.ws_rate ?? 0);
            this.ws = { ws_clients: c, ws_rate: r };
          } else if (t === 'diag') {
            const text = String(msg.text ?? '');
            this.lastDiag = text;
          } else if (t === 'market') {
            const m = msg as any;
            const sym = (m.symbol || m.s || this.symbol || '').toString();
            const bid = Number(m.bestBid || m.b || m.bid || m.bp);
            const ask = Number(m.bestAsk || m.a || m.ask || m.ap);
            const last = Number(m.lastPrice || m.p || m.last);
            const ts = Number(m.ts || Date.now());
            this.market = {
              symbol: sym,
              bid: isFinite(bid) ? bid : undefined,
              ask: isFinite(ask) ? ask : undefined,
              last: isFinite(last) ? last : undefined,
              ts,
              raw: m
            };
          } else if (t === 'order_event' || t === 'trade' || t === 'fill') {
            const k = t + '_count';
            this.metrics[k] = (this.metrics[k] || 0) + 1;
          }
        })
    );
  }
}
