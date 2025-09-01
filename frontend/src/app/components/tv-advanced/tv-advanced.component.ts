import { Component, ElementRef, OnDestroy, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../services/api.service';

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
export class TvAdvancedComponent implements OnInit, OnDestroy {
    private containerId = 'tv-advanced-' + Math.random().toString(36).slice(2);
    symbol = 'BINANCE:BTCUSDT';
    theme: 'dark' | 'light' = 'dark';
    private scriptEl?: HTMLScriptElement;
    private widget?: any;

    constructor(private el: ElementRef, private api: ApiService) {}

    async ngOnInit(): Promise<void> {
        await this.loadConfig();
        await this.ensureScriptLoaded();
        this.mountWidget();
    }

    ngOnDestroy(): void {
        try {
            if (this.widget && typeof this.widget.remove === 'function') {
                this.widget.remove();
            }
        } catch { /* noop */ }
        if (this.scriptEl && this.scriptEl.parentNode) {
            // tv.js можно оставить кэшированным; удаление не обязательно.
            // this.scriptEl.parentNode.removeChild(this.scriptEl);
        }
    }

    private async loadConfig() {
        try {
            const res: any = await this.api.getConfig().toPromise();
            const cfg = (res && res.cfg) || {};
            // пробуем вытащить символ из стратегии
            const rawSym: string = (cfg.strategy && cfg.strategy.symbol) || 'BTCUSDT';
            this.symbol = rawSym.includes(':') ? rawSym : `BINANCE:${rawSym}`;
            // тема из cfg.ui.theme ('dark'|'light'), по умолчанию dark
            const ui = (cfg.ui || {});
            this.theme = (ui.theme === 'light' ? 'light' : 'dark');
        } catch {
            this.symbol = 'BINANCE:BTCUSDT';
            this.theme = 'dark';
        }
    }

    private ensureScriptLoaded(): Promise<void> {
        return new Promise((resolve) => {
            if (window.TradingView) return resolve();
            const script = document.createElement('script');
            script.type = 'text/javascript';
            script.src = 'https://s3.tradingview.com/tv.js';
            script.onload = () => resolve();
            document.head.appendChild(script);
            this.scriptEl = script;
        });
    }

    private mountWidget() {
        const container = this.el.nativeElement.querySelector(`#${this.containerId}`);
        if (!container || !window.TradingView) return;

        // Документация Advanced Chart widget (tv.js) — конфиг через TradingView.widget(...)
        // https://www.tradingview.com/widget-docs/widgets/charts/advanced-chart/
        this.widget = new window.TradingView.widget({
            container_id: this.containerId,
            symbol: this.symbol,             // например BINANCE:BNBUSDT
            interval: '1',                   // 1m
            timezone: 'Etc/UTC',
            theme: this.theme,
            style: '1',
            locale: 'en',
            autosize: true,
            // доп. опции, часто полезные в скальпинге:
            hide_top_toolbar: false,
            hide_legend: false,
            hide_side_toolbar: false,
            allow_symbol_change: true,
            withdateranges: true,
            details: true,
            studies: ['Volume@tv-basic-study'],
            // НЕ указываем datafeed — виджет сам тянет рыночные данные TradingView (display-only). :contentReference[oaicite:2]{index=2}
            // Если в будущем понадобится локальный datafeed без зависимости от TV — см. Charting Library / Lightweight Charts. :contentReference[oaicite:3]{index=3}
        });
    }

    // Шаблон использует containerId
    get id() { return this.containerId; }
}
