import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AppMaterialModule } from '../../app.module';
import { WsService } from '../../services/ws.service';

interface LiveOrder {
    id: string;
    side: 'BUY'|'SELL';
    price: number;
    qty: number;
    status: string;
    ts: number;
}

@Component({
    selector: 'app-orders-widget',
    standalone: true,
    imports: [CommonModule, AppMaterialModule],
    templateUrl: './orders-widget.component.html',
    styleUrls: ['./orders-widget.component.scss']
})
export class OrdersWidgetComponent {
    orders: LiveOrder[] = [];
    maxKeep = 100;

    constructor(private ws: WsService) {}

    ngOnInit() {
        this.ws.connect();
        this.ws.messages$.subscribe((msg: any) => {
            if (!msg || typeof msg !== 'object') return;
            if (msg.type === 'order_event') {
                const o = msg.order || {};
                const row: LiveOrder = {
                    id: String(msg.id || o.orderId || ''),
                    side: String(msg.side || o.side || 'BUY').toUpperCase() as any,
                    price: Number(msg.price || o.price || 0),
                    qty: Number(msg.qty || o.qty || o.origQty || o.quantity || 0),
                    status: String(msg.evt || msg.status || msg.event || o.status || 'NEW').toUpperCase(),
                    ts: Number(msg.ts || msg.time || msg.T || o.updateTime || o.transactTime || Date.now())
                };
                // кладём сверху
                this.orders.unshift(row);
                if (this.orders.length > this.maxKeep) this.orders.pop();
            }
        });
    }

    trackId(_i: number, r: LiveOrder) { return r.id + ':' + r.ts; }
}
