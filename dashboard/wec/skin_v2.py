"""Skin "Monitoring v2": redesign dashboard Genis bergaya impeccable.style (Kinpaku).

Diterapkan di atas template yang sudah di-patch patch_template.py (ML + digital twin).
Semua CSS dikunci di bawah .wec-v2 supaya tidak bentrok dengan halaman Genis lama.
- Tema "paper" (default, terang) dan "instrument" (gelap arang), tombol di header, disimpan di browser
- Tipografi: Albert Sans (teks), Alumni Sans tipis (angka/judul), JetBrains Mono (label)
- Satu aksen emas (kinpaku) + patina; kartu datar bergaris tipis; tanpa emoji, tanpa glow/blur
- Warna gauge dan grafik ECharts mengikuti tema
"""

import re
import sys

EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿️‍]")

PALETTE_METHODS = r"""        wecPal() {
            const dark = this.timeThemeClass === 'theme-instrument';
            return dark
                ? { volt: '#7fd1cb', curr: '#4fb3ac', power: '#f2b530', wind: '#d9d9d9', windAlt: '#9a9a9a', track: 'rgba(255,255,255,0.10)' }
                : { volt: '#0f6560', curr: '#3a9d97', power: '#c8961f', wind: '#262626', windAlt: '#8a8a8a', track: 'rgba(17,17,17,0.08)' };
        },
        toggleTheme() {
            this.timeThemeClass = this.timeThemeClass === 'theme-instrument' ? 'theme-paper' : 'theme-instrument';
            try { window.localStorage.setItem('wec-v2-theme', this.timeThemeClass); } catch (e) { /* opsional */ }
            if (this.chartsReady) { this.$nextTick(() => { try { this.initChartOptions(); this.refreshAllCharts(); } catch (e) { /* grafik dimuat ulang saat data berikutnya */ } }); }
        },
        initChartOptions() {
            const p = this.wecPal();
            const textColor = this.timeThemeClass === 'theme-instrument' ? '#a6a6a6' : '#5e5e5e';
            this.setGauge(this.charts.g_volt, p.volt, 300, textColor);
            this.setGauge(this.charts.g_curr, p.curr, 20, textColor);
            this.setGauge(this.charts.g_power, p.power, 1000, textColor);
            this.setGauge(this.charts.g_wind, p.wind, 25, textColor);
            this.setLineChart(this.charts.l_volt, p.volt, 'V');
            this.setLineChart(this.charts.l_curr, p.curr, 'A');
            this.setLineChart(this.charts.l_wind, p.wind, 'm/s', true);
            this.setLineChart(this.charts.l_power, p.power, 'W');
        },
        watchWecSize() {
            const el = this.$el && this.$el.nodeType === 1 ? this.$el : document.querySelector('.wec-v2');
            const redraw = () => {
                clearTimeout(this._wecRT);
                this._wecRT = setTimeout(() => {
                    Object.values(this.charts || {}).forEach(c => { try { c && c.resize && c.resize(); } catch (e) { /* belum siap */ } });
                    if (this.resizeTwin) this.resizeTwin();
                }, 120);
            };
            try { this._wecRO = new ResizeObserver(redraw); if (el) this._wecRO.observe(el); } catch (e) { /* browser lama: pakai window resize */ }
            try { document.fonts.ready.then(redraw); } catch (e) { /* opsional */ }
        },
        loadWecFonts() {
            if (document.getElementById('wec-v2-fonts')) return;
            const l = document.createElement('link');
            l.id = 'wec-v2-fonts'; l.rel = 'stylesheet';
            l.href = 'https://fonts.googleapis.com/css2?family=Albert+Sans:wght@400;500;600;700&family=Alumni+Sans:wght@200..600&family=JetBrains+Mono:wght@400;500&display=swap';
            document.head.appendChild(l);
        },
"""

CSS = r"""
    /* =================== Monitoring v2 · gaya Kinpaku (impeccable.style) =================== */
    .wec-v2.theme-paper {
        --k-paper: #f7f7f7; --k-raised: #fdfdfd; --k-deep: #efefef; --k-gray: #e6e6e6;
        --k-ink: #111111; --k-text: #222222; --k-muted: #5e5e5e; --k-faint: #6b6b6b;
        --k-rule: rgba(17,17,17,0.08); --k-edge: rgba(17,17,17,0.28);
        --k-gold: #f2b530; --k-gold-rich: #c8961f; --k-patina: #3a9d97; --k-patina-deep: #0f6560; --k-vermilion: #b5452a;
        --k-lift: 0 1px 1px rgba(17,17,17,.05), 0 2px 3px rgba(17,17,17,.04), 0 6px 12px rgba(17,17,17,.05);
        --k-lift-2: 0 1px 1px rgba(17,17,17,.04), 0 3px 5px rgba(17,17,17,.05), 0 12px 20px rgba(17,17,17,.06);
        --bg-gradient: var(--k-paper); --card-bg: var(--k-raised); --card-bg-inner: var(--k-paper);
        --card-border: var(--k-rule); --card-border-hover: var(--k-edge); --card-shadow: var(--k-lift); --card-shadow-hover: var(--k-lift-2);
        --title-color: var(--k-ink); --text-main: var(--k-text); --text-muted: var(--k-muted);
        --accent-blue: var(--k-patina-deep); --accent-turquoise: var(--k-patina); --accent-green: var(--k-patina-deep); --accent-yellow: var(--k-gold-rich);
    }
    .wec-v2.theme-instrument {
        --k-paper: #1a1a1a; --k-raised: #242424; --k-deep: #2e2e2e; --k-gray: #383838;
        --k-ink: #f2f2f2; --k-text: #e6e6e6; --k-muted: #a6a6a6; --k-faint: #8c8c8c;
        --k-rule: rgba(255,255,255,0.10); --k-edge: rgba(255,255,255,0.30);
        --k-gold: #f2b530; --k-gold-rich: #e0a92a; --k-patina: #4fb3ac; --k-patina-deep: #7fd1cb; --k-vermilion: #e07a5f;
        --k-lift: 0 1px 1px rgba(0,0,0,.4), 0 6px 14px rgba(0,0,0,.25);
        --k-lift-2: 0 1px 1px rgba(0,0,0,.4), 0 12px 24px rgba(0,0,0,.35);
        --bg-gradient: var(--k-paper); --card-bg: var(--k-raised); --card-bg-inner: var(--k-deep);
        --card-border: var(--k-rule); --card-border-hover: var(--k-edge); --card-shadow: var(--k-lift); --card-shadow-hover: var(--k-lift-2);
        --title-color: var(--k-ink); --text-main: var(--k-text); --text-muted: var(--k-muted);
        --accent-blue: var(--k-patina-deep); --accent-turquoise: var(--k-patina); --accent-green: var(--k-patina-deep); --accent-yellow: var(--k-gold);
    }
    body:has(.wec-v2), body:has(.wec-v2) .nr-dashboard-theme, body:has(.wec-v2) .v-main { background: var(--k-paper, #f7f7f7) !important; }
    body:has(.wec-v2) .v-app-bar, body:has(.wec-v2) header.v-toolbar, body:has(.wec-v2) .v-navigation-drawer { display: none !important; }
    body:has(.wec-v2) .v-main { padding-top: 0 !important; --v-layout-top: 0px !important; }
    body:has(.wec-v2.theme-instrument), body:has(.wec-v2.theme-instrument) .nr-dashboard-theme, body:has(.wec-v2.theme-instrument) .v-main { background: #1a1a1a !important; }
    .wec-v2 {
        --k-font: "Albert Sans", "Avenir Next", "Helvetica Neue", Arial, system-ui, sans-serif;
        --k-display: "Alumni Sans", "Albert Sans", Arial, sans-serif;
        --k-mono: "JetBrains Mono", ui-monospace, Menlo, Consolas, monospace;
        background: var(--k-paper); color: var(--k-text); font-family: var(--k-font);
        padding: clamp(16px, 2.5vw, 40px); letter-spacing: 0;
        /* penuh jendela, menutupi bar atas Node-RED; scroll di dalam */
        position: fixed; inset: 0; z-index: 2000; width: auto; min-width: 0; min-height: 0; max-width: none; margin: 0;
        overflow-x: hidden; overflow-y: auto; overscroll-behavior: contain; -webkit-overflow-scrolling: touch;
    }
    /* kartu grid boleh menyusut; grafik digambar ulang oleh ResizeObserver */
    .wec-v2 [class*="grid"] > *, .wec-v2 .wec-two > *, .wec-v2 .wec-twin-wrap > *, .wec-v2 .wec-twin-side > *, .wec-v2 .card, .wec-v2 .feature-metric { min-width: 0; }
    .wec-v2 .gauge-container, .wec-v2 .graph-container, .wec-v2 .map-container { width: 100%; overflow: hidden; }
    .wec-v2 .header-actions { display: flex; flex-wrap: wrap; gap: 8px; }
    .wec-v2::before {
        content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 0; opacity: .035;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
    }
    /* header */
    .wec-v2 .header-section { padding-bottom: 20px; margin-bottom: 8px; border-bottom: 1px solid var(--k-rule); align-items: flex-end; }
    .wec-v2 h2.dash-title { font-family: var(--k-display); font-weight: 200; font-size: clamp(2.4rem, 4.4vw, 3.6rem); line-height: 1; letter-spacing: 0; color: var(--k-ink); text-transform: none; margin: 0; }
    .wec-v2 h2.dash-title span { color: var(--k-gold-rich) !important; }
    .wec-v2 .dash-subtitle { font-family: var(--k-mono); font-size: .6875rem; letter-spacing: .14em; text-transform: uppercase; color: var(--k-muted); margin-top: 10px; }
    .wec-v2 .turbine-selector { background: var(--k-deep); border: 1px solid var(--k-rule); border-radius: 999px; padding: 3px; box-shadow: inset 0 1px 2px rgba(0,0,0,.08); }
    .wec-v2 .t-btn { font-family: var(--k-font); font-weight: 600; font-size: .8125rem; border-radius: 999px; padding: 8px 16px; background: transparent; color: var(--k-muted); border: 0; box-shadow: none; }
    .wec-v2 .t-btn.active { background: var(--k-raised); color: var(--k-ink); box-shadow: var(--k-lift); }
    .wec-v2 .status-badge, .wec-v2 .feature-status, .wec-v2 .badge {
        font-family: var(--k-mono) !important; font-size: .6875rem; letter-spacing: .12em; text-transform: uppercase;
        color: var(--k-muted) !important; background: var(--k-raised); border: 1px solid var(--k-rule) !important; border-radius: 3px; box-shadow: none; }
    .wec-v2 .status-dot { width: 7px; height: 7px; box-shadow: 0 0 0 1px rgba(0,0,0,.12), 0 0 4px rgba(242,181,48,.6); background: var(--k-gold) !important; }
    .wec-v2 .status-red { color: var(--k-vermilion) !important; }
    .wec-theme-btn { font-family: var(--k-mono); font-size: .6875rem; letter-spacing: .12em; text-transform: uppercase; min-height: 32px; padding: 6px 12px;
        border-radius: 3px; border: 1px solid var(--k-rule); background: var(--k-ink); color: var(--k-paper); cursor: pointer; }
    /* panel */
    .wec-v2 .glass-panel, .wec-v2 .card {
        background: var(--k-raised) !important; border: 1px solid var(--k-rule) !important; border-radius: 8px !important;
        box-shadow: var(--k-lift) !important; backdrop-filter: none !important; -webkit-backdrop-filter: none !important; }
    .wec-v2 .glass-panel:hover, .wec-v2 .card:hover { border-color: var(--k-edge) !important; transform: none !important; box-shadow: var(--k-lift-2) !important; }
    .wec-v2 .voltage-active, .wec-v2 .current-active, .wec-v2 .power-active, .wec-v2 .wind-active { box-shadow: var(--k-lift) !important; }
    .wec-v2 .glass-inner, .wec-v2 .feature-metric, .wec-v2 .compute-device, .wec-v2 .kpi-card, .wec-v2 .forecast-card, .wec-v2 .wec-node, .wec-v2 .wec-sliders {
        background: var(--k-paper) !important; border: 1px solid var(--k-rule) !important; border-radius: 3px !important; box-shadow: none !important; }
    /* label = mono kecil */
    .wec-v2 .card-header, .wec-v2 .param-label, .wec-v2 .feature-metric > span, .wec-v2 .kpi-label, .wec-v2 .log-table th,
    .wec-v2 .wec-node, .wec-v2 .sensor-details dt, .wec-v2 .prediction-details, .wec-v2 .stream-controls label, .wec-v2 .wec-sliders label, .wec-v2 .f-time {
        font-family: var(--k-mono) !important; font-size: .6875rem !important; letter-spacing: .12em; text-transform: uppercase; color: var(--k-muted) !important; font-weight: 500; }
    .wec-v2 .feature-heading h3, .wec-v2 .feature-heading h4, .wec-v2 .log-title, .wec-v2 .section-title, .wec-v2 h3 {
        font-family: var(--k-font); font-weight: 600; font-size: 1.0625rem; line-height: 1.35; color: var(--k-ink) !important; letter-spacing: 0; text-transform: none; }
    .wec-v2 .feature-note, .wec-v2 .wec-sub { color: var(--k-muted); font-size: .8125rem; line-height: 1.6; }
    /* angka = display tipis */
    .wec-v2 .energy-value, .wec-v2 .env-value, .wec-v2 .kpi-value, .wec-v2 .feature-metric strong, .wec-v2 .compute-watts, .wec-v2 .f-speed, .wec-v2 .wec-node b {
        font-family: var(--k-display) !important; font-weight: 300 !important; color: var(--k-ink) !important; letter-spacing: 0; font-variant-numeric: tabular-nums; text-shadow: none !important; }
    .wec-v2 .feature-metric strong, .wec-v2 .compute-watts { font-size: 2.6rem !important; line-height: 1; }
    .wec-v2 .energy-value { font-size: 3.6rem !important; }
    .wec-v2 .env-value { font-size: 2.4rem !important; }
    .wec-v2 .wec-node b { font-size: 1.4rem !important; }
    .wec-v2 .feature-metric small, .wec-v2 .env-unit, .wec-v2 .energy-unit, .wec-v2 .compute-watts small { font-family: var(--k-mono); font-size: .6875rem; letter-spacing: .1em; color: var(--k-muted) !important; }
    .wec-v2 .param-icon, .wec-v2 .kpi-icon, .wec-v2 .f-icon, .wec-v2 .icon, .wec-v2 .turbine-icon { display: none !important; }
    .wec-v2 .savings-badge { font-family: var(--k-mono); font-size: .6875rem; letter-spacing: .1em; background: transparent !important; border: 1px solid var(--k-rule) !important; color: var(--k-muted) !important; border-radius: 3px; }
    /* tombol */
    .wec-v2 .glass-btn, .wec-v2 .action-primary { font-family: var(--k-font); font-weight: 600; font-size: .8125rem; background: var(--k-ink) !important; color: var(--k-paper) !important;
        border: 0 !important; border-radius: 3px !important; box-shadow: none !important; min-height: 36px; }
    .wec-v2 .glass-btn:disabled, .wec-v2 .action-primary:disabled { opacity: .45; }
    .wec-v2 .action-soft, .wec-v2 .glass-select, .wec-v2 .stream-controls input, .wec-v2 .stream-controls select {
        background: var(--k-raised) !important; color: var(--k-text) !important; border: 1px solid var(--k-rule) !important; border-radius: 3px !important; box-shadow: none !important; }
    .wec-v2 .wec-toggle { border-radius: 999px; background: var(--k-deep); border: 1px solid var(--k-rule); padding: 3px; }
    .wec-v2 .wec-toggle button { border-radius: 999px; min-height: 30px; font-size: .8125rem; color: var(--k-muted); }
    .wec-v2 .wec-toggle button.on { background: var(--k-raised); color: var(--k-ink); box-shadow: var(--k-lift); }
    /* tabel, garis, isian */
    .wec-v2 .log-table th { background: var(--k-paper) !important; border-bottom: 1px solid var(--k-rule) !important; }
    .wec-v2 .log-table td { border-bottom: 1px solid var(--k-rule) !important; color: var(--k-text) !important; font-variant-numeric: tabular-nums; }
    .wec-v2 .log-table td[style] { color: var(--k-text) !important; }
    .wec-v2 .section-divider { background: transparent !important; border-bottom: 1px solid var(--k-rule) !important; height: auto !important; padding-bottom: 12px; margin-top: 48px !important; }
    .wec-v2 .section-divider h3.dash-title { font-family: var(--k-display) !important; font-weight: 300 !important; font-size: clamp(1.8rem, 3vw, 2.6rem) !important;
        letter-spacing: 0; text-transform: none; color: var(--k-ink) !important; padding-left: 0 !important; }
    .wec-v2 .compute-bar, .wec-v2 .wec-soc, .wec-v2 .wec-ratio-track, .wec-v2 .progress-bg, .wec-v2 .bar-full { background: var(--k-deep) !important; border: 0 !important;
        box-shadow: inset 0 1px 3px rgba(17,17,17,.16), inset 0 -1px 0 rgba(255,255,255,.7) !important; }
    .wec-v2 .wec-soc-fill { background: var(--k-patina) !important; }
    .wec-v2 .wec-ratio-ok { background: color-mix(in oklab, var(--k-patina) 22%, transparent) !important; }
    .wec-v2 .wec-ratio-dot { background: var(--k-ink); }
    .wec-v2 .wec-flow i.run { background: repeating-linear-gradient(90deg, var(--k-gold-rich) 0 6px, transparent 6px 12px) !important; background-size: 24px 2px !important; }
    .wec-v2 .wec-chip.wec-ok { color: var(--k-patina-deep) !important; }
    .wec-v2 .wec-chip.wec-low { color: var(--k-gold-rich) !important; }
    .wec-v2 .wec-chip.wec-high { color: var(--k-vermilion) !important; }
    .wec-v2 .comparison-result { border-left: 0; border-top: 1px solid var(--k-rule); background: transparent; padding-left: 0; }
    .wec-v2 .wec-twin { background: linear-gradient(180deg, var(--k-raised), var(--k-deep)) !important; border-radius: 3px; }
    .wec-v2 .map-container, .wec-v2 .gauge-container, .wec-v2 .graph-container { border-radius: 3px; }
    .wec-v2 .formula-box { background: var(--k-paper) !important; border: 1px solid var(--k-rule) !important; border-left-width: 1px !important; font-family: var(--k-mono); }
    .wec-v2 .project-footer { border-top: 1px solid var(--k-rule); color: var(--k-muted); font-family: var(--k-mono); font-size: .6875rem; letter-spacing: .12em; }
    .wec-v2 .glass-toast { background: var(--k-ink) !important; color: var(--k-paper) !important; border: 0 !important; border-radius: 3px !important; backdrop-filter: none !important; }
    /* perbandingan real vs digital twin */
    .wec-v2 .wec-compare { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; align-items: stretch; }
    .wec-v2 .wec-compare > section { margin: 0 !important; display: flex; flex-direction: column; }
    .wec-v2 .wec-eyebrow { display: block; font-family: var(--k-mono); font-size: .6875rem; letter-spacing: .14em; text-transform: uppercase; color: var(--k-gold-rich); margin-bottom: 4px; }
    .wec-v2 .wec-compare .stream-frame { max-width: none; aspect-ratio: 4 / 3; border-radius: 3px; background: var(--k-deep); }
    .wec-v2 .wec-compare .wec-twin-wrap { grid-template-columns: minmax(0, 1fr); }
    .wec-v2 .wec-compare .wec-twin { height: auto; aspect-ratio: 4 / 3; }
    .wec-v2 .wec-compare .wec-twin-side { grid-template-columns: repeat(4, minmax(0, 1fr)); }
    .wec-v2 .wec-compare .wec-twin-side .wec-sliders { grid-column: 1 / -1; }
    .wec-v2 .wec-compare .wec-twin-side .feature-metric strong { font-size: 1.6rem !important; }
    .wec-v2 .wec-compare .stream-controls { margin-top: 12px; }
    .wec-v2 .wec-real-live { color: var(--k-text); gap: 18px; }
    .wec-v2 .wec-real-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px 28px; width: min(100%, 420px); }
    .wec-v2 .wec-real-grid > div { display: grid; grid-template-columns: auto 1fr; align-items: baseline; column-gap: 6px; text-align: left; border-top: 1px solid var(--k-rule); padding-top: 8px; }
    .wec-v2 .wec-real-grid span { grid-column: 1 / -1; font-family: var(--k-mono); font-size: .6875rem; letter-spacing: .12em; text-transform: uppercase; color: var(--k-muted) !important; }
    .wec-v2 .wec-real-grid b { font-family: var(--k-display); font-weight: 300; font-size: 2.6rem; line-height: 1; color: var(--k-ink); font-variant-numeric: tabular-nums; }
    .wec-v2 .wec-real-grid small { font-family: var(--k-mono); font-size: .6875rem; color: var(--k-muted); }
    .wec-v2 .wec-real-hint { font-size: .8125rem; color: var(--k-muted) !important; }
    .wec-v2 .wec-real-warn { font-family: var(--k-mono); font-size: .6875rem; letter-spacing: .12em; text-transform: uppercase; color: var(--k-vermilion) !important; }
    @media (max-width: 1024px) {
        .wec-v2 .wec-compare { grid-template-columns: minmax(0, 1fr); }
    }
    @media (min-width: 1700px) {
        .wec-v2 .grid-params { grid-template-columns: repeat(5, minmax(0, 1fr)); }
    }
    @media (max-width: 640px) {
        .wec-v2 { padding: 16px 16px 32px; }
        .wec-v2 .header-section { flex-direction: column; align-items: stretch; gap: 14px; padding-bottom: 14px; }
        .wec-v2 .header-section > div:first-child { gap: 12px !important; }
        .wec-v2 h2.dash-title { font-size: 2.2rem; }
        .wec-v2 .turbine-selector { align-self: flex-start; }
        .wec-v2 .dashboard-grid { grid-template-columns: minmax(0, 1fr) !important; gap: 12px; }
        .wec-v2 .dashboard-grid > * { grid-column: 1 / -1 !important; }
        .wec-v2 .grid-gauges, .wec-v2 .grid-params { grid-template-columns: repeat(2, minmax(0, 1fr)) !important; }
        .wec-v2 .grid-gauges > *, .wec-v2 .grid-params > * { grid-column: span 1 !important; }
        .wec-v2 .grid-gauges > :last-child:nth-child(odd), .wec-v2 .grid-params > :last-child:nth-child(odd) { grid-column: 1 / -1 !important; }
        .wec-v2 .grid-gauges .card, .wec-v2 .grid-params .card { padding: 12px !important; }
        .wec-v2 .gauge-container { height: 120px !important; }
        .wec-v2 .graph-container { height: 220px !important; }
        .wec-v2 .env-value { font-size: 1.9rem !important; }
        .wec-v2 .energy-value { font-size: 2.8rem !important; }
        .wec-v2 .card-header { letter-spacing: .08em; }
        .wec-v2 .wec-metrics, .wec-v2 .wec-gauge-row, .wec-v2 .wec-twin-side { grid-template-columns: repeat(2, minmax(0, 1fr)) !important; }
        .wec-v2 .wec-two { grid-template-columns: minmax(0, 1fr) !important; }
        .wec-v2 .feature-metric { padding: 10px 12px !important; }
        .wec-v2 .feature-metric strong, .wec-v2 .compute-watts { font-size: 1.8rem !important; }
        .wec-v2 .wec-twin-side .feature-metric strong { font-size: 1.5rem !important; }
        .wec-v2 .section-divider { margin-top: 32px !important; }
        .wec-v2 .table-responsive { overflow-x: auto; }
        .wec-v2 .wec-compare .wec-twin-side { grid-template-columns: repeat(2, minmax(0, 1fr)) !important; }
        .wec-v2 .wec-real-grid b { font-size: 2rem; }
    }
"""


def compare_layout(s):
    """CCTV (real) dan digital twin berdampingan: desktop 2 kolom, HP atas-bawah."""
    a = s.index("        <!-- CCTV hanya dimuat atas permintaan")
    b = s.index("        </section>\n", a) + len("        </section>\n")
    cctv = s[a:b]
    c = s.index('        <section ref="twinSection"')
    d = s.index("        </section>\n", c) + len("        </section>\n")
    twin = s[c:d]
    assert b <= c, "CCTV diharapkan sebelum twin"
    ph = '<div v-else class="stream-placeholder"><strong>Live CCTV siap dikonfigurasi</strong><span>Masukkan alamat pemutar, lalu klik Mulai. Video tidak dimuat otomatis.</span></div>'
    assert cctv.count(ph) == 1, "placeholder CCTV berubah"
    cctv = cctv.replace(ph, """<div v-else class="stream-placeholder wec-real-live">
                    <span class="wec-eyebrow">Kamera mati · data sensor live</span>
                    <div class="wec-real-grid">
                        <div><span>Angin</span><b>{{ displayMetric(wec.live && wec.live.ws, 2) }}</b><small>m/s</small></div>
                        <div><span>Daya</span><b>{{ displayMetric(wec.live && wec.live.p, 1) }}</b><small>W</small></div>
                        <div><span>Arah</span><b>{{ displayMetric(wec.live && wec.live.wd, 0) }}</b><small>°</small></div>
                        <div><span>Tegangan</span><b>{{ displayMetric(wec.live && wec.live.v, 1) }}</b><small>V</small></div>
                    </div>
                    <span v-if="wec.live && wec.live.pzem === false" class="wec-real-hint wec-real-warn">PZEM tidak merespons · data listrik kosong</span>
                    <span class="wec-real-hint">Masukkan alamat pemutar di bawah, lalu klik Mulai untuk video.</span></div>""")
    cctv = cctv.replace('<h3 id="streamTitle">', '<span class="wec-eyebrow">Real</span><h3 id="streamTitle">', 1)
    twin = twin.replace('<h3 id="twinTitle">', '<span class="wec-eyebrow">Digital twin</span><h3 id="twinTitle">', 1)
    wrap = ('        <!-- Perbandingan real (CCTV) vs digital twin -->\n'
            '        <div class="wec-compare mt-3 relative-z">\n' + cctv + twin + '        </div>\n')
    return s[:a] + wrap + s[b:c] + s[d:]


def skin(src):
    s = compare_layout(src)
    def rep(a, b, label, count=1):
        nonlocal s
        assert s.count(a) == count, f"anchor '{label}' ditemukan {s.count(a)} kali"
        s = s.replace(a, b)
    rep('<div class="dash-container" :class="timeThemeClass">', '<div class="dash-container wec-v2" :class="timeThemeClass">', "root")
    rep("MONITORING TURBIN\n", "Monitoring Turbin\n", "judul")
    rep("CITA ITB • 2026", "CITA ITB · Wind Edge Chip · v2", "subjudul")
    t_end0 = s.index("<script>")
    head = re.sub(r"ANALISIS PERFORMA\s+SISTEM", "Analisis performa sistem", s[:t_end0])
    head = re.sub(r"SPESIFIKASI\s+&amp;\s+TEORI\s+SISTEM|SPESIFIKASI\s+&\s+TEORI\s+SISTEM", "Spesifikasi dan teori sistem", head)
    s = head + s[t_end0:]
    rep('            <div class="header-actions">\n',
        '            <div class="header-actions">\n                <button type="button" class="wec-theme-btn" @click="toggleTheme">{{ timeThemeClass === \'theme-instrument\' ? \'Terang\' : \'Gelap\' }}</button>\n',
        "header-actions")
    # tema: pilihan pengguna, bukan jam
    a = s.index("        updateTimeTheme() {")
    b = s.index("        },", a) + len("        },")
    s = s[:a] + """        updateTimeTheme() {
            let t = 'theme-paper';
            try { t = window.localStorage.getItem('wec-v2-theme') || 'theme-paper'; } catch (e) { /* opsional */ }
            if (t !== 'theme-paper' && t !== 'theme-instrument') t = 'theme-paper';
            this.timeThemeClass = t;
        },""" + s[b:]
    rep("timeThemeClass: 'theme-day'", "timeThemeClass: 'theme-paper'", "data tema")
    rep("        this.updateTimeTheme(); this.themeTimer = setInterval(this.updateTimeTheme, 60000);\n",
        "        this.loadWecFonts(); this.updateTimeTheme();\n", "mounted tema")
    # warna grafik ikut tema
    block_start = s.index("                    const textColor = '#64748b';")
    block_end = s.index("this.setLineChart(this.charts.l_power, '#fbbf24', 'W');", block_start) + len("this.setLineChart(this.charts.l_power, '#fbbf24', 'W');")
    s = s[:block_start] + "                    this.initChartOptions();" + s[block_end:]
    rep("lineStyle: { color: '#34d399', width: 3 }, data: [] }, ", "lineStyle: { color: this.wecPal().wind, width: 2 }, data: [] }, ", "garis arduino")
    rep("lineStyle: { color: '#818cf8', width: 3, type: 'dashed' }, data: [] } ", "lineStyle: { color: this.wecPal().windAlt, width: 2, type: 'dashed' }, data: [] } ", "garis stasiun")
    rep("itemStyle: { color: '#38bdf8', opacity: 0.8 } }]", "itemStyle: { color: this.wecPal().power, opacity: 0.6 } }]", "scatter")
    rep("detail: { fontSize: 22, color: 'auto', fontFamily: 'Arial', fontWeight: 'bold', formatter: '{value}', offsetCenter: [0, '35%'] }",
        "detail: { fontSize: 30, color: (this.timeThemeClass === 'theme-instrument' ? '#f2f2f2' : '#111111'), fontFamily: 'Alumni Sans, Albert Sans, sans-serif', fontWeight: 300, formatter: '{value}', offsetCenter: [0, '35%'] }", "gauge font")
    rep("axisLine: { lineStyle: { width: 12, color: [[1, 'rgba(150,150,150,0.15)']] } }", "axisLine: { lineStyle: { width: 10, color: [[1, this.wecPal().track]] } }", "gauge track")
    rep("pointer: { show: true, itemStyle: { color: 'auto' }, width: 4, length: '60%' }",
        "pointer: { show: true, itemStyle: { color: (this.timeThemeClass === 'theme-instrument' ? '#f2f2f2' : '#111111') }, width: 3, length: '55%' }", "gauge pointer")
    rep("progress: { show: true, width: 12, itemStyle: { color: color } }", "progress: { show: true, width: 10, itemStyle: { color: color } }", "gauge progress")
    rep("    methods: {\n", "    methods: {\n" + PALETTE_METHODS, "methods")
    rep("        this.loadWecFonts(); this.updateTimeTheme();\n",
        "        this.loadWecFonts(); this.updateTimeTheme(); this.$nextTick(this.watchWecSize);\n", "mounted ukuran")
    rep("    unmounted() { this.cleanupDashboard(); }", "    unmounted() { if (this._wecRO) this._wecRO.disconnect(); this.cleanupDashboard(); }", "unmounted")
    # emoji hanya dihapus dari markup (bukan dari string JS seperti ikon toast)
    t_end = s.index("<script>")
    s = EMOJI.sub("", s[:t_end]) + s[t_end:]
    i = s.rindex("</style>")
    s = s[:i] + CSS + s[i:]
    return s


if __name__ == "__main__":
    src = open(sys.argv[1]).read()
    out = skin(src)
    open(sys.argv[2], "w").write(out)
    print(f"skin v2: {len(src)} -> {len(out)} karakter")
