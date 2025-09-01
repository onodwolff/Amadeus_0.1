import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../services/api.service';
import { TvAdvancedComponent } from '../tv-advanced/tv-advanced.component';
import { TvLightweightComponent } from '../tv-lightweight/tv-lightweight.component';

@Component({
    selector: 'app-chart-host',
    standalone: true,
    imports: [CommonModule, TvAdvancedComponent, TvLightweightComponent],
    templateUrl: './chart-host.component.html',
    styleUrls: ['./chart-host.component.css']
})
export class ChartHostComponent {
    chartType: 'tv' | 'lightweight' = 'tv';
    theme: 'dark' | 'light' = 'dark';

    constructor(private api: ApiService) {}

    ngOnInit() {
        this.api.getConfig().subscribe({
            next: (res: any) => {
                const cfg = (res && res.cfg) || {};
                const ui = cfg.ui || {};
                const t = (ui.chart || 'tv').toString().toLowerCase();
                this.chartType = (t === 'lightweight') ? 'lightweight' : 'tv';
                this.theme = (ui.theme === 'light' ? 'light' : 'dark');
            },
            error: _ => {}
        });
    }
}
