import { Component, ElementRef, OnDestroy, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { WsService } from '../../services/ws.service';

// используем any для совместимости с разными версиями lightweight-charts (v4/v5)
import { createChart, ColorType } from 'lightweight-charts';

@Component({
    selector: 'app-equity-sparkline',
    standalone: true,
    imports: [CommonModule],
    templateUrl: './equity-sparkline.component.html',
    styleUrls: ['./equity-sparkline.component.css']
})
export class EquitySparklineComponent implements OnInit, OnDestroy {
    private id = 'eq-' + Math.random().toString(36).slice(2);
    private chart: any;
    private series: any;
    private ro?: ResizeObserver;

    points: Array<{ t: number; v: number }> = [];
    eqNow = 0;
    eqHigh = 0;
    eqLow = 0;
    ddPct = 0;     // текущий drawdown %
    ddMaxPct = 0;  // максимальный DD за сессию

    constructor(private el: ElementRef, private ws: WsService) {}

    ngOnInit(): void {
        this.makeChart();
        this.bindWs();
    }

    ngOnDestroy(): void {
        try { this.ro?.disconnect(); } catch {}
        try { this.chart?.remove?.(); } catch {}
    }

    private makeChart() {
        const host: HTMLElement = this.el.nativeElement.querySelector('#' + this.id);
        if (!host) return;

        this.chart = createChart(host, {
            autoSize: true,
            layout: {
                background: { type: (ColorType as any)?.Solid ?? 'solid', color: '#0d0d0f' },
                textColor: '#d0d0d0',
            },
            rightPriceScale: { borderVisible: false, visible: false },
            timeScale: { borderVisible: false, visible: false },
            grid: { vertLines: { color: '#111' }, horzLines: { color: '#111' } },
            crosshair: { mode: 0 },
        } as any);

        const opts: any = {
            lineWidth: 2,
            priceLineVisible: false,
            lastValueVisible: false,
            priceFormat: { type: 'price' },
            topColor: 'rgba(120, 200, 255, 0.15)',
            bottomColor: 'rgba(120, 200, 255, 0.02)',
        };

        // совместимо с v4/v5 API
        if (typeof this.chart.addAreaSeries === 'function') {
            this.series = this.chart.addAreaSeries(opts);
        } else if (typeof this.chart.addSeries === 'function') {
            this.series = this.chart.addSeries({ type: 'Area' } as any, opts as any);
        }

        this.series.setData([]);
        this.ro = new ResizeObserver(() => this.chart.applyOptions({}));
        this.ro.observe(host);
    }

    private bindWs() {
        this.ws.connect();
        this.ws.messages$.subscribe((msg: any) => {
            if (!msg || typeof msg !== 'object') return;

            // ловим либо 'equity', либо 'bank' c полем equity
            const t = String(msg.type || '');
            const val = t === 'equity' ? Number(msg.value ?? msg.equity)
                : t === 'bank'   ? Number(msg.equity ?? msg.value)
                    : NaN;
            if (!isFinite(val)) return;

            const ts = Math.floor((Number(msg.ts) || Date.now()) / 1000);
            this.points.push({ t: ts, v: val });
            if (this.points.length > 2000) this.points.shift();

            this.eqNow  = val;
            this.eqHigh = this.points.reduce((m, p) => Math.max(m, p.v), -Infinity);
            this.eqLow  = this.points.reduce((m, p) => Math.min(m, p.v),  Infinity);

            const peak = this.eqHigh || val;
            this.ddPct = peak ? (100 * (peak - val) / peak) : 0;

            const scan = this.points.reduce<{ peak:number; maxdd:number }>((acc, p) => {
                acc.peak = Math.max(acc.peak, p.v);
                const dd = acc.peak ? 100 * (acc.peak - p.v) / acc.peak : 0;
                acc.maxdd = Math.max(acc.maxdd, dd);
                return acc;
            }, { peak: 0, maxdd: 0 });
            this.ddMaxPct = scan.maxdd;

            this.series?.update?.({ time: ts as any, value: val });
        });
    }

    get containerId() { return this.id; }
}
