import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AppMaterialModule } from '../../app.module';
import { ApiService } from '../../services/api.service';
import { RiskStatus } from '../../models';

@Component({
    selector: 'app-risk-widget',
    standalone: true,
    imports: [CommonModule, AppMaterialModule],
    templateUrl: './risk-widget.component.html',
    styleUrls: ['./risk-widget.component.css']
})
export class RiskWidgetComponent {
    loading = true;
    data: RiskStatus | null = null;
    err = '';

    constructor(private api: ApiService) {}

    ngOnInit() { this.refresh(); }

    refresh() {
        this.loading = true;
        this.api.getRiskStatus().subscribe({
            next: (d: RiskStatus) => { this.data = d; this.err = ''; this.loading = false; },
            error: (e: unknown) => { this.err = String((e as { message?: string })?.message || e); this.loading = false; }
        });
    }

    unlock() {
        this.api.unlockRisk().subscribe(() => this.refresh());
    }
}
