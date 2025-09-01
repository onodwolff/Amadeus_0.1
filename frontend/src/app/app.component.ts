import { Component } from '@angular/core';
import { ControlsComponent } from './components/controls/controls.component';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { LogsComponent } from './components/logs/logs.component';
import { ConfigComponent } from './components/config/config.component';
import { GuardsComponent } from './components/guards/guards.component';
import { TvAdvancedComponent } from './components/tv-advanced/tv-advanced.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    ControlsComponent,
    DashboardComponent,
    LogsComponent,
    ConfigComponent,
    GuardsComponent,
    TvAdvancedComponent
  ],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent { title = 'Amadeus'; }
