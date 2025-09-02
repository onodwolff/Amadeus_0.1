import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable, timer } from 'rxjs';
import { switchMap, catchError } from 'rxjs/operators';

@Injectable({ providedIn: 'root' })
export class ApiService {
  readonly api = 'http://127.0.0.1:8100/api';

  // Глобальное состояние запуска бота
  readonly running$ = new BehaviorSubject<boolean>(false);

  constructor(private http: HttpClient) {
    // Периодический пул статуса на случай потери WS
    timer(0, 2000).pipe(
        switchMap(() => this.status()),
        catchError(() => {
          // если бэкенд недоступен — не трогаем текущее значение
          return [];
        })
    ).subscribe((s: any) => {
      if (s && typeof s.running === 'boolean') this.running$.next(!!s.running);
    });
  }

  // ручная установка (WS дергает сюда)
  setRunning(v: boolean) { this.running$.next(!!v); }

  // BOT
  status(): Observable<any> { return this.http.get(`${this.api}/bot/status`); }
  start(): Observable<any> { return this.http.post(`${this.api}/bot/start`, {}); }
  stop():  Observable<any> { return this.http.post(`${this.api}/bot/stop`,  {}); }

  // CONFIG
  getConfig(): Observable<any> { return this.http.get(`${this.api}/config`); }
  putConfig(cfg: any): Observable<any> { return this.http.post(`${this.api}/config`, cfg); }

  // RISK
  getRiskStatus(): Observable<any> { return this.http.get(`${this.api}/risk/status`); }

  // HISTORY
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
