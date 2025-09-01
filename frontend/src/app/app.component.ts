import { Component } from '@angular/core';
import { ControlsComponent } from './components/controls/controls.component';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { LogsComponent } from './components/logs/logs.component';
import { ConfigComponent } from './components/config/config.component';
import { GuardsComponent } from './components/guards/guards.component';
import { ChartHostComponent } from './components/chart-host/chart-host.component';
import { HistoryComponent } from './components/history/history.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    ControlsComponent,
    DashboardComponent,
    LogsComponent,
    ConfigComponent,
    GuardsComponent,
    ChartHostComponent,   // ⬅️ тут хост, он сам подгружает нужный чарт
    HistoryComponent
  ],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent { title = 'Amadeus'; }
