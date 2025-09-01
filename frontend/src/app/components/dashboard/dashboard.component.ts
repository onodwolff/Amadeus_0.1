import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatChipsModule } from '@angular/material/chips';
import { MatTableModule } from '@angular/material/table';
import { WsService } from '../../services/ws.service';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, MatChipsModule, MatTableModule],
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.css'],
})
export class DashboardComponent implements OnInit {
  market: any = {};
  bank: any = {};
  diag = '—';
  wsRate = 0;

  displayedColumns = ['side', 'qty', 'price', 'liq', 'ts'];
  trades: any[] = [];
  orders: any[] = [];

  constructor(public ws: WsService) {}

  ngOnInit(): void {
    this.ws.connect();
    this.ws.stream$.subscribe((evt) => {
      if (evt.type === 'market') this.market = evt;
      if (evt.type === 'bank') this.bank = evt;
      if (evt.type === 'diag') this.diag = evt.text;
      if (evt.type === 'stats') this.wsRate = evt.ws_rate;

      if (evt.type === 'trade' || evt.type === 'fill') {
        const row = {
          side: evt.side || (evt.type === 'trade' ? evt.side : '—'),
          qty: evt.qty || evt.quote,
          price: evt.price || evt.avg,
          liq: evt.liq || '—',
          ts: new Date().toLocaleTimeString(),
        };
        this.trades.unshift(row);
        this.trades = this.trades.slice(0, 40);
      }

      if (evt.type === 'order_event') {
        this.orders.unshift({ ...evt, ts: new Date().toLocaleTimeString() });
        this.orders = this.orders.slice(0, 80);
      }
    });
  }
}
