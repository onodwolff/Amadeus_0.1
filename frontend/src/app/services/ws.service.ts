import { Injectable, NgZone } from '@angular/core';
import { Subject } from 'rxjs';
import { ApiService } from './api.service';

/**
 * WS-клиент с авто-реконнектом.
 * Совместимость: оставляем stream$ и PUBLIC connect() — логи/компоненты зависят.
 */
@Injectable({ providedIn: 'root' })
export class WsService {
    public readonly stream$ = new Subject<any>();
    public readonly messages$ = this.stream$.asObservable();

    private ws?: WebSocket;
    private backoff = 500;
    private readonly maxBackoff = 8000;

    constructor(private zone: NgZone, private api: ApiService) {}

    public connect(url = this._resolveUrl()) {
        if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) return;

        this.ws = new WebSocket(url);

        this.ws.onopen = () => { this.backoff = 500; };

        this.ws.onmessage = (evt) => {
            try {
                const data = JSON.parse(evt.data as any);
                this.zone.run(() => {
                    if (data && data.type === 'status' && typeof data.running === 'boolean') {
                        this.api.setRunning(!!data.running);
                    }
                    this.stream$.next(data);
                });
            } catch { /* ignore non-JSON */ }
        };

        this.ws.onerror = () => { try { this.ws?.close(); } catch {} };

        this.ws.onclose = () => {
            setTimeout(() => this.connect(url), this.backoff);
            this.backoff = Math.min(this.backoff * 2, this.maxBackoff);
        };
    }

    private _resolveUrl(): string {
        const w: any = window as any;
        let base: string;
        if (w.__WS__)   base = String(w.__WS__);
        else if (w.__API__)  base = String(w.__API__).replace(/^http/, 'ws').replace(/\/$/, '') + '/ws';
        else base = 'ws://127.0.0.1:8100/ws';
        const sep = base.includes('?') ? '&' : '?';
        return `${base}${sep}token=${encodeURIComponent(this.api.token)}`;
    }
}
