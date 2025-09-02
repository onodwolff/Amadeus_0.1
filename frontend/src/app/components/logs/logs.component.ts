import { Component, ElementRef, ViewChild, NgZone } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AppMaterialModule } from '../../app.module';
import { WsService } from '../../services/ws.service';

interface LogRow {
    ts: number;
    type: string;
    text: string;
}

@Component({
    selector: 'app-logs',
    standalone: true,
    imports: [CommonModule, AppMaterialModule],
    templateUrl: './logs.component.html',
    styleUrls: ['./logs.component.css']
})
export class LogsComponent {
    @ViewChild('pane') pane?: ElementRef<HTMLDivElement>;

    rows: LogRow[] = [];
    maxRows = 2000;

    constructor(private ws: WsService, private zone: NgZone) {}

    ngOnInit() {
        this.ws.connect();
        this.ws.stream$.subscribe((evt: any) => {
            this.zone.run(() => this.onEvent(evt));
        });
    }

    private onEvent(evt: any) {
        const t = Date.now();

        let type = 'msg';
        let text = '';

        if (!evt) { type = 'diag'; text = 'empty event'; }
        else if (typeof evt === 'string') { type = 'diag'; text = evt; }
        else if (evt.type) { type = String(evt.type); }

        switch (type) {
            case 'status':
                text = `running=${evt.running} equity=${evt.equity ?? ''} symbol=${evt.symbol ?? ''}`;
                break;
            case 'diag':
                text = String(evt.text ?? JSON.stringify(evt));
                break;
            case 'stats':
                text = `ws_clients=${evt.ws_clients} ws_rate=${evt.ws_rate}`;
                break;
            case 'order_event':
                text = `ORDER ${evt.evt || evt.status} ${evt.side} @ ${evt.price} x ${evt.qty}`;
                break;
            case 'trade':
                text = `TRADE ${evt.side} @ ${evt.price} x ${evt.qty} pnl=${evt.pnl ?? ''}`;
                break;
            default:
                text = text || JSON.stringify(evt);
        }

        this.rows.push({ ts: t, type, text });
        if (this.rows.length > this.maxRows) this.rows.splice(0, this.rows.length - this.maxRows);
    }

    clear() { this.rows = []; }
}
