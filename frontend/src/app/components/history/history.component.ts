import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AppMaterialModule } from '../../app.module';
import { ApiService } from '../../services/api.service';
import { HistoryResponse, HistoryStats, OrderHistoryItem, TradeHistoryItem } from '../../models';

@Component({
    selector: 'app-history',
    standalone: true,
    imports: [CommonModule, AppMaterialModule],
    templateUrl: './history.component.html',
    styleUrls: ['./history.component.css']
})
export class HistoryComponent {
    orders: OrderHistoryItem[] = [];
    trades: TradeHistoryItem[] = [];
    loadingO = false;
    loadingT = false;
    stats: HistoryStats = { orders: 0, trades: 0 };

    constructor(private api: ApiService) {}

    ngOnInit() {
        this.refreshAll();
    }

    refreshAll() {
        this.refreshOrders();
        this.refreshTrades();
        this.api.historyStats().subscribe(s => this.stats = s);
    }

    refreshOrders() {
        this.loadingO = true;
        this.api.historyOrders(200, 0).subscribe({
            next: (res: HistoryResponse<OrderHistoryItem>) => { this.orders = res.items ?? []; this.loadingO = false; },
            error: () => { this.loadingO = false; }
        });
    }

    refreshTrades() {
        this.loadingT = true;
        this.api.historyTrades(200, 0).subscribe({
            next: (res: HistoryResponse<TradeHistoryItem>) => { this.trades = res.items ?? []; this.loadingT = false; },
            error: () => { this.loadingT = false; }
        });
    }

    export(kind: 'orders'|'trades') {
        const url = this.api.historyExportUrl(kind);
        window.open(url, '_blank');
    }

    clear(kind: 'orders'|'trades'|'all') {
        this.api.historyClear(kind).subscribe(() => this.refreshAll());
    }
}
