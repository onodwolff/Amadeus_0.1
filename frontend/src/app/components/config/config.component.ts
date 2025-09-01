import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AppMaterialModule } from '../../app.module';
import { ApiService } from '../../services/api.service';

@Component({
    selector: 'app-config',
    standalone: true,
    imports: [CommonModule, FormsModule, AppMaterialModule],
    templateUrl: './config.component.html',
    styleUrls: ['./config.component.css']
})
export class ConfigComponent {
    cfg: any = { features: { risk_protections: true } };
    cfgStr = '';
    loading = false;
    error = '';

    constructor(private api: ApiService) {}

    ngOnInit(): void { this.load(); }

    load() {
        this.loading = true;
        this.api.getConfig().subscribe({
            next: (res: any) => {
                const raw = res?.cfg ?? {};
                // дефолты
                this.cfg = {
                    features: { risk_protections: true, ...(raw.features || {}) },
                    protections: raw.protections || [],
                    ...raw,
                };
                this.cfgStr = JSON.stringify(this.cfg, null, 2);
                this.loading = false;
                this.error = '';
            },
            error: (err) => { this.error = err?.message ?? 'Ошибка загрузки конфига'; this.loading = false; }
        });
    }

    toggleRisk() {
        if (!this.cfg.features) this.cfg.features = {};
        this.cfg.features.risk_protections = !this.cfg.features.risk_protections;
        this.cfgStr = JSON.stringify(this.cfg, null, 2);
    }

    save() {
        try {
            // если пользователь правит JSON вручную — доверяем ему
            const parsed = JSON.parse(this.cfgStr);
            this.loading = true;
            this.api.putConfig(parsed).subscribe({
                next: () => { this.loading = false; },
                error: (err) => { this.error = err?.message ?? 'Ошибка сохранения'; this.loading = false; }
            });
        } catch (e:any) {
            this.error = 'JSON невалиден: ' + (e?.message || e);
        }
    }
}
