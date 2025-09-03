import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AppMaterialModule } from '../../app.module';
import { ApiService } from '../../services/api.service';
import { MatSnackBar } from '@angular/material/snack-bar';
import { FormBuilder, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { Config, ConfigGetResponse, ConfigResponse } from '../../models';
import { MatRadioModule } from '@angular/material/radio';
import { MatSliderModule } from '@angular/material/slider';
import { MatFormFieldModule } from '@angular/material/form-field';

@Component({
  selector: 'app-config',
  standalone: true,
  imports: [
    CommonModule,
    AppMaterialModule,
    ReactiveFormsModule,
    MatRadioModule,
    MatSliderModule,
    MatFormFieldModule,
  ],
  templateUrl: './config.component.html',
  styleUrls: ['./config.component.css'],
})
export class ConfigComponent {
  loading = true;
  err = '';
  cfgForm: FormGroup;

  constructor(
    private api: ApiService,
    private snack: MatSnackBar,
    private fb: FormBuilder
  ) {
    this.cfgForm = this.fb.group({
      api: this.fb.group({
        paper: [false],
        shadow: [false],
        autostart: [false],
      }),
      shadow: this.fb.group({
        rest_base: [''],
        ws_base: [''],
      }),
      ui: this.fb.group({
        chart: [''],
        theme: [''],
      }),
      risk: this.fb.group({
        max_drawdown_pct: [0],
        dd_window_sec: [0],
        stop_duration_sec: [0],
        cooldown_sec: [0],
        min_trades_for_dd: [0],
      }),
      strategy: this.fb.group({
        symbol: [''],
        market_maker: this.fb.group({
          aggressive_take: [false],
          capital_usage: [0],
        }),
      }),
    });
  }

  ngOnInit() {
    this.load();
  }

  load() {
    this.loading = true;
    this.err = '';
    const isConfigResp = (
      r: ConfigGetResponse
    ): r is ConfigResponse => (r as ConfigResponse).cfg !== undefined;
    this.api.getConfig().subscribe({
      next: (res: ConfigGetResponse) => {
        const cfg: Config = isConfigResp(res) ? res.cfg : res;
        this.cfgForm.reset();
        if (cfg) this.cfgForm.patchValue(cfg);
        this.loading = false;
      },
      error: (e: unknown) => {
        this.err = String((e as { message?: string })?.message || e);
        this.loading = false;
      },
    });
  }

  save() {
    this.err = '';
    const cfg = this.cfgForm.getRawValue() as Config;
    this.api.putConfig(cfg).subscribe({
      next: () => {
        this.snack.open('Сохранено', 'OK', { duration: 1200 });
        this.load();
      },
      error: (e: unknown) => {
        const errObj = e as { error?: { detail?: string }; message?: string };
        this.err = String(errObj.error?.detail || errObj.message || e);
      },
    });
  }

  loadDefault() {
    this.api.getDefaultConfig().subscribe({
      next: (res: ConfigResponse) => {
        this.cfgForm.reset();
        if (res?.cfg) this.cfgForm.patchValue(res.cfg);
      },
      error: (e: unknown) => {
        this.err = String((e as { message?: string })?.message || e);
      },
    });
  }

  restoreBackup() {
    this.api.restoreConfig().subscribe({
      next: (res: ConfigResponse) => {
        this.cfgForm.reset();
        if (res?.cfg) this.cfgForm.patchValue(res.cfg);
        this.snack.open('Откат выполнен', 'OK', { duration: 1200 });
      },
      error: (e: unknown) => {
        const errObj = e as { error?: { detail?: string }; message?: string };
        this.err = String(errObj.error?.detail || errObj.message || e);
      },
    });
  }

  clearLocal() {
    try {
      localStorage.clear();
      sessionStorage.clear();
    } catch {}
    this.snack.open('Кэш браузера очищен (local/session).', 'OK', {
      duration: 1200,
    });
  }
}
