import { Component } from '@angular/core';
import { ControlsComponent } from './components/controls/controls.component';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { LogsComponent } from './components/logs/logs.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [ControlsComponent, DashboardComponent, LogsComponent],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent { title = 'Amadeus'; }
