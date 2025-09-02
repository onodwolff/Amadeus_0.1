import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable, of, timer } from 'rxjs';
import { catchError, switchMap } from 'rxjs/operators';

/** Статус бота: расширен под dashboard (metrics?, cfg?) */
export interface BotStatus {
  running: boolean;
  symbol?: string;
  equity?: number;
  ts?: number;
  metrics?: any;
  cfg?: any;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly baseRoot: string = ((window as any).__API__ || 'http://127.0.0.1:8100').replace(/\/$/, '');
  readonly api: string = this.baseRoot + '/api';

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
  status(): Observable<BotStatus> { return this.http.get<BotStatus>(`${this.api}/bot/status`); }
  start():  Observable<any>       { return this.http.post(`${this.api}/bot/start`, {}); }
  stop():   Observable<any>       { return this.http.post(`${this.api}/bot/stop`,  {}); }

  // ----------- SCANNER ---------
  scan(): Observable<any>         { return this.http.post(`${this.api}/scanner/scan`, {}); }

  // ----------- CONFIG ----------
  getConfig(): Observable<any>    { return this.http.get(`${this.api}/config`); }

  /**
   * Универсальный сейв конфигурации:
   * 1) PUT {cfg} → 2) PUT raw → 3) POST {cfg} → 4) POST raw
   * Это гасит 405/400/422 при несовпадении контракта.
   */
  putConfig(cfg: any): Observable<any> {
    const url = `${this.api}/config`;
    const bodyWrapped = { cfg };
    const bodyRaw = cfg;

    return this.http.put(url, bodyWrapped).pipe(
        catchError(err1 => {
          if ([405, 400, 415, 422].includes(err1?.status)) {
            return this.http.put(url, bodyRaw).pipe(
                catchError(err2 => {
                  if ([405, 400, 415, 422].includes(err2?.status)) {
                    return this.http.post(url, bodyWrapped).pipe(
                        catchError(err3 => {
                          if ([405, 400, 415, 422].includes(err3?.status)) {
                            return this.http.post(url, bodyRaw);
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

  getDefaultConfig(): Observable<any> { return this.http.get(`${this.api}/config/default`); }
  restoreConfig():    Observable<any> { return this.http.post(`${this.api}/config/restore`, {}); }

  // ------------ RISK -----------
  getRiskStatus(): Observable<any> { return this.http.get(`${this.api}/risk/status`); }
  unlockRisk():    Observable<any> { return this.http.post(`${this.api}/risk/unlock`, {}); }

  // ----------- HISTORY ---------
  historyOrders(limit = 200, offset = 0): Observable<any> {
    return this.http.get(`${this.api}/history/orders?limit=${limit}&offset=${offset}`);
  }
  historyTrades(limit = 200, offset = 0): Observable<any> {
    return this.http.get(`${this.api}/history/trades?limit=${limit}&offset=${offset}`);
  }
  historyStats(): Observable<any> {
    return this.http.get(`${this.api}/history/stats`);
  }
  historyClear(kind: 'orders'|'trades'|'all' = 'all'): Observable<any> {
    return this.http.post(`${this.api}/history/clear?kind=${kind}`, {});
  }
  historyExportUrl(kind: 'orders'|'trades' = 'orders'): string {
    return `${this.api}/history/export.csv?kind=${kind}`;
  }
}