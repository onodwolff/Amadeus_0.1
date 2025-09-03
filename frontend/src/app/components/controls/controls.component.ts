import { Component, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AppMaterialModule } from '../../app.module';
import { ApiService } from '../../services/api.service';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Subscription, timer } from 'rxjs';

@Component({
  selector: 'app-controls',
  standalone: true,
  imports: [CommonModule, AppMaterialModule],
  templateUrl: './controls.component.html',
  styleUrls: ['./controls.component.css']
})
export class ControlsComponent implements OnDestroy {
  running = false;
  busy = false;
  sub?: Subscription;
  autoRefreshSub?: Subscription;

  constructor(private api: ApiService, private snack: MatSnackBar) {
    // глобальный стейт запуска бота
    this.sub = this.api.running$.subscribe(v => this.running = !!v);
    // лёгкий авто-рефреш статуса (как запасной канал, если WS не пришёл)
    this.autoRefreshSub = timer(0, 5000).subscribe(_ => this.refresh());
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
    this.autoRefreshSub?.unsubscribe();
  }

  refresh() {
    this.api.status().subscribe({
      next: s => { this.running = !!s?.running; },
      error: _ => {}
    });
  }

  async doStart() {
    if (this.busy || this.running) return;
    this.busy = true;
    this.api.start().subscribe({
      next: _ => {
        this.api.setRunning(true);
        this.running = true;
        this.snack.open('Старт', 'OK', { duration: 1200 });
      },
      error: err => {
        this.snack.open(`Ошибка старта: ${err?.error?.error || err?.message || 'unknown'}`, 'OK', { duration: 2500 });
      },
      complete: () => { this.busy = false; }
    });
  }

  async doStop() {
    if (this.busy || !this.running) return;
    this.busy = true;
    this.api.stop().subscribe({
      next: _ => {
        this.api.setRunning(false);
        this.running = false;
        // после остановки показываем финальную статистику
        this.api.historyStats().subscribe(stats => {
          this.api.historyTrades(10000, 0).subscribe(res => {
            const pnl = (res.items || []).reduce((s, t) => s + (t.pnl || 0), 0);
            this.snack.open(`Стоп. PnL: ${pnl.toFixed(2)}, Trades: ${stats.trades}`, 'OK', { duration: 4000 });
          });
        });
      },
      error: err => {
        this.snack.open(`Ошибка остановки: ${err?.error?.error || err?.message || 'unknown'}`, 'OK', { duration: 2500 });
      },
      complete: () => { this.busy = false; }
    });
  }
}
