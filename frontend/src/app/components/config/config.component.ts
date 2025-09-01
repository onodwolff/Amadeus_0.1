import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AppMaterialModule } from '../../app.module';
import { ApiService } from '../../services/api.service';
import { MatSnackBar } from '@angular/material/snack-bar';
import { FormsModule } from '@angular/forms'; // ⬅️ добавили

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
        this.api.getConfig().subscribe({
            next: (res: any) => {
                const cfg = res?.cfg ?? {};
                this.text = JSON.stringify(cfg, null, 2);
                this.loading = false;
            },
            error: (e) => {
                this.err = String(e?.message || e);
                this.loading = false;
            }
        });
    }

    save() {
        this.err = '';
        const raw = this.text?.trim();
        if (!raw) { this.err = 'Нельзя сохранять пустой конфиг.'; return; }
        let parsed: any = null;
        try {
            parsed = JSON.parse(raw);
        } catch {
            // отправим как строку — бэкенд сам умеет YAML/JSON
            parsed = raw;
        }
        this.api.putConfig(parsed).subscribe({
            next: _ => { this.snack.open('Сохранено', 'OK', { duration: 1200 }); this.load(); },
            error: (e) => { this.err = String(e?.error?.detail || e?.message || e); }
        });
    }

    loadDefault() {
        this.api.getDefaultConfig().subscribe({
            next: (res:any) => { this.text = JSON.stringify(res?.cfg ?? {}, null, 2); },
            error: (e) => { this.err = String(e?.message || e); }
        });
    }

    restoreBackup() {
        this.api.restoreConfig().subscribe({
            next: (res:any) => {
                this.text = JSON.stringify(res?.cfg ?? {}, null, 2);
                this.snack.open('Откат выполнен', 'OK', { duration: 1200 });
            },
            error: (e) => { this.err = String(e?.error?.detail || e?.message || e); }
        });
    }

    clearLocal() {
        try { localStorage.clear(); sessionStorage.clear(); } catch {}
        this.snack.open('Кэш браузера очищен (local/session).', 'OK', { duration: 1200 });
    }
}
