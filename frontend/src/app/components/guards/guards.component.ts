import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AppMaterialModule } from '../../app.module';
import { ApiService } from '../../services/api.service';

@Component({
    selector: 'app-guards',
    standalone: true,
    imports: [CommonModule, AppMaterialModule],
    templateUrl: './guards.component.html',
    styleUrls: ['./guards.component.scss']
})
export class GuardsComponent {
    data: any = null;
    loading = false;
    error = '';

    constructor(private api: ApiService) {}

    ngOnInit() { this.refresh(); }

    refresh() {
        this.loading = true;
        this.api.getRiskStatus().subscribe({
            next: (res) => { this.data = res; this.loading = false; this.error=''; },
            error: (e) => { this.error = e?.message ?? 'Ошибка'; this.loading = false; }
        });
    }

    unlock() {
        this.api.unlockRisk().subscribe({ next: () => this.refresh() });
    }
}
