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
  private get api(): string {
    return (window as any).__API__ as string;
  }
  private get ws(): string {
    return (window as any).__WS__ as string;
  }

  constructor(private http: HttpClient) {}

  // ---- BOT ----
  status(): Observable<BotStatus> {
    return this.http.get<BotStatus>(`${this.api}/bot/status`);
  }

  start(): Observable<any> {
    return this.http.post(`${this.api}/bot/start`, {});
  }

  stop(): Observable<any> {
    return this.http.post(`${this.api}/bot/stop`, {});
  }

  // ---- SCANNER ----
  // При необходимости передай payload, иначе отправится пустой объект
  scan(payload: any = {}): Observable<any> {
    return this.http.post(`${this.api}/scanner/scan`, payload);
  }

  // ---- CONFIG ----
  getConfig(): Observable<any> {
    return this.http.get(`${this.api}/config`);
  }

  putConfig(body: any): Observable<any> {
    return this.http.put(`${this.api}/config`, body);
  }

  // ---- RISK ----
  getRiskStatus(): Observable<any> {
    return this.http.get(`${this.api}/risk/status`);
  }

  unlockRisk(): Observable<any> {
    return this.http.post(`${this.api}/risk/unlock`, {});
  }
}
