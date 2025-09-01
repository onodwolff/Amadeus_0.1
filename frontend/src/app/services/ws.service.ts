import { Injectable, NgZone } from '@angular/core';
import { webSocket, WebSocketSubject } from 'rxjs/webSocket';
import { Subject, timer } from 'rxjs';
import { delayWhen, retryWhen, tap, shareReplay } from 'rxjs/operators';

@Injectable({ providedIn: 'root' })
export class WsService {
  private socket$: WebSocketSubject<any> | null = null;

  private messagesSubject$ = new Subject<any>();
  /** Новый универсальный поток сообщений */
  readonly messages$ = this.messagesSubject$.asObservable().pipe(shareReplay(1));
  /** ✅ Совместимость со старым кодом */
  readonly stream$ = this.messages$;

  private get url(): string {
    const u = (window as any).__WS__;
    return typeof u === 'string' && u.length ? u : 'ws://127.0.0.1:8100/ws';
  }

  constructor(private zone: NgZone) {
    // автоподключение при создании сервиса
    this.connect();
  }

  /** ✅ Публичный connect для совместимости (идемпотентен) */
  connect(): void {
    if (this.socket$) return;

    const create = () =>
        webSocket({
          url: this.url,
          deserializer: ({ data }) => { try { return JSON.parse(data); } catch { return data; } },
          serializer: (v) => JSON.stringify(v),
          openObserver: { next: () => console.log('[WS] open', this.url) },
          closeObserver: { next: () => { console.log('[WS] close'); this.socket$ = null; } },
        });

    this.socket$ = create();
    this.socket$
        .pipe(
            // Экспоненциальный автобэкофф reconnection
            retryWhen(errs =>
                errs.pipe(
                    tap(() => console.warn('[WS] reconnecting...')),
                    delayWhen((_, i) => timer(Math.min(1000 * Math.pow(1.6, i), 10000))),
                )
            )
        )
        .subscribe({
          next: msg => this.zone.run(() => this.messagesSubject$.next(msg)),
          error: err => console.error('[WS] error', err),
          complete: () => console.log('[WS] complete'),
        });
  }

  /** Отправка в сокет (если нужно) */
  send(payload: any) {
    try { this.socket$?.next(payload); } catch (e) { console.warn('WS send failed', e); }
  }

  /** Опционально: вручную закрыть соединение */
  close() {
    try { this.socket$?.complete(); } catch {}
    this.socket$ = null;
  }
}
