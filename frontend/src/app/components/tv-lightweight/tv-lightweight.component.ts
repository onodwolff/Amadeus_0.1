import { Component, ElementRef, OnDestroy, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { createChart, ColorType } from 'lightweight-charts';
import { ApiService } from '../../services/api.service';
import { WsService } from '../../services/ws.service';
import { firstValueFrom } from 'rxjs';

@Component({
    selector: 'app-tv-lightweight',
    standalone: true,
    imports: [CommonModule],
    templateUrl: './tv-lightweight.component.html',
    styleUrls: ['./tv-lightweight.component.css']
})
export class TvLightweightComponent implements OnInit, OnDestroy {
    private containerId = 'lwch-' + Math.random().toString(36).slice(2);
    private chart: any;
    private series: any;
    private ro?: ResizeObserver;

    symbol = 'BNBUSDT';
    theme: 'dark' | 'light' = 'dark';

    constructor(private el: ElementRef, private api: ApiService, private ws: WsService) {}

    async ngOnInit(): Promise<void> {
        await this.loadConfig();
        this.makeChart();
        this.bindWs();
    }

    ngOnDestroy(): void {
        try { this.ro?.disconnect(); } catch {}
        try { this.chart?.remove?.(); } catch {}
    }

    private async loadConfig() {
        try {
            const res: any = await firstValueFrom(this.api.getConfig());
            const cfg = (res && res.cfg) || {};
            const rawSym: string = (cfg.strategy && cfg.strategy.symbol) || 'BNBUSDT';
            this.symbol = (rawSym || 'BNBUSDT').toUpperCase();
            const ui = (cfg.ui || {});
            this.theme = (ui.theme === 'light' ? 'light' : 'dark');
        } catch {
            this.symbol = 'BNBUSDT';
            this.theme = 'dark';
        }
    }

    private makeChart() {
        const host: HTMLElement = this.el.nativeElement.querySelector('#' + this.containerId);
        if (!host) return;

        // Кидаем опции как any, чтобы не привязываться к минорным изменениям типов между версиями
        this.chart = createChart(host, {
            autoSize: true,
            layout: {
                background: { type: (ColorType as any)?.Solid ?? 'solid', color: this.theme === 'dark' ? '#0d0d0f' : '#ffffff' },
                textColor: this.theme === 'dark' ? '#d0d0d0' : '#222',
            },
            rightPriceScale: { borderVisible: false },
            timeScale: { borderVisible: false, rightOffset: 3, barSpacing: 8 },
            grid: {
                vertLines: { color: this.theme === 'dark' ? '#1f1f25' : '#eaeaea' },
                horzLines: { color: this.theme === 'dark' ? '#1f1f25' : '#eaeaea' },
            },
            crosshair: { mode: 1 },
        } as any);

        const opts: any = {
            lineWidth: 2,
            priceLineVisible: true,
            lastValueVisible: true,
            priceFormat: { type: 'price' },
        };

        // ✅ Совместимость v4/v5:
        // v4: chart.addAreaSeries(opts)
        // v5: chart.addSeries({ type: 'Area' }, opts)
        const anyChart: any = this.chart;
        if (typeof anyChart.addAreaSeries === 'function') {
            this.series = anyChart.addAreaSeries(opts);
        } else if (typeof anyChart.addSeries === 'function') {
            this.series = anyChart.addSeries({ type: 'Area' } as any, opts as any);
        } else {
            console.error('lightweight-charts: no addSeries/addAreaSeries available');
            return;
        }

        // стартовая точка
        const now = Math.floor(Date.now() / 1000);
        this.series.setData([{ time: now as any, value: 0 }]);

        // авто-ресайз
        this.ro = new ResizeObserver(() => this.chart.applyOptions({}));
        this.ro.observe(host);
    }

    private bindWs() {
        this.ws.connect();
        this.ws.messages$.subscribe((msg: any) => {
            if (!msg || typeof msg !== 'object' || msg.type !== 'market') return;

            const s = (msg.symbol || '').toString().toUpperCase();
            if (!s || (this.symbol && s !== this.symbol)) return;

            const last = Number(msg.lastPrice ?? msg.last ?? msg.c ?? msg.p);
            if (!isFinite(last)) return;

            const timeSec = Math.floor((Number(msg.ts) || Date.now()) / 1000);
            this.series?.update?.({ time: timeSec as any, value: last });
        });
    }

    get id() { return this.containerId; }
}
