import { Component, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AppMaterialModule } from '../../app.module';
import { WsService } from '../../services/ws.service';
import { Subscription } from 'rxjs';

interface LogItem {
  ts: number;
  type: string;
  text: string;
  raw?: any;
}

@Component({
  selector: 'app-logs',
  standalone: true,
  imports: [CommonModule, AppMaterialModule],
  templateUrl: './logs.component.html',
  styleUrls: ['./logs.component.css']
})
export class LogsComponent implements OnDestroy {
  items: LogItem[] = [];
  private sub = new Subscription();
  private maxItems = 500;

  constructor(private ws: WsService) {
    // ✅ Совместимость: теперь connect() публичный (или можно вообще не вызывать — сервис сам автоподключается)
    this.ws.connect();

    this.sub.add(
        // можно было бы использовать messages$, но stream$ оставлен для обратной совместимости
        this.ws.stream$.subscribe((evt: any) => {
          const t = (evt && typeof evt === 'object' && evt.type) ? String(evt.type) : 'text';
          const txt =
              t === 'diag'
                  ? String(evt.text ?? '')
                  : typeof evt === 'string'
                      ? evt
                      : JSON.stringify(evt);
          this.items.unshift({ ts: Date.now(), type: t, text: txt, raw: evt });
          if (this.items.length > this.maxItems) this.items.pop();
        })
    );
  }

  ngOnDestroy(): void { this.sub.unsubscribe(); }

  clear() { this.items = []; }
}
