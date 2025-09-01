import { Component, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../services/api.service';
import { ScriptLoaderService } from '../../services/script-loader.service';

declare global {
    interface Window { TradingView?: any; }
}

@Component({
    selector: 'app-tv-advanced',
    standalone: true,
    imports: [CommonModule],
    templateUrl: './tv-advanced.component.html',
    styleUrls: ['./tv-advanced.component.css']
})
export class TvAdvancedComponent {
    containerId = 'tvw-' + Math.random().toString(36).slice(2);
    error = '';
    loading = true;

    private symbol = 'BNBUSDT';
    private theme: 'dark'|'light' = 'dark';

    constructor(
        private el: ElementRef,
        private api: ApiService,
        private loader: ScriptLoaderService,
    ) {}

    async ngOnInit() {
        await this.readConfig();
        this.initWidget();
    }

    private async readConfig() {
        try {
            const res: any = await this.api.getConfig().toPromise();
            const cfg = res?.cfg ?? res ?? {};
            const ui = cfg?.ui ?? {};
            const strat = cfg?.strategy ?? {};
            this.theme = (ui.theme === 'light' ? 'light' : 'dark');
            this.symbol = String(strat.symbol ?? 'BNBUSDT').toUpperCase();
        } catch {
            this.symbol = 'BNBUSDT';
            this.theme = 'dark';
        }
    }

    private async initWidget() {
        this.loading = true;
        this.error = '';

        // 1) грузим библиотеку виджета
        try {
            await Promise.race([
                this.loader.load('https://s3.tradingview.com/tv.js', 'tradingview_widget_js'),
                new Promise((_, rej) => setTimeout(() => rej(new Error('timeout loading tv.js')), 8000)),
            ]);
        } catch (e: any) {
            this.loading = false;
            this.error = 'Не удалось загрузить TradingView (возможна блокировка s3.tradingview.com).';
            return;
        }

        // 2) ждём появления TradingView в window
        const ok = await this.waitFor(() => !!window.TradingView, 8000);
        if (!ok) {
            this.loading = false;
            this.error = 'TradingView недоступен (window.TradingView не появился).';
            return;
        }

        // 3) создаём контейнер
        const host: HTMLElement = this.el.nativeElement.querySelector('#' + this.containerId);
        if (!host) { this.loading = false; this.error = 'Контейнер виджета не найден.'; return; }

        // 4) инициализируем Advanced Chart
        try {
            /* Документация: Advanced Real-Time Chart (виджет). Инициализация — new TradingView.widget({...}). */
            new window.TradingView.widget({
                container_id: this.containerId,
                symbol: this.mapSymbol(this.symbol),   // BINANCE:BNBUSDT
                interval: '60',
                theme: this.theme,
                style: '1',
                locale: 'ru',
                autosize: true,
                hide_top_toolbar: false,
                hide_legend: false,
                allow_symbol_change: true,
                save_image: false,
                studies: [],
            });
            this.loading = false;
        } catch (e: any) {
            this.loading = false;
            this.error = 'Ошибка инициализации TradingView.widget().';
        }
    }

    private mapSymbol(sym: string): string {
        // простое сопоставление для крипты на Binance в виджете TradingView
        return `BINANCE:${sym}`;
    }

    private async waitFor(cond: () => boolean, ms = 5000): Promise<boolean> {
        const t0 = Date.now();
        while (Date.now() - t0 < ms) {
            if (cond()) return true;
            await new Promise(r => setTimeout(r, 100));
        }
        return false;
    }
}
