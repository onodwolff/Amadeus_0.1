import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AppMaterialModule } from '../../app.module';
import { ApiService } from '../../services/api.service';
import { MatSnackBar } from '@angular/material/snack-bar';
import { FormsModule } from '@angular/forms'; // ⬅️ добавили
import { Config, ConfigGetResponse, ConfigResponse } from '../../models';

@Component({
    selector: 'app-config',
    standalone: true,
    imports: [CommonModule, AppMaterialModule, FormsModule], // ⬅️ добавили FormsModule
    templateUrl: './config.component.html',
    styleUrls: ['./config.component.css']
})
export class ConfigComponent {
    text = '{\n}\n';
    loading = true;
    err = '';

    constructor(private api: ApiService, private snack: MatSnackBar) {}

    ngOnInit() { this.load(); }

    load() {
        this.loading = true; this.err = '';
        const isConfigResp = (r: ConfigGetResponse): r is ConfigResponse => (r as ConfigResponse).cfg !== undefined;
        this.api.getConfig().subscribe({
            next: (res: ConfigGetResponse) => {
                const cfg: Config = isConfigResp(res) ? res.cfg : res;
                this.text = JSON.stringify(cfg ?? {}, null, 2);
                this.loading = false;
            },
            error: (e: unknown) => {
                this.err = String((e as { message?: string })?.message || e);
                this.loading = false;
            }
        });
    }

    save() {
        this.err = '';
        const raw = this.text?.trim();
        if (!raw) { this.err = 'Нельзя сохранять пустой конфиг.'; return; }
        let parsed: Config | string;
        try {
            parsed = JSON.parse(raw) as Config;
        } catch {
            // отправим как строку — бэкенд сам умеет YAML/JSON
            parsed = raw;
        }
        this.api.putConfig(parsed).subscribe({
            next: () => { this.snack.open('Сохранено', 'OK', { duration: 1200 }); this.load(); },
            error: (e: unknown) => {
                const errObj = e as { error?: { detail?: string }; message?: string };
                this.err = String(errObj.error?.detail || errObj.message || e);
            }
        });
    }

    loadDefault() {
        this.api.getDefaultConfig().subscribe({
            next: (res: ConfigResponse) => { this.text = JSON.stringify(res?.cfg ?? {}, null, 2); },
            error: (e: unknown) => { this.err = String((e as { message?: string })?.message || e); }
        });
    }

    restoreBackup() {
        this.api.restoreConfig().subscribe({
            next: (res: ConfigResponse) => {
                this.text = JSON.stringify(res?.cfg ?? {}, null, 2);
                this.snack.open('Откат выполнен', 'OK', { duration: 1200 });
            },
            error: (e: unknown) => {
                const errObj = e as { error?: { detail?: string }; message?: string };
                this.err = String(errObj.error?.detail || errObj.message || e);
            }
        });
    }

    clearLocal() {
        try { localStorage.clear(); sessionStorage.clear(); } catch {}
        this.snack.open('Кэш браузера очищен (local/session).', 'OK', { duration: 1200 });
    }
}
