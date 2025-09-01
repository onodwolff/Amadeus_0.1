import { Component } from '@angular/core';
import { ApiService } from '../../services/api.service';
import { MatButtonModule } from '@angular/material/button';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-controls',
  standalone: true,
  imports: [CommonModule, MatButtonModule, MatSlideToggleModule, MatSnackBarModule],
  templateUrl: './controls.component.html',
  styleUrls: ['./controls.component.css']
})
export class ControlsComponent {
  running = false;
  constructor(private api: ApiService, private snack: MatSnackBar) { this.refresh(); }

  refresh() { this.api.status().subscribe((s:any) => this.running = !!s.running); }
  start() { this.api.start().subscribe(_ => { this.running = true; this.snack.open('Старт', 'OK', {duration:1200}); }); }
  stop()  { this.api.stop().subscribe(_ => { this.running = false; this.snack.open('Стоп', 'OK', {duration:1200}); }); }
  scan()  {
    this.api.scan().subscribe((res:any) => {
      const best = res?.best?.symbol || '—';
      this.snack.open('Лучшая пара: ' + best, 'OK', {duration:2000});
      const el = document.getElementById('scanner-results');
      if (el) el.innerText = JSON.stringify(res, null, 2);
    });
  }
}
