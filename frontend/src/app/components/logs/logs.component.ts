import { Component } from '@angular/core';
import { WsService } from '../../services/ws.service';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-logs',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './logs.component.html',
  styleUrls: ['./logs.component.css']
})
export class LogsComponent {
  rows: any[] = [];
  constructor(ws: WsService) {
    ws.connect();
    ws.stream$.subscribe(evt => {
      if (evt.type === 'diag' || evt.type === 'stats' || evt.type === 'market' || evt.type === 'fill' || evt.type==='order_event') {
        this.rows.unshift({ ts: new Date().toLocaleTimeString(), evt });
        this.rows = this.rows.slice(0, 200);
      }
    });
  }
}
