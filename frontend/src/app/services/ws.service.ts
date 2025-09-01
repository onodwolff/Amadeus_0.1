import { Injectable } from '@angular/core';
import { Subject } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class WsService {
  stream$ = new Subject<any>();
  ws?: WebSocket;

  private url(): string {
    const w: any = window as any;
    if (w.__WS__) return w.__WS__;
    if (w.__API__) return String(w.__API__).replace(/^http/, 'ws').replace(/\/$/, '') + '/ws';
    return 'ws://127.0.0.1:8100/ws';
  }

  connect(url = this.url()) {
    this.ws = new WebSocket(url);
    this.ws.onmessage = (e) => { try { this.stream$.next(JSON.parse(e.data)); } catch {} };
    this.ws.onclose = () => setTimeout(() => this.connect(url), 1000);
  }
}
