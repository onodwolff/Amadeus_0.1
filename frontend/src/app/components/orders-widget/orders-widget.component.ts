import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AppMaterialModule } from '../../app.module';
import { WsService } from '../../services/ws.service';

interface OrderRow {
    id: string; side: 'BUY'|'SELL'; price: number; qty: number; status: string; ts: number;
}

interface TradeRow {
    id: string; side: 'BUY'|'SELL'; price: number; qty: number; pnl: number; ts: number;
}

@Component({
    selector: 'app-orders-widget',
    standalone: true,
    imports: [CommonModule, AppMaterialModule],
    templateUrl: './orders-widget.component.html',
    styleUrls: ['./orders-widget.component.css']
})
export class OrdersWidgetComponent {
    open: Record<string, OrderRow> = {};
    recent: TradeRow[] = [];

    constructor(ws: WsService) {
        ws.connect();
        ws.messages$.subscribe((msg: any) => {
            if (!msg || typeof msg !== 'object') return;
            if (msg.type === 'order_event') {
                const id = String(msg.id);
                const row: OrderRow = {
                    id,
                    side: (msg.side || 'BUY').toUpperCase(),
                    price: Number(msg.price || 0),
                    qty: Number(msg.qty || 0),
                    status: String(msg.evt || 'NEW'),
                    ts: Number(msg.ts || Date.now())
                };
                if (row.status === 'NEW') this.open[id] = row;
                else {
                    // обновим и уберём из открытых
                    if (this.open[id]) this.open[id] = row;
                    if (row.status === 'FILLED' || row.status === 'CANCELED') delete this.open[id];
                }
            } else if (msg.type === 'trade') {
                const tr: TradeRow = {
                    id: String(msg.id || ''),
                    side: (msg.side || 'BUY').toUpperCase(),
                    price: Number(msg.price || 0),
                    qty: Number(msg.qty || 0),
                    pnl: Number(msg.pnl || 0),
                    ts: Number(msg.ts || Date.now())
                };
                this.recent.unshift(tr);
                if (this.recent.length > 200) this.recent.pop();
            }
        });
    }

    get openList(): OrderRow[] { return Object.values(this.open).sort((a,b)=>b.ts-a.ts); }
}
