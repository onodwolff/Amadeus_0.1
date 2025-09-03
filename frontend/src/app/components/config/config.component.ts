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
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatExpansionModule } from '@angular/material/expansion';

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
    MatTooltipModule,
    MatExpansionModule,
  ],
  templateUrl: './config.component.html',
  styleUrls: ['./config.component.css'],
})
export class ConfigComponent {
  loading = true;
  err = '';
  cfgForm: FormGroup;
  tips = {
    paper: 'Режим бумажной торговли без реальных сделок',
    shadow: 'Дублировать сделки в теневом API',
    autostart: 'Запускать бота автоматически',
    rest_base: 'Базовый REST URL теневого API',
    ws_base: 'Базовый WebSocket URL теневого API',
    chart: 'URL шаблона графика',
    theme_light: 'Светлая тема интерфейса',
    theme_dark: 'Тёмная тема интерфейса',
    max_drawdown_pct: 'Максимальная допустимая просадка',
    dd_window_sec: 'Окно расчёта просадки в секундах',
    stop_duration_sec: 'Длительность остановки после просадки',
    cooldown_sec: 'Пауза после остановки в секундах',
    min_trades_for_dd: 'Минимум сделок для учёта просадки',
    symbol: 'Торговый инструмент',
    aggressive_take: 'Агрессивно забирать лучшие цены',
    capital_usage: 'Доля капитала в сделке',
  };

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
        enabled: [true],
        alpha: [0.85],
        latency_ms: [120],
        post_only_reject: [true],
        market_slippage_bps: [1.0],
        rest_base: [''],
        ws_base: [''],
      }),
      ui: this.fb.group({
        chart: [''],
        theme: [''],
      }),
      features: this.fb.group({
        risk_protections: [true],
        market_widget_feed: [true],
      }),
      risk: this.fb.group({
        max_drawdown_pct: [10],
        dd_window_sec: [24 * 3600],
        stop_duration_sec: [12 * 3600],
        cooldown_sec: [30 * 60],
        min_trades_for_dd: [0],
      }),
      history: this.fb.group({
        db_path: ['data/history.db'],
        retention_days: [365],
      }),
      scanner: this.fb.group({
        enabled: [false],
        quote: ['USDT'],
        min_price: [0.0001],
        min_vol_usdt_24h: [3_000_000],
        top_by_volume: [120],
        max_pairs: [60],
        min_spread_bps: [5],
        vol_bars: [0],
        score: this.fb.group({
          w_spread: [1.0],
          w_vol: [0.3],
        }),
        whitelist: [''],
        blacklist: [''],
      }),
      strategy: this.fb.group({
        name: ['market_maker'],
        market_maker: this.fb.group({
          symbol: ['BNBUSDT'],
          quote_size: [10],
          capital_usage: [1],
          min_spread_pct: [0],
          cancel_timeout: [10],
          reorder_interval: [1],
          loop_sleep: [0.2],
          depth_level: [5],
          maker_fee_pct: [0.1],
          taker_fee_pct: [0.1],
          econ: this.fb.group({
            min_net_pct: [0.1],
          }),
          post_only: [true],
          aggressive_take: [false],
          aggressive_bps: [0],
          inventory_target: [0.5],
          inventory_tolerance: [0.5],
          allow_short: [false],
          status_poll_interval: [2],
          stats_interval: [30],
          ws_timeout: [2],
          bootstrap_on_idle: [true],
          rest_bootstrap_interval: [3],
          plan_log_interval: [5],
          paper_cash: [1000],
        }),
        trend_follow: this.fb.group({}),
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
        if (cfg) {
          const copy: any = { ...cfg };
          if (copy.scanner) {
            copy.scanner = { ...copy.scanner };
            copy.scanner.whitelist = Array.isArray(copy.scanner.whitelist)
              ? copy.scanner.whitelist.join(', ')
              : copy.scanner.whitelist;
            copy.scanner.blacklist = Array.isArray(copy.scanner.blacklist)
              ? copy.scanner.blacklist.join(', ')
              : copy.scanner.blacklist;
          }
          this.cfgForm.patchValue(copy);
        }
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
    if (cfg.scanner) {
      const wl = cfg.scanner.whitelist as unknown;
      if (typeof wl === 'string') {
        cfg.scanner.whitelist = wl
          .split(',')
          .map((s) => s.trim())
          .filter((s) => s);
      }
      const bl = cfg.scanner.blacklist as unknown;
      if (typeof bl === 'string') {
        cfg.scanner.blacklist = bl
          .split(',')
          .map((s) => s.trim())
          .filter((s) => s);
      }
    }
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
        if (res?.cfg) {
          const copy: any = { ...res.cfg };
          if (copy.scanner) {
            copy.scanner = { ...copy.scanner };
            copy.scanner.whitelist = Array.isArray(copy.scanner.whitelist)
              ? copy.scanner.whitelist.join(', ')
              : copy.scanner.whitelist;
            copy.scanner.blacklist = Array.isArray(copy.scanner.blacklist)
              ? copy.scanner.blacklist.join(', ')
              : copy.scanner.blacklist;
          }
          this.cfgForm.patchValue(copy);
        }
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
        if (res?.cfg) {
          const copy: any = { ...res.cfg };
          if (copy.scanner) {
            copy.scanner = { ...copy.scanner };
            copy.scanner.whitelist = Array.isArray(copy.scanner.whitelist)
              ? copy.scanner.whitelist.join(', ')
              : copy.scanner.whitelist;
            copy.scanner.blacklist = Array.isArray(copy.scanner.blacklist)
              ? copy.scanner.blacklist.join(', ')
              : copy.scanner.blacklist;
          }
          this.cfgForm.patchValue(copy);
        }
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
