import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable, of, timer } from 'rxjs';
import { catchError, switchMap } from 'rxjs/operators';
import { environment } from '../../environments/environment';
import {
  BotStatus,
  Config,
  ConfigGetResponse,
  ConfigResponse,
  HistoryResponse,
  HistoryStats,
  OrderHistoryItem,
  RiskStatus,
  TradeHistoryItem,
} from '../models';

/** Статус бота: расширен под dashboard (metrics?, cfg?) */
// Interface moved to models.ts

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly win = window as unknown as { __API__?: string; __TOKEN__?: string };
  private readonly baseRoot: string = (this.win.__API__ || environment.apiBaseUrl || 'http://127.0.0.1:8100').replace(/\/$/, '');
  readonly api: string = this.baseRoot + '/api';
  private readonly _token: string = this.win.__TOKEN__ || 'secret-token';

  private auth() { return { headers: { 'Authorization': `Bearer ${this._token}` } }; }
  get token(): string { return this._token; }

  /** Шарим статус запуска бота между компонентами */
  readonly running$ = new BehaviorSubject<boolean>(false);

  constructor(private http: HttpClient) {
    // Бэкап к WS: лёгкий пул статуса
    timer(0, 2000).pipe(
        switchMap(() => this.status().pipe(catchError(() => of<BotStatus | null>(null))))
    ).subscribe((s) => {
      if (s && typeof s.running === 'boolean') this.running$.next(!!s.running);
    });
  }

  setRunning(v: boolean) { this.running$.next(!!v); }

  // ------------ BOT ------------
  status(): Observable<BotStatus> { return this.http.get<BotStatus>(`${this.api}/bot/status`, this.auth()); }
  start():  Observable<unknown>   { return this.http.post(`${this.api}/bot/start`, {}, this.auth()); }
  stop():   Observable<unknown>   { return this.http.post(`${this.api}/bot/stop`,  {}, this.auth()); }

  // ----------- SCANNER ---------
  scan(): Observable<unknown>     { return this.http.post(`${this.api}/scanner/scan`, {}, this.auth()); }

  // ----------- CONFIG ----------
  getConfig(): Observable<ConfigGetResponse> { return this.http.get<ConfigGetResponse>(`${this.api}/config`, this.auth()); }

  /**
   * Универсальный сейв конфигурации:
   * 1) PUT {cfg} → 2) PUT raw → 3) POST {cfg} → 4) POST raw
   * Это гасит 405/400/422 при несовпадении контракта.
   */
  putConfig(cfg: Config | string): Observable<unknown> {
    const url = `${this.api}/config`;
    const bodyWrapped = { cfg };
    const bodyRaw = cfg;

    const opts = this.auth();
    const getStatus = (e: unknown) => (e as { status?: number } | undefined)?.status;
    return this.http.put(url, bodyWrapped, opts).pipe(
        catchError((err1: unknown) => {
          if ([405, 400, 415, 422].includes(getStatus(err1) ?? 0)) {
            return this.http.put(url, bodyRaw, opts).pipe(
                catchError((err2: unknown) => {
                  if ([405, 400, 415, 422].includes(getStatus(err2) ?? 0)) {
                    return this.http.post(url, bodyWrapped, opts).pipe(
                        catchError((err3: unknown) => {
                          if ([405, 400, 415, 422].includes(getStatus(err3) ?? 0)) {
                            return this.http.post(url, bodyRaw, opts);
                          }
                          throw err3;
                        })
                    );
                  }
                  throw err2;
                })
            );
          }
          throw err1;
        })
    );
  }

  getDefaultConfig(): Observable<ConfigResponse> { return this.http.get<ConfigResponse>(`${this.api}/config/default`, this.auth()); }
  restoreConfig():    Observable<ConfigResponse> { return this.http.post<ConfigResponse>(`${this.api}/config/restore`, {}, this.auth()); }

  // ------------ RISK -----------
  getRiskStatus(): Observable<RiskStatus> { return this.http.get<RiskStatus>(`${this.api}/risk/status`, this.auth()); }
  unlockRisk():    Observable<unknown> { return this.http.post(`${this.api}/risk/unlock`, {}, this.auth()); }

  // ----------- HISTORY ---------
  historyOrders(limit = 200, offset = 0): Observable<HistoryResponse<OrderHistoryItem>> {
    return this.http.get<HistoryResponse<OrderHistoryItem>>(`${this.api}/history/orders?limit=${limit}&offset=${offset}`, this.auth());
  }
  historyTrades(limit = 200, offset = 0): Observable<HistoryResponse<TradeHistoryItem>> {
    return this.http.get<HistoryResponse<TradeHistoryItem>>(`${this.api}/history/trades?limit=${limit}&offset=${offset}`, this.auth());
  }
  historyStats(): Observable<HistoryStats> {
    return this.http.get<HistoryStats>(`${this.api}/history/stats`, this.auth());
  }
  historyClear(kind: 'orders'|'trades'|'all' = 'all'): Observable<HistoryStats> {
    return this.http.post<HistoryStats>(`${this.api}/history/clear?kind=${kind}`, {}, this.auth());
  }
  historyExportUrl(kind: 'orders'|'trades' = 'orders'): string {
    return `${this.api}/history/export.csv?kind=${kind}&token=${this._token}`;
  }
}
