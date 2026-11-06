"""Skin "Hackathon" (/dashboard/hackathon): dashboard v2 dengan gaya cloaked.com.

Dibangun di atas skin_v2.skin(patch_template.patch(template Genis)), lalu:
- bar pengumuman gelap + hero (judul serif besar, angka live, pil "Prediksi 1 jam" beraksen oranye)
- tiga fitur ML dipindah tepat setelah hero, di dalam pita gelap (seperti seksi "Data parasites" di cloaked.com)
- token gaya cloaked.com: krem #FBF8EF, tinta #130F02, coklat gelap #1C180B, aksen #FF550C,
  kartu radius 32px, tombol pil, garis tipis vertikal di tepi isi
- huruf: Newsreader (pengganti Simula Book, serif judul + angka) dan Hanken Grotesk (pengganti STK Bureau Sans)
- tema terang (krem, bawaan) dan gelap (coklat malam), disimpan di browser (wec-hk-theme)
Semua CSS dikunci di bawah .wec-v2.wec-hk.
"""

import sys

import patch_template
import skin_v2
from power_panel import patch_current_panel
from comparison_panel import patch_comparison
from history_panel import patch_history_panel
from twin_presentation import patch_twin_presentation
from branding_panel import patch_branding

ANNOUNCE = """        <div class="hk-announce relative-z">DeepTech for Smart-X Hackathon 2026 · <b>Tim Chitato</b> · data live dari atap Gedung CRIMSE ITB</div>
"""

HERO = r"""
        <!-- Hackathon: bar pengumuman + hero bergaya cloaked.com -->
        <section class="hk-hero relative-z" aria-labelledby="hkTitle">
            <div class="hk-hero-copy">
                <h1 id="hkTitle" class="hk-h1">Prediksi daya turbin, <em>langsung di turbin.</em></h1>
                <p class="hk-lead-strong">Satu jam ke depan, diperbarui setiap menit.</p>
                <p class="hk-lead">MLP INT8 yang identik bit demi bit dengan akselerator FPGA rancangan tim. Tetap memprediksi saat sensor daya diam, dan tahu kapan baterai perlu dibantu PLN.</p>
                <a class="hk-pill-input" href="#hk-ml" @click.prevent="hkScroll('hk-ml')">
                    <span class="hk-pill-dot" :class="{ 'hk-pill-dot-off': !wecForecast }"></span>
                    <span class="hk-pill-label">Prediksi 1 jam</span>
                    <b>{{ wecForecast ? displayMetric(wecForecast.power_w, 1) + ' W' : '—' }}</b>
                    <i class="hk-pill-go" aria-hidden="true">→</i>
                </a>
                <p class="hk-fine">{{ wecForecast ? (wecRingkas || 'Mode normal · daya terukur PZEM') : (wec.ml && wec.ml.alasan ? 'Belum ada prediksi: ' + wec.ml.alasan : 'Menyambungkan ke mesin ML…') }}</p>
            </div>
            <div class="hk-hero-card">
                <div class="hk-hero-stats">
                    <div><span>Daya sekarang</span><b>{{ displayMetric(wec.live && wec.live.p, 1) }}<small>W</small></b></div>
                    <div><span>Angin stasiun</span><b>{{ displayMetric(wec.live && wec.live.ws, 2) }}<small>m/s</small></b></div>
                    <div><span>Energi 1 jam</span><b>{{ wecForecast ? displayMetric(wecForecast.power_w, 0) : '—' }}<small>Wh</small></b></div>
                    <div><span>SoC baterai</span><b>{{ wecBattery ? displayMetric(wecBattery.soc, 0) : '—' }}<small>%</small></b></div>
                </div>
                <div class="hk-glass">
                    <span class="hk-glass-title">Status turbin</span>
                    <div class="hk-glass-row"><b :class="'hk-st-' + wecStatusKey">{{ wecStatus ? wecStatus.label : 'Menunggu data' }}</b>
                        <span v-if="wecStatus && wecStatus.ratio !== null">rasio {{ displayMetric(wecStatus.ratio, 2) }}</span></div>
                    <span class="hk-glass-sub" v-if="wec.live && wec.live.pzem === false">PZEM tidak merespons · prediksi memakai daya dari angin</span>
                    <span class="hk-glass-sub" v-else>Daya aktual dibanding daya wajar untuk angin saat ini</span>
                    <span class="hk-glass-sub hk-chip" :class="{ 'hk-chip-on': wecFpga }">{{ wecFpga ? (wecFpga.sumber === 'simulasi' ? 'Chip: simulasi golden model' : 'Chip: Tang Nano 4K aktif') + ' · ' + wecFpga.cycles + ' siklus' : 'Chip: FPGA belum tersambung, CPU bit-exact' }}</span>
                </div>
            </div>
        </section>
"""

BAND_OPEN = r"""
        <section id="hk-ml" class="hk-band hk-dark relative-z" aria-labelledby="hkMlTitle">
            <h2 id="hkMlTitle" class="hk-h2"><em>Tiga fitur ML</em> berjalan di satu chip INT8.</h2>
            <p class="hk-lead hk-band-lead">Prediksi daya 1 jam, status turbin dari kurva daya wajar, dan simulasi baterai. Ketiganya dihitung tiap menit dengan bobot yang sama persis dengan RTL Verilog akselerator MAC4.</p>
"""
BAND_CLOSE = "        </section>\n"

LIVE_HEAD = r"""
        <div class="hk-section-head relative-z" id="hk-live">
            <h2 class="hk-h2">Data live dari <em>atap CRIMSE.</em></h2>
            <p class="hk-lead">PZEM-017, stasiun cuaca, dan anemometer lewat MQTT tiap 3 detik.</p>
        </div>
"""

METHODS = r"""        hkScroll(id) {
            const el = document.getElementById(id);
            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        },
"""

H = ".wec-v2.wec-hk"
CSS = r"""
    /* =================== Hackathon · gaya cloaked.com =================== */
    H.theme-paper {
        --k-paper: #fbf8ef; --k-raised: #fffdf7; --k-deep: #f3efe2; --k-gray: #e9e6da;
        --k-ink: #130f02; --k-text: #130f02; --k-muted: #454030; --k-faint: #a09c8f;
        --k-rule: #e9e6da; --k-edge: #a09c8f;
        --k-gold: #ff550c; --k-gold-rich: #ff550c; --k-patina: #1f9d6b; --k-patina-deep: #137a52; --k-vermilion: #ec4545;
        --k-lift: none; --k-lift-2: 0 18px 40px -24px rgba(19,15,2,.35);
        --hk-dark: #1c180b; --hk-dark-2: #130f02;
    }
    H.theme-instrument {
        --k-paper: #130f02; --k-raised: #1c180b; --k-deep: #26210f; --k-gray: #2f2914;
        --k-ink: #fbf8ef; --k-text: #e9e6da; --k-muted: #a09c8f; --k-faint: #7c776a;
        --k-rule: rgba(251,248,239,.10); --k-edge: rgba(251,248,239,.28);
        --k-gold: #ff6a2a; --k-gold-rich: #ff6a2a; --k-patina: #03dd8e; --k-patina-deep: #03dd8e; --k-vermilion: #ff6b6b;
        --k-lift: none; --k-lift-2: 0 18px 40px -24px rgba(0,0,0,.6);
        --hk-dark: #0b0901; --hk-dark-2: #060500;
    }
    body:has(.wec-hk), body:has(.wec-hk) .nr-dashboard-theme, body:has(.wec-hk) .v-main { background: var(--k-paper, #fbf8ef) !important; }
    body:has(.wec-hk.theme-instrument), body:has(.wec-hk.theme-instrument) .v-main { background: #130f02 !important; }
    H {
        --k-font: "Hanken Grotesk", "Helvetica Neue", Arial, system-ui, sans-serif;
        --k-display: "Newsreader", "Iowan Old Style", Georgia, serif;
        --k-mono: "Hanken Grotesk", "Helvetica Neue", Arial, sans-serif;
        --hk-pad: clamp(16px, 5.5vw, 80px);
        padding: 0 var(--hk-pad) 48px; font-size: 14px; color: var(--k-text);
    }
    /* garis tipis vertikal di tepi isi, khas cloaked.com */
    H::before { content: ""; position: fixed; top: 0; bottom: 0; left: calc(var(--hk-pad) - 24px); right: calc(var(--hk-pad) - 24px);
        border-left: 1px solid var(--k-rule); border-right: 1px solid var(--k-rule); background: none; opacity: 1; z-index: 0; pointer-events: none; }
    @media (max-width: 640px) { H::before { display: none; } }

    /* bar pengumuman + navigasi */
    H .hk-announce { margin: 0 calc(-1 * var(--hk-pad)); padding: 9px var(--hk-pad); background: var(--hk-dark-2); color: #fbf8ef;
        font-size: 13px; text-align: center; line-height: 1.4; }
    H .hk-announce b { color: #ff550c; font-weight: 500; }
    H .header-section { border-bottom: 1px solid var(--k-rule); margin: 0 calc(-1 * var(--hk-pad)); padding: 14px var(--hk-pad); align-items: center; }
    H h2.dash-title { font-family: var(--k-font); font-weight: 600; font-size: 1.35rem; letter-spacing: -.02em; line-height: 1; display: flex; align-items: center; gap: 8px; }
    H h2.dash-title::before { content: ""; width: 18px; height: 14px; background: #ff550c; clip-path: polygon(0 100%, 38% 8%, 52% 40%, 66% 0, 100% 100%); }
    H h2.dash-title span { color: var(--k-faint) !important; font-weight: 400; }
    H h2.dash-title span::before { content: "· T"; }
    H .energy-value { color: var(--k-ink) !important; background: none !important; -webkit-text-fill-color: currentColor !important; }
    /* kompas arah angin: pindah ke pojok bawah kartu supaya tidak menutupi satuan (m/s) */
    H .compass-widget { top: auto; bottom: 46px; right: 14px; width: 34px; height: 34px; background: var(--k-raised); border-color: var(--k-rule); }
    H .compass-arrow { color: #ff550c; }
    H .compass-val { bottom: -17px; font-family: var(--k-font); font-weight: 500; }
    H .dash-subtitle { font-family: var(--k-font); text-transform: none; letter-spacing: 0; font-size: 13px; color: var(--k-muted); margin-top: 6px; }
    H .turbine-selector { background: transparent; border: 1px solid var(--k-rule); box-shadow: none; padding: 3px; }
    H .t-btn { font-family: var(--k-font); font-weight: 500; font-size: 14px; }
    H .t-btn.active { background: var(--k-ink); color: var(--k-paper); box-shadow: none; }
    H .wec-theme-btn { font-family: var(--k-font); text-transform: none; letter-spacing: 0; font-size: 15px; border-radius: 1000px; padding: 9px 16px;
        background: transparent; color: var(--k-ink); border: 1px solid var(--k-muted); }
    H .status-badge, H .feature-status, H .badge { font-family: var(--k-font) !important; text-transform: none; letter-spacing: 0; font-size: 13px;
        border-radius: 1000px; padding: 5px 12px; background: var(--k-deep); border: 1px solid var(--k-rule) !important; color: var(--k-muted) !important; }
    H .hk-svm { color: var(--k-faint) !important; background: transparent; cursor: help; }
    H .status-dot { background: #ff550c !important; box-shadow: 0 0 0 3px color-mix(in oklab, #ff550c 22%, transparent); }

    /* hero */
    H .hk-hero { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.05fr); gap: clamp(20px, 3vw, 48px); align-items: stretch;
        padding: clamp(28px, 4vw, 56px) 0 clamp(36px, 5vw, 64px); }
    H .hk-hero-copy { display: flex; flex-direction: column; justify-content: center; padding-left: clamp(0px, 2vw, 32px); }
    H .hk-h1, H .hk-h2 { font-family: var(--k-display); font-weight: 400; color: var(--k-ink); margin: 0; letter-spacing: -.02em; }
    H .hk-h1 { font-size: clamp(2.5rem, 4.6vw, 3.6rem); line-height: 1.08; max-width: 12ch; }
    H .hk-h2 { font-size: clamp(2rem, 3.6vw, 3rem); line-height: 1.1; max-width: 22ch; }
    H .hk-h1 em, H .hk-h2 em { font-style: normal; color: #ff550c; }
    H .hk-lead-strong { font-size: 17px; font-weight: 500; color: var(--k-ink); margin: 28px 0 6px; }
    H .hk-lead { font-size: 16px; line-height: 1.45; color: var(--k-faint); margin: 0; max-width: 46ch; }
    H .hk-pill-input { display: flex; align-items: center; gap: 12px; margin-top: 28px; width: min(100%, 380px); padding: 8px 8px 8px 18px;
        background: var(--k-raised); border: 1px solid var(--k-rule); border-radius: 1000px; color: var(--k-ink); text-decoration: none;
        box-shadow: 0 14px 34px -18px rgba(19,15,2,.35); transition: box-shadow .2s ease, transform .2s ease; }
    H .hk-pill-input:hover { transform: translateY(-1px); box-shadow: 0 18px 40px -18px rgba(19,15,2,.45); }
    H .hk-pill-dot { width: 10px; height: 10px; border-radius: 50%; background: #03dd8e; box-shadow: 0 0 0 4px color-mix(in oklab, #03dd8e 22%, transparent); }
    H .hk-pill-dot-off { background: var(--k-faint); box-shadow: none; }
    H .hk-pill-label { color: var(--k-faint); font-size: 15px; }
    H .hk-pill-input b { font-family: var(--k-display); font-weight: 400; font-size: 22px; margin-left: auto; font-variant-numeric: tabular-nums; }
    H .hk-pill-go { width: 40px; height: 40px; border-radius: 50%; display: grid; place-items: center; font-style: normal; font-size: 18px;
        background: #ff550c; color: #fbf8ef; }
    H .hk-fine { font-size: 12px; color: var(--k-muted); margin: 12px 0 0 18px; }
    H .hk-hero-card { position: relative; overflow: hidden; border-radius: 32px; min-height: 340px; padding: clamp(22px, 3vw, 36px);
        background: radial-gradient(120% 90% at 85% 0%, rgba(255,85,12,.38), transparent 55%), radial-gradient(90% 80% at 0% 100%, rgba(3,221,142,.14), transparent 60%), #1c180b;
        color: #fbf8ef; display: flex; flex-direction: column; justify-content: space-between; gap: 24px; }
    H .hk-hero-stats { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 22px 28px; }
    H .hk-hero-stats span { display: block; font-size: 13px; color: rgba(251,248,239,.62); margin-bottom: 4px; }
    H .hk-hero-stats b { font-family: var(--k-display); font-weight: 300; font-size: clamp(2.4rem, 4vw, 3.4rem); line-height: 1; font-variant-numeric: tabular-nums; }
    H .hk-hero-stats small { font-family: var(--k-font); font-size: 14px; margin-left: 6px; color: rgba(251,248,239,.62); }
    H .hk-glass { align-self: flex-start; width: min(100%, 320px); padding: 16px 18px; border-radius: 20px;
        background: rgba(60,52,36,.55); border: 1px solid rgba(251,248,239,.14); backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px); }
    H .hk-glass-title { display: block; font-family: var(--k-display); font-size: 22px; line-height: 1.15; }
    H .hk-glass-row { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; margin-top: 10px; padding: 8px 12px;
        border-radius: 12px; background: rgba(19,15,2,.45); font-size: 13px; color: rgba(251,248,239,.7); }
    H .hk-glass-row b { font-weight: 600; color: #fbf8ef; }
    H .hk-glass-row b.hk-st-ok { color: #03dd8e; } H .hk-glass-row b.hk-st-low { color: #ffb020; } H .hk-glass-row b.hk-st-high { color: #ff6b6b; }
    H .hk-glass-sub { display: block; font-size: 12px; color: rgba(251,248,239,.6); margin-top: 8px; }
    H .hk-chip::before { content: ""; display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 6px; background: rgba(251,248,239,.35); }
    H .hk-chip-on { color: #fbf8ef; } H .hk-chip-on::before { background: #03dd8e; }
    H .wec-fpga.wec-fpga-on .wec-eyebrow { color: #03dd8e !important; }

    /* pita gelap: fitur ML */
    H .hk-band { margin: 0 calc(-1 * var(--hk-pad)); padding: clamp(48px, 6vw, 88px) var(--hk-pad); }
    H .hk-dark { background: var(--hk-dark-2); color: #e9e6da;
        --k-paper: #1c180b; --k-raised: #1c180b; --k-deep: #26210f; --k-gray: #2f2914;
        --k-ink: #fbf8ef; --k-text: #e9e6da; --k-muted: #a09c8f; --k-faint: #a09c8f;
        --k-rule: rgba(251,248,239,.09); --k-edge: rgba(251,248,239,.26);
        --k-patina: #03dd8e; --k-patina-deep: #03dd8e; --k-gold-rich: #ff6a2a; --k-vermilion: #ff6b6b;
        --title-color: #fbf8ef; --text-main: #e9e6da; --text-muted: #a09c8f; }
    H .hk-dark .hk-h2 { color: #fbf8ef; }
    H .hk-band-lead { margin: 18px 0 clamp(28px, 4vw, 44px); color: #a09c8f; max-width: 62ch; }
    H .hk-dark .glass-panel, H .hk-dark .card { background: #1c180b !important; border: 1px solid rgba(251,248,239,.09) !important; }
    H .hk-dark .feature-metric, H .hk-dark .compute-device, H .hk-dark .glass-inner { background: rgba(251,248,239,.035) !important; border-color: rgba(251,248,239,.08) !important; }
    H .hk-section-head { padding: clamp(44px, 6vw, 80px) 0 clamp(20px, 3vw, 32px); }
    H .hk-section-head .hk-lead { margin-top: 14px; }

    /* kartu, label, angka */
    H .glass-panel, H .card { border-radius: 32px !important; border: 1px solid var(--k-rule) !important; box-shadow: none !important; padding: clamp(18px, 2vw, 28px); }
    H .glass-panel:hover, H .card:hover { box-shadow: var(--k-lift-2) !important; border-color: var(--k-rule) !important; }
    H .glass-inner, H .feature-metric, H .compute-device, H .kpi-card, H .forecast-card, H .wec-node, H .wec-sliders {
        border-radius: 20px !important; background: var(--k-deep) !important; border: 1px solid transparent !important; }
    H .card-header, H .param-label, H .feature-metric > span, H .kpi-label, H .log-table th, H .wec-node, H .sensor-details dt,
    H .prediction-details, H .stream-controls label, H .wec-sliders label, H .f-time, H .wec-eyebrow, H .wec-real-grid span, H .wec-real-warn {
        font-family: var(--k-font) !important; font-size: 13px !important; letter-spacing: 0 !important; text-transform: none !important; font-weight: 400; color: var(--k-muted) !important; }
    H .wec-eyebrow { color: #ff550c !important; font-weight: 500; }
    H .feature-heading h3, H .feature-heading h4, H .log-title, H .section-title, H h3 {
        font-family: var(--k-display) !important; font-weight: 400 !important; font-size: clamp(1.35rem, 2vw, 1.75rem) !important; line-height: 1.15; letter-spacing: -.01em; color: var(--k-ink) !important; }
    H .feature-note, H .wec-sub { font-size: 14px; line-height: 1.45; color: var(--k-faint); }
    H .wec-mode { color: #ff550c !important; }
    H .energy-value, H .env-value, H .kpi-value, H .feature-metric strong, H .compute-watts, H .f-speed, H .wec-node b, H .wec-real-grid b {
        font-family: var(--k-display) !important; font-weight: 300 !important; letter-spacing: -.02em; }
    H .feature-metric small, H .env-unit, H .energy-unit, H .compute-watts small, H .wec-real-grid small { font-family: var(--k-font); letter-spacing: 0; font-size: 13px; }
    H .section-divider { border-bottom: 0 !important; margin-top: clamp(44px, 6vw, 80px) !important; }
    H .section-divider h3.dash-title { font-family: var(--k-display) !important; font-weight: 400 !important; font-size: clamp(2rem, 3.6vw, 3rem) !important; letter-spacing: -.02em !important; }
    H .section-divider h3.dash-title::before { display: none; }

    /* tombol pil */
    H .glass-btn, H .action-primary { font-family: var(--k-font); font-weight: 500; font-size: 15px; background: #ff550c !important; color: #fbf8ef !important;
        border-radius: 1000px !important; padding: 10px 18px; min-height: 40px; }
    H .action-soft, H .glass-select, H .stream-controls input, H .stream-controls select { border-radius: 1000px !important; border: 1px solid var(--k-rule) !important; padding: 8px 14px; }
    H .wec-toggle button.on { background: var(--k-ink); color: var(--k-paper); box-shadow: none; }
    H .wec-sliders input[type=range] { accent-color: #ff550c; }
    H .wec-sliders label { font-size: 14px !important; color: var(--k-ink) !important; }
    H .savings-badge { border-radius: 1000px; font-family: var(--k-font); letter-spacing: 0; }

    /* isian, bar, tabel */
    H .compute-bar, H .wec-soc, H .wec-ratio-track, H .progress-bg, H .bar-full { box-shadow: none !important; border-radius: 1000px; }
    H .wec-flow i.run { background: repeating-linear-gradient(90deg, #ff550c 0 6px, transparent 6px 12px) !important; background-size: 24px 2px !important; }
    H .wec-compare .stream-frame, H .wec-twin, H .map-container, H .gauge-container, H .graph-container { border-radius: 20px; }
    H .log-table th { background: transparent !important; }
    H .project-footer { font-family: var(--k-font); letter-spacing: 0; text-transform: none; font-size: 13px; }
    H .glass-toast { border-radius: 1000px !important; }

    @media (max-width: 1024px) {
        H .hk-hero { grid-template-columns: minmax(0, 1fr); }
        H .hk-hero-copy { padding-left: 0; }
    }
    @media (max-width: 640px) {
        H { padding: 0 16px 32px; --hk-pad: 16px; }
        H .hk-h1 { font-size: 2.4rem; }
        H .hk-hero-card { min-height: 0; border-radius: 24px; }
        H .hk-hero-stats b { font-size: 2.2rem; }
        H .glass-panel, H .card { border-radius: 24px !important; }
        H .hk-pill-input { width: 100%; }
    }
""".replace("H", H)


def skin(src):
    s = skin_v2.skin(src)

    def rep(a, b, label, count=1):
        nonlocal s
        assert s.count(a) == count, f"anchor '{label}' ditemukan {s.count(a)} kali"
        s = s.replace(a, b)

    rep('<div class="dash-container wec-v2" :class="timeThemeClass">\n', '<div class="dash-container wec-v2 wec-hk" :class="timeThemeClass">\n' + ANNOUNCE, "root")
    rep("'wec-v2-theme'", "'wec-hk-theme'", "kunci tema", count=2)
    rep("CITA ITB · Wind Edge Chip · v2", "CITA ITB · Wind Edge Chip", "subjudul")
    rep("Monitoring Turbin\n", "windedgechip\n", "judul")
    rep("l.id = 'wec-v2-fonts'", "l.id = 'wec-hk-fonts'", "font id")
    rep("if (document.getElementById('wec-v2-fonts')) return;", "if (document.getElementById('wec-hk-fonts')) return;", "font cek")
    rep("https://fonts.googleapis.com/css2?family=Albert+Sans:wght@400;500;600;700&family=Alumni+Sans:wght@200..600&family=JetBrains+Mono:wght@400;500&display=swap",
        "https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@300;400;500;600&family=Newsreader:opsz,wght@6..72,300;6..72,400;6..72,500&display=swap", "font url")
    # palet grafik
    rep("? { volt: '#7fd1cb', curr: '#4fb3ac', power: '#f2b530', wind: '#d9d9d9', windAlt: '#9a9a9a', track: 'rgba(255,255,255,0.10)' }",
        "? { volt: '#e9e6da', curr: '#a09c8f', power: '#ff6a2a', wind: '#03dd8e', windAlt: '#7c776a', track: 'rgba(251,248,239,0.10)' }", "palet gelap")
    rep(": { volt: '#0f6560', curr: '#3a9d97', power: '#c8961f', wind: '#262626', windAlt: '#8a8a8a', track: 'rgba(17,17,17,0.08)' };",
        ": { volt: '#454030', curr: '#a09c8f', power: '#ff550c', wind: '#130f02', windAlt: '#a09c8f', track: 'rgba(19,15,2,0.08)' };", "palet terang")
    rep("const textColor = this.timeThemeClass === 'theme-instrument' ? '#a6a6a6' : '#5e5e5e';",
        "const textColor = this.timeThemeClass === 'theme-instrument' ? '#a09c8f' : '#454030';", "warna teks grafik")
    rep("fontFamily: 'Alumni Sans, Albert Sans, sans-serif', fontWeight: 300", "fontFamily: 'Newsreader, Georgia, serif', fontWeight: 300", "font gauge")
    s = s.replace("(this.timeThemeClass === 'theme-instrument' ? '#f2f2f2' : '#111111')", "(this.timeThemeClass === 'theme-instrument' ? '#fbf8ef' : '#130f02')")

    # urutan: header -> hero -> pita ML gelap -> data live -> sisanya
    a = s.index('<section class="card glass-panel feature-panel mt-3 relative-z" aria-labelledby="predictionTitle">')
    a = s.rindex("\n", 0, a) + 1
    b = s.index('ref="mapSection"')
    b = s.rindex("\n", 0, b) + 1
    ml = s[a:b]
    s = s[:a] + s[b:]
    h = s.index('<div class="dashboard-grid grid-gauges relative-z">')
    h = s.rindex("\n", 0, h) + 1
    s = s[:h] + HERO + BAND_OPEN + ml + BAND_CLOSE + LIVE_HEAD + s[h:]

    # Turbin 1: angin stasiun menggantikan anemometer Arduino yang macet di 1,25 m/s (Turbin 2 tidak punya stasiun)
    rep("                     ML: {{ activeT.currentData.ml_status }}",
        "                     SVM TA: {{ activeT.currentData.ml_status }}", "badge svm")
    rep('<div class="status-badge"\n                    style="border-color: var(--accent-turquoise); color: var(--accent-turquoise); font-family: \'Arial\', sans-serif;">',
        '<div class="status-badge hk-svm" title="SVM dari TA di Raspi, sejak 21 Okt memakai angin stasiun dan diameter 2,5 m (label rumus Cp; ±30% menit masih Anomaly karena Cp di atas batas Betz). Status utama: kartu Status turbin (kurva daya wajar).">', "badge svm gaya")
    rep("setValue('g_wind', d.Windspeed !== undefined ? d.Windspeed : (d.wind !== undefined ? d.wind : this.activeT.currentData.wind_arduino));",
        "setValue('g_wind', this.activeTurbine === 1 && d.windspeedstation !== undefined && d.windspeedstation !== null ? d.windspeedstation : (d.Windspeed !== undefined ? d.Windspeed : (d.wind !== undefined ? d.wind : this.activeT.currentData.wind_arduino)));", "gauge angin")
    rep("if (t.currentData.wind_arduino > t.maxVal.wind_arduino) t.maxVal.wind_arduino = t.currentData.wind_arduino;",
        "if (t.currentData.wind_arduino > t.maxVal.wind_arduino) t.maxVal.wind_arduino = t.currentData.wind_arduino;\n            if (parseFloat(t.currentData.wind_station) > (parseFloat(t.maxVal.wind_station) || 0)) t.maxVal.wind_station = t.currentData.wind_station;", "max angin stasiun")
    rep('<div class="sub-val">Max: <span class="highlight">{{ activeT.maxVal.wind_arduino }}</span> m/s</div>',
        '<div class="sub-val">Max: <span class="highlight">{{ activeTurbine === 1 ? activeT.maxVal.wind_station : activeT.maxVal.wind_arduino }}</span> m/s{{ activeTurbine === 1 ? \' · stasiun\' : \'\' }}</div>', "max angin teks")
    rep("let wind = parseFloat(d.wind_arduino) || 0; let power = parseFloat(d.power) || 0;",
        "let wind = (targetT === 1 ? parseFloat(d.wind_station) : NaN); if (!(wind >= 0)) wind = parseFloat(d.wind_arduino) || 0; let power = parseFloat(d.power) || 0;", "scatter angin")
    # panel daya komputasi: INA2 mengukur FPGA + ESP32-S3 sekaligus (edge/esp32 env esp32_daya -> MQTT WEC/daya)
    rep("{ key: 'fpga', label: 'FPGA', color: '#0d9488' }", "{ key: 'fpga', label: 'FPGA + ESP32-S3', color: '#ff550c' }", "label fpga")
    rep("{ key: 'raspberry_pi', label: 'Raspberry Pi', color: '#0284c7' }", "{ key: 'raspberry_pi', label: 'Raspberry Pi', color: '#a09c8f' }", "label rpi")
    rep('<h3 id="computePowerTitle">Konsumsi Daya · Raspberry Pi vs FPGA</h3><p class="feature-note">Dua sensor khusus perangkat komputasi · bersama untuk kedua turbin.</p>',
        '<h3 id="computePowerTitle">Konsumsi Daya · Raspberry Pi vs FPGA + ESP32-S3</h3><p class="feature-note">Dua INA219 pada ESP32 terpisah, tiap 1 detik lewat MQTT <code>WEC/daya</code> · bersama untuk kedua turbin.</p>', "judul daya")
    rep("    methods: {\n", "    methods: {\n" + METHODS, "methods")
    i = s.rindex("</style>")
    s = s[:i] + CSS + s[i:]
    return patch_branding(patch_twin_presentation(patch_history_panel(patch_comparison(patch_current_panel(s)))))


if __name__ == "__main__":
    src = open(sys.argv[1]).read()
    out = skin(patch_template.patch(src))
    open(sys.argv[2], "w").write(out)
    print(f"skin hackathon: {len(src)} -> {len(out)} karakter")
