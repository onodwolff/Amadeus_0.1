import { Component } from '@angular/core';
import { ControlsComponent } from './components/controls/controls.component';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { LogsComponent } from './components/logs/logs.component';
import { ConfigComponent } from './components/config/config.component';
import { GuardsComponent } from './components/guards/guards.component';
import { ChartHostComponent } from './components/chart-host/chart-host.component';
import { HistoryComponent } from './components/history/history.component';
import { RiskWidgetComponent } from './components/risk-widget/risk-widget.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    ControlsComponent,
    DashboardComponent,
    LogsComponent,
    ConfigComponent,
    GuardsComponent,
    ChartHostComponent,
    HistoryComponent,
    RiskWidgetComponent
  ],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent { title = 'Amadeus'; }
