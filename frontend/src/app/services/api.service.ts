import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface BotStatus {
  running: boolean;
  symbol?: string;
  metrics?: any;
  cfg?: any;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  constructor(private http: HttpClient) {}

  /** REST base, прокидывается через window.__API__ в index.html */
  private get api(): string {
    const v = (window as any).__API__;
    return typeof v === 'string' && v.length ? v : 'http://127.0.0.1:8100';
  }
  /** WS base, если где-то нужно */
  private get ws(): string {
    const v = (window as any).__WS__;
    return typeof v === 'string' && v.length ? v : 'ws://127.0.0.1:8100/ws';
  }

  // ---------- BOT ----------
  status(): Observable<BotStatus> {
    return this.http.get<BotStatus>(`${this.api}/bot/status`);
  }
  start(): Observable<any> {
    return this.http.post(`${this.api}/bot/start`, {});
  }
  stop(): Observable<any> {
    return this.http.post(`${this.api}/bot/stop`, {});
  }

  // ---------- SCANNER ----------
  scan(payload: any = {}): Observable<any> {
    return this.http.post(`${this.api}/scanner/scan`, payload);
  }

  // ---------- CONFIG ----------
  getConfig() { return this.http.get(`${this.api}/config`); }
  putConfig(payload: any) { return this.http.put(`${this.api}/config`, payload); }
  getDefaultConfig() { return this.http.get(`${this.api}/config/default`); }
  restoreConfig() { return this.http.post(`${this.api}/config/restore`, {}); }


// ---------- RISK ----------
  getRiskStatus(): Observable<any> {
    return this.http.get(`${this.api}/risk/status`);
  }
  unlockRisk(): Observable<any> {
    return this.http.post(`${this.api}/risk/unlock`, {});
  }

  // ---------- HISTORY ----------
  historyOrders(limit = 200, offset = 0): Observable<any> {
    return this.http.get(`${this.api}/history/orders?limit=${limit}&offset=${offset}`);
  }
  historyTrades(limit = 200, offset = 0): Observable<any> {
    return this.http.get(`${this.api}/history/trades?limit=${limit}&offset=${offset}`);
  }
  historyStats(): Observable<any> {
    return this.http.get(`${this.api}/history/stats`);
  }
  historyClear(kind: 'orders' | 'trades' | 'all' = 'all'): Observable<any> {
    return this.http.post(`${this.api}/history/clear?kind=${kind}`, {});
  }
  historyExportUrl(kind: 'orders' | 'trades' = 'orders'): string {
    return `${this.api}/history/export.csv?kind=${kind}`;
  }
}
