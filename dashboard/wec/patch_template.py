"""Patch template dashboard Genis ("ECharts Neon Component") dengan hasil ML + digital twin 3D.

Semua fitur Genis dipertahankan. Setiap potongan yang diganti dicek dulu (assert): kalau template
di server sudah berubah, patch berhenti tanpa menulis apa pun.
Pemakaian: python patch_template.py template_asli.vue template_baru.vue
"""

import sys

PRED_START = '<section class="card glass-panel feature-panel mt-3 relative-z" aria-labelledby="predictionTitle">'

NEW_PANELS = r'''<section class="card glass-panel feature-panel mt-3 relative-z" aria-labelledby="predictionTitle">
            <div class="feature-heading">
                <div><h3 id="predictionTitle">Prediksi ML · Rata-rata Daya 1 Jam ke Depan · T{{ activeTurbine }}</h3>
                <p class="feature-note">MLP INT8 16-32-16-1 yang identik dengan akselerator FPGA, dihitung tiap menit dari data live + prakiraan Open-Meteo.</p></div>
                <span class="feature-status" :class="{'feature-warning': activeT.prediction.error || predictionExpired}">{{ activeTurbine === 2 ? 'Hanya Turbin 1' : predictionStatus }}</span>
            </div>
            <p v-if="activeT.prediction.error" class="feature-error">{{ activeT.prediction.error }}</p>
            <details v-if="activeTurbine === 1 && wecRingkas" class="wec-detail">
                <summary class="feature-note wec-mode">{{ wecRingkas }} <span class="wec-detail-buka">· detail</span></summary>
                <p v-if="activeTurbine === 1 && wecForecast && wecForecast.mode && wecForecast.mode !== 'normal'" class="feature-note wec-mode">Mode cadangan: {{ wecForecast.menit_estimasi }} dari 61 menit terakhir tanpa data daya. <span v-if="wecForecast.menit_cut_in">{{ wecForecast.menit_cut_in }} menit angin di bawah ambang putar 1,4 m/s (PZEM mati di bawah 7 V) → daya 0 W. </span><span v-if="wecForecast.menit_estimasi - (wecForecast.menit_cut_in || 0) > 0">{{ wecForecast.menit_estimasi - (wecForecast.menit_cut_in || 0) }} menit PZEM tidak merespons → daya wajar dari angin (MLP kurva daya). </span>Uji 1–20 Okt: MAE 5,14 W, setara mode normal 5,07 W.</p>
                <p v-if="activeTurbine === 1 && wecForecast && wecForecast.offline" class="feature-note wec-mode">Mode offline: prakiraan Open-Meteo tidak tersedia, prediksi memakai model INT8 offline (tanpa prakiraan cuaca). Uji 1–20 Okt: MAE 5,62 W vs 5,48 W dengan Open-Meteo.</p>
                <p v-if="activeTurbine === 1 && wecForecast && wecForecast.pulih" class="feature-note wec-mode">Mode pemulihan: Raspi baru kembali setelah mati, baru {{ wecForecast.menit_data_60 }} dari 60 menit terakhir berisi data; menit yang kosong diisi nilai tertua yang ada. Uji Raspi mati 75 menit (1–20 Okt): MAE 6,04 W, hampir sama dengan data utuh 5,99 W (persistence 8,73 W).</p>
                <p v-if="activeTurbine === 1 && wecForecast && wecForecast.celah && !wecForecast.pulih" class="feature-note wec-mode">Data berlubang (Raspi sempat reboot karena internet mati): rata-rata fitur dihitung dari menit yang tersedia. Uji dengan 20% data hilang: cakupan 97,7%, MAE 5,07 W vs 5,00 W data utuh.</p>
            </details>
            <p v-if="activeTurbine === 1 && wec.ml && !wecForecast" class="feature-note wec-mode">Belum ada prediksi: {{ wec.ml.alasan || 'menunggu data' }}.</p>
            <div class="feature-metrics wec-metrics">
                <div class="feature-metric"><span>Rata-rata daya 1 jam ke depan</span><strong>{{ displayMetric(activeT.prediction.power_w, 1) }} <small>W</small></strong>
                    <em class="wec-sub" v-if="activeTurbine === 1 && wecForecast">rentang 80%: {{ displayMetric(wecForecast.p10, 1) }}–{{ displayMetric(wecForecast.p90, 1) }} W</em></div>
                <div class="feature-metric"><span>Energi 1 jam berikutnya</span><strong>{{ displayMetric(activeT.prediction.energy_wh, 1) }} <small>Wh</small></strong>
                    <em class="wec-sub" v-if="activeTurbine === 1 && wecForecast">persistence: {{ displayMetric(wecForecast.persistence_w, 1) }} W</em></div>
                <div class="feature-metric"><span>Prakiraan angin 1 jam (Open-Meteo)</span><strong>{{ displayMetric(activeT.prediction.wind_ms, 2) }} <small>m/s</small></strong>
                    <em class="wec-sub">grid model cuaca, bukan anemometer atap</em></div>
                <div class="feature-metric"><span>Akurasi live 24 jam (MAE)</span><strong>{{ wecEval && wecEval.n ? displayMetric(wecEval.mae_w, 1) : '—' }} <small>W</small></strong>
                    <em class="wec-sub">{{ wecEval && wecEval.n ? 'persistence ' + displayMetric(wecEval.mae_persistence_w, 1) + ' W · ' + wecEval.n + ' prediksi dinilai' : 'dinilai setelah 60 menit berjalan' }}</em></div>
            </div>
            <p v-if="activeTurbine === 1" class="wec-fpga" :class="{ 'wec-fpga-on': wecFpga }"><span class="wec-eyebrow">Chip</span>{{ wecFpgaText }}</p>
            <div class="prediction-details"><span>Model: {{ activeT.prediction.model || '—' }}</span><span>Dibuat: {{ displayTimestamp(activeT.prediction.generated_at) }}</span><span>Target: {{ displayTimestamp(activeT.prediction.target_at) }}</span></div>
            <p class="feature-note">{{ activeTurbine === 2 ? 'Turbin 2 belum punya anemometer stasiun yang valid, sehingga prediksi hanya untuk Turbin 1.' : (predictionExpired ? 'Prediksi melewati waktu target. Menunggu hasil terbaru.' : 'Nilai = rata-rata daya 60 menit ke depan (sama dengan energi Wh jam berikutnya). Rentang 80% dari galat historis.') }}</p>
        </section>

        <div class="wec-two mt-3 relative-z" v-if="activeTurbine === 1">
            <section class="card glass-panel feature-panel" aria-labelledby="wecStatusTitle">
                <div class="feature-heading"><div><h3 id="wecStatusTitle">Status Turbin · Kurva Daya Wajar</h3>
                    <p class="feature-note">Daya aktual dibandingkan daya yang wajar untuk angin saat ini (MLP INT8 kedua, rata-rata 30 menit).</p></div>
                    <span class="feature-status wec-chip" :class="'wec-' + wecStatusKey">{{ wecStatus ? wecStatus.label : 'Menunggu data' }}</span></div>
                <div class="wec-gauge-row">
                    <div class="feature-metric"><span>Daya aktual (30 menit)</span><strong>{{ displayMetric(wecStatus && wecStatus.actual_w, 1) }} <small>W</small></strong></div>
                    <div class="feature-metric"><span>Daya wajar (30 menit)</span><strong>{{ displayMetric(wecStatus && wecStatus.expected_w, 1) }} <small>W</small></strong></div>
                </div>
                <div class="wec-ratio" v-if="wecStatus && wecStatus.ratio !== null">
                    <div class="wec-ratio-track"><div class="wec-ratio-ok" :style="ratioBand"></div><div class="wec-ratio-dot" :style="{left: ratioPos + '%'}"></div></div>
                    <div class="wec-ratio-labels"><span>0</span><span>rasio {{ displayMetric(wecStatus.ratio, 2) }}</span><span>2</span></div>
                </div>
                <p class="feature-note">Ambang dari data validasi: di bawah {{ wecStatus ? displayMetric(wecStatus.ambang.bawah, 2) : '—' }} → di bawah normal, di atas {{ wecStatus ? displayMetric(wecStatus.ambang.atas, 2) : '—' }} → periksa sensor. Saat daya wajar &lt; 5 W, status tidak dinilai (angin lemah).</p>
            </section>
            <section class="card glass-panel feature-panel" aria-labelledby="wecBatTitle">
                <div class="feature-heading"><div><h3 id="wecBatTitle">Aki 12 V 50 Ah · Simulasi 1 Jam ke Depan</h3>
                    <p class="feature-note">Rantai turbin → charge controller → aki {{ wecBattery ? wecBattery.kapasitas_wh : 600 }} Wh (dipakai sampai 50%) → inverter → beban; kelebihan saat aki penuh ke dump load 35 Ω.</p></div>
                    <span class="feature-status" :class="{'feature-warning': wecBattery && wecBattery.pln_soon}">{{ wecBattery && wecBattery.pln_soon ? 'Perlu PLN' : 'Aman' }}</span></div>
                <div class="wec-soc"><div class="wec-soc-fill" :style="{width: (wecBattery ? wecBattery.soc : 0) + '%'}"></div>
                    <div class="wec-soc-next" v-if="wecBattery && wecBattery.soc_1h !== null" :style="{left: wecBattery.soc_1h + '%'}" title="perkiraan 1 jam lagi"></div></div>
                <div class="wec-gauge-row">
                    <div class="feature-metric"><span>SoC sekarang → 1 jam</span><strong>{{ wecBattery ? displayMetric(wecBattery.soc, 0) : '—' }}<small>%</small> → {{ wecBattery ? displayMetric(wecBattery.soc_1h, 0) : '—' }}<small>%</small></strong></div>
                    <div class="feature-metric"><span>Energi ke baterai 1 jam</span><strong>{{ wecBattery ? displayMetric(wecBattery.energy_1h_wh, 1) : '—' }} <small>Wh</small></strong></div>
                </div>
                <p class="feature-note">Simulasi: aki dan inverter belum terpasang (turbin sekarang ke dump load 35 Ω / 1.200 W). Beban {{ wecBattery ? wecBattery.load_w : '—' }} W. Angka nyata butuh sensor aki dan keluaran inverter.</p>
            </section>
        </div>

        <section ref="twinSection" class="card glass-panel feature-panel mt-3 relative-z" aria-labelledby="twinTitle">
            <div class="feature-heading"><div><h3 id="twinTitle">Digital Twin 3D · Turbin 1</h3>
                <p class="feature-note">Geser untuk memutar, cubit/scroll untuk zoom. Mode demo: atur angin dan lihat respons turbin serta model.</p></div>
                <div class="wec-toggle" role="group" aria-label="Mode digital twin">
                    <button type="button" :class="{on: twin.mode === 'live'}" @click="twin.mode = 'live'">Live</button>
                    <button type="button" :class="{on: twin.mode === 'demo'}" @click="twin.mode = 'demo'">Demo</button></div></div>
            <div class="wec-twin-wrap">
                <div ref="twinBox" class="wec-twin"><p v-if="twin.error" class="feature-error wec-twin-msg">{{ twin.error }}</p>
                    <p v-else-if="!twin.ready" class="feature-note wec-twin-msg">Memuat model 3D…</p></div>
                <div class="wec-twin-side">
                    <div v-if="twin.mode === 'demo'" class="wec-sliders">
                        <label>Angin {{ displayMetric(twin.demoWind, 1) }} m/s<input type="range" min="0" max="8" step="0.1" v-model.number="twin.demoWind"></label>
                        <label>Arah {{ twin.demoDir }}°<input type="range" min="0" max="359" step="1" v-model.number="twin.demoDir"></label></div>
                    <div class="feature-metric"><span>Angin {{ twin.mode === 'demo' ? '(demo)' : '(live)' }}</span><strong>{{ displayMetric(twinView.wind, 2) }} <small>m/s</small></strong></div>
                    <div class="feature-metric"><span>Daya {{ twin.mode === 'demo' ? '(kurva empiris)' : '(live)' }}</span><strong>{{ displayMetric(twinView.power, 1) }} <small>W</small></strong></div>
                    <div class="feature-metric"><span>Prediksi 1 jam {{ twin.mode === 'demo' ? '(model INT8)' : '' }}</span><strong>{{ displayMetric(twinView.forecast, 1) }} <small>W</small></strong></div>
                    <div class="feature-metric"><span>Putaran rotor (estimasi)</span><strong>{{ displayMetric(twinView.rpm, 0) }} <small>rpm</small></strong></div>
                </div>
            </div>
            <div class="wec-flow" aria-label="Aliran energi">
                <span class="wec-node">Turbin<b>{{ displayMetric(twinView.power, 0) }} W</b></span><i :class="{run: twinView.power > 1}"></i>
                <span class="wec-node">Baterai<b>{{ displayMetric(twinView.soc, 0) }}% {{ twinView.charging ? '↑' : '↓' }}</b></span><i :class="{run: twinView.load > 0}"></i>
                <span class="wec-node">Beban<b>{{ displayMetric(twinView.load, 0) }} W</b></span>
                <span class="wec-node wec-pln" :class="{on: twinView.pln}">PLN<b>{{ twinView.pln ? 'siaga' : 'standby' }}</b></span>
            </div>
            <p class="feature-note">Putaran rotor dihitung dari angin (perkiraan tip-speed), bukan diukur. Mode demo: daya dari kurva daya empiris turbin ini; prediksi dari model INT8 yang sama, dengan anggapan angin slider sudah bertahan 1 jam. Prediksi bisa lebih rendah dari daya sekarang karena di data nyata angin kencang jarang bertahan lama.</p>
        </section>

'''

DATA_ANCHOR = "            maxPowerRating: 1000 // Watt\n"
DATA_ADD = """            maxPowerRating: 1000, // Watt
            wec: { ml: null, live: null, model: null, fpga: null },
            twin: { mode: 'live', demoWind: 3.0, demoDir: 90, ready: false, error: '' },
            twinRuntime: Object.seal({ three: null, renderer: null, scene: null, camera: null, rotor: null, yaw: null, particles: null,
                raf: null, observer: null, started: false, angle: 0, rpmNow: 0, yawNow: 0, az: 0.8, el: 0.35, dist: 9, drag: null, visible: false, last: 0 })
"""

COMPUTED_ANCHOR = "    computed: {\n"
COMPUTED_ADD = """    computed: {
        wecForecast() { return this.wec.ml && this.wec.ml.forecast ? this.wec.ml.forecast : null; },
        wecStatus() { return this.wec.ml ? this.wec.ml.status : null; },
        wecBattery() { return this.wec.ml ? this.wec.ml.battery : null; },
        wecEval() { return this.wec.ml ? this.wec.ml.eval : null; },
        wecWarmup() { return this.wec.ml ? this.wec.ml.warmup : null; },
        wecRingkas() {
            const f = this.wecForecast; if (!f) return '';
            const r = [];
            if (f.mode && f.mode !== 'normal') r.push((f.menit_cut_in || 0) * 2 >= f.menit_estimasi ? 'Angin lemah: turbin diam, daya 0 W' : 'Sensor daya diam: daya diperkirakan dari angin');
            if (f.pulih) r.push('Raspi baru kembali: mode pemulihan');
            else if (f.celah) r.push('Sebagian data hilang (Raspi restart), prediksi tetap jalan');
            if (f.offline) r.push('Tanpa prakiraan cuaca (offline)');
            return r.join(' · ');
        },
        wecFpga() {
            const f = this.wec.fpga;
            if (!f || !f.t || (this.wec.ml && this.wec.ml.t && this.wec.ml.t - f.t > 180000)) return null;   // basi: lebih dari 3 menit tertinggal
            return f;
        },
        wecFpgaText() {
            const f = this.wecFpga;
            if (!f) return 'FPGA belum tersambung · prediksi dihitung CPU dengan bobot INT8 yang sama (bit-exact)';
            const src = f.sumber === 'simulasi' ? 'Simulasi golden model (papan belum tersambung)' : 'Tang Nano 4K via ' + (f.port || 'UART');
            return src + ' · ' + f.cycles + ' siklus · ' + (f.us !== null && f.us !== undefined ? Math.round(f.us / 100) / 10 + ' ms pulang-pergi · ' : '') + (f.cocok ? 'hasil identik dengan CPU' : 'BEDA dengan CPU (' + f.out_q_fpga + ' vs ' + f.out_q_cpu + ')');
        },
        wecStatusKey() {
            const l = this.wecStatus ? this.wecStatus.label : '';
            return l === 'Normal' ? 'ok' : l === 'Di bawah normal' ? 'low' : l === 'Di atas normal' || l === 'PZEM tidak merespons' ? 'high' : 'idle';
        },
        ratioPos() { const r = this.wecStatus && this.wecStatus.ratio; return r === null || r === undefined ? 50 : Math.max(0, Math.min(100, r / 2 * 100)); },
        ratioBand() {
            const a = this.wecStatus ? this.wecStatus.ambang : { bawah: 0.42, atas: 1.46 };
            return { left: (a.bawah / 2 * 100) + '%', width: ((Math.min(a.atas, 2) - a.bawah) / 2 * 100) + '%' };
        },
        twinView() {
            if (this.twin.mode === 'demo') {
                const w = this.twin.demoWind, p = this.demoPower(w);
                const b = this.demoBattery(p);
                return { wind: w, dir: this.twin.demoDir, power: p, forecast: this.demoForecast(w, p), rpm: this.estimateRpm(w, p),
                         soc: b.soc, load: b.load, charging: b.charging, pln: b.pln };
            }
            const l = this.wec.live || {};
            const w = typeof l.ws === 'number' ? l.ws : null, p = typeof l.p === 'number' ? l.p : null;
            const bt = this.wecBattery;
            return { wind: w, dir: typeof l.wd === 'number' ? l.wd : 0, power: p, forecast: this.wecForecast ? this.wecForecast.power_w : null, rpm: this.estimateRpm(w, p),
                     soc: bt ? bt.soc : null, load: bt ? bt.load_w : null, charging: typeof p === 'number' && bt && p * 0.95 > bt.load_w, pln: !!(bt && bt.pln_soon) };
        },
"""

WATCH_ANCHOR = "            if (!newMsg || typeof newMsg.topic !== 'string') return;\n"
WATCH_ADD = WATCH_ANCHOR + """            // Replay saat browser tersambung dikirim sebagai SATU pesan: kalau beberapa pesan datang beruntun,
            // watcher Vue hanya melihat yang terakhir (hasil ML baru muncul di tick berikutnya).
            if (newMsg.topic === 'wec_replay' && Array.isArray(newMsg.payload)) {
                const handler = this.$options.watch.msg;
                newMsg.payload.forEach(m => { try { handler.call(this, m); } catch (e) { /* lewati satu pesan rusak */ } });
                return;
            }
            // Hasil Mesin WEC (Node-RED): ML 3 fitur + data live untuk digital twin.
            if (newMsg.topic === 'wec_ml') { this.wec.ml = newMsg.payload; return; }
            if (newMsg.topic === 'wec_live') { this.wec.live = newMsg.payload; return; }
            if (newMsg.topic === 'wec_fpga') { this.wec.fpga = newMsg.payload; return; }
            // jangan Object.freeze: proxy reaktif Vue gagal membaca properti beku (mode demo crash dan halaman seperti refresh)
            if (newMsg.topic === 'wec_model') { this.wec.model = newMsg.payload; return; }
"""

METHODS_ANCHOR = "    methods: {\n        nonNegativeNumber(value) {\n"
METHODS_ADD = r"""    methods: {
        // ---------- Wind Edge Chip: demo + digital twin ----------
        demoPower(w) {
            const k = this.wec.model && this.wec.model.kurva_daya;
            if (!k) return null;
            const xs = k.angin_ms; let best = 0, ys = [];
            k.daya_W.forEach(v => { best = Math.max(best, v === null ? 0 : v); ys.push(best); });   // dibuat tidak turun
            if (w <= xs[0]) return ys[0] * w / xs[0];
            for (let i = 1; i < xs.length; i++) if (w <= xs[i]) return ys[i - 1] + (w - xs[i - 1]) / (xs[i] - xs[i - 1]) * (ys[i] - ys[i - 1]);
            return ys[ys.length - 1];
        },
        demoForecast(w, p) {
            // Angin dari slider dianggap bertahan 60 menit terakhir; prakiraan Open-Meteo ikut slider
            // (median Open-Meteo/stasiun di data latih = 0,76), arah dari slider, jam = sekarang (WIB).
            const m = this.wec.model && this.wec.model.forecast;
            if (!m || p === null) return null;
            const d = this.twin.demoDir * Math.PI / 180, now = new Date(Date.now() + 7 * 3600000);
            const hr = now.getUTCHours() + now.getUTCMinutes() / 60, f0 = (this.wec.ml && this.wec.ml.features) || {};
            const f = { p_now: p, p_lag5: p, p_lag15: p, p_lag30: p, p_lag60: p, p_mean60: p,
                w_now: w, w_mean10: w, w_mean60: w, w3_mean10: w * w * w,
                dir_sin: w > 0.2 ? Math.sin(d) : 0, dir_cos: w > 0.2 ? Math.cos(d) : 0,
                hour_sin: Math.sin(2 * Math.PI * hr / 24), hour_cos: Math.cos(2 * Math.PI * hr / 24),
                rho: typeof f0.rho === 'number' ? f0.rho : 1.077, om_wind_next: w * 0.76 };
            const rh = (x) => { const fl = Math.floor(x), dd = x - fl; return dd > 0.5 ? fl + 1 : dd < 0.5 ? fl : (fl % 2 === 0 ? fl : fl + 1); };
            let h = m.fitur.map(n => { const s = m.skala_fitur[n]; const q = rh((f[n] - s.center) / s.scale); return Math.max(-128, Math.min(127, q)); });
            for (let k = 0; k < m.weights.length; k++) {
                const W = m.weights[k], b = m.bias[k];
                h = b.map((bj, j) => { let acc = bj; for (let i = 0; i < h.length; i++) acc += h[i] * W[i][j]; const s = Math.floor(acc * 32 / 256); return s < 0 ? 0 : s > 127 ? 127 : s; });
            }
            return h[0] * m.skala_keluaran_W_per_lsb;
        },
        demoBattery(p) {
            const live = this.wecBattery, now = new Date(Date.now() + 7 * 3600000), hh = now.getUTCHours();
            const load = 6 + (hh >= 18 && hh < 23 ? 25 : 0);                     // sama dengan simulasi baterai (beban dasar + malam)
            const soc = live && typeof live.soc === 'number' ? live.soc : 50;
            const charging = typeof p === 'number' && p * 0.95 > load;
            return { soc, load, charging, pln: !charging && soc <= 12 };
        },
        estimateRpm(w, p) {
            if (typeof w !== 'number' || w < 1.2 || (typeof p === 'number' && p < 0.5)) return 0;
            return 5.5 * w / 1.25 * 60 / (2 * Math.PI);     // tip-speed ratio ±5,5, jari-jari 1,25 m
        },
        observeTwin() {
            const el = this.$refs.twinSection;
            if (!el || !('IntersectionObserver' in window)) { this.initTwin(); return; }
            this.twinRuntime.observer = new IntersectionObserver(entries => {
                this.twinRuntime.visible = entries.some(e => e.isIntersecting);
                if (this.twinRuntime.visible && !this.twinRuntime.started) this.initTwin();
            }, { rootMargin: '200px' });
            this.twinRuntime.observer.observe(el);
        },
        async initTwin() {
            const R = this.twinRuntime;
            if (R.started) return;
            R.started = true;
            try {
                const THREE = await import('https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js');
                if (!this.runtime.active) return;
                R.three = THREE;
                const box = this.$refs.twinBox;
                const css = getComputedStyle(box);
                const col = (name, fb) => (css.getPropertyValue(name) || '').trim() || fb;
                const scene = new THREE.Scene();
                const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100);
                const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
                renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
                box.appendChild(renderer.domElement);
                scene.add(new THREE.HemisphereLight(0xffffff, 0x8a7a6a, 1.6));
                const sun = new THREE.DirectionalLight(0xffffff, 1.4); sun.position.set(5, 8, 4); scene.add(sun);
                const mat = (c, r = 0.6, m = 0.1) => new THREE.MeshStandardMaterial({ color: c, roughness: r, metalness: m });
                // atap gedung + pagar tipis
                const roof = new THREE.Mesh(new THREE.BoxGeometry(9, 0.2, 9), mat(0xd6d3cf, 0.95)); roof.position.y = -0.1; scene.add(roof);
                const rail = mat(0x9aa3ad, 0.5, 0.4);
                [[0, 4.4, 9, 0.06], [0, -4.4, 9, 0.06]].forEach(([x, z, w, d]) => { const r = new THREE.Mesh(new THREE.BoxGeometry(w, 0.05, d), rail); r.position.set(x, 0.6, z); scene.add(r); });
                // menara
                const tower = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.11, 4.2, 20), mat(0x2f6f8f, 0.4, 0.5)); tower.position.y = 2.1; scene.add(tower);
                const yaw = new THREE.Group(); yaw.position.y = 4.25; scene.add(yaw);
                const nacelle = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.13, 0.7, 20), mat(0xf4f4f2, 0.35)); nacelle.rotation.z = Math.PI / 2; yaw.add(nacelle);
                const tailBoom = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.04, 0.04), mat(0xc9c9c6)); tailBoom.position.x = -0.75; yaw.add(tailBoom);
                const vane = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.45, 0.02), mat(0xf4f4f2, 0.4)); vane.position.set(-1.15, 0.12, 0); yaw.add(vane);
                const rotor = new THREE.Group(); rotor.position.x = 0.42; yaw.add(rotor);
                const hub = new THREE.Mesh(new THREE.SphereGeometry(0.12, 20, 16), mat(0xf4f4f2, 0.3)); hub.scale.x = 1.3; rotor.add(hub);
                for (let k = 0; k < 5; k++) {
                    const blade = new THREE.Mesh(new THREE.BoxGeometry(0.03, 1.2, 0.14), mat(0xfbfbfa, 0.35));
                    blade.position.y = 0.66; const arm = new THREE.Group(); arm.add(blade); arm.rotation.x = k * 2 * Math.PI / 5; blade.rotation.y = 0.3; rotor.add(arm);
                }
                // partikel angin
                const N = 260, pos = new Float32Array(N * 3);
                for (let i = 0; i < N; i++) { pos[3 * i] = (Math.random() - 0.5) * 10; pos[3 * i + 1] = 1 + Math.random() * 5; pos[3 * i + 2] = (Math.random() - 0.5) * 10; }
                const pg = new THREE.BufferGeometry(); pg.setAttribute('position', new THREE.BufferAttribute(pos, 3));
                const accent = new THREE.Color(col('--accent-blue', '#2c5e68'));
                const particles = new THREE.Points(pg, new THREE.PointsMaterial({ color: accent, size: 0.05, transparent: true, opacity: 0.75 }));
                scene.add(particles);
                Object.assign(R, { scene, camera, renderer, rotor, yaw, particles });
                const el = renderer.domElement;
                el.style.touchAction = 'none';
                el.addEventListener('pointerdown', e => { R.drag = { x: e.clientX, y: e.clientY }; el.setPointerCapture(e.pointerId); });
                el.addEventListener('pointermove', e => { if (!R.drag) return; R.az -= (e.clientX - R.drag.x) * 0.008; R.el = Math.max(0.05, Math.min(1.3, R.el + (e.clientY - R.drag.y) * 0.006)); R.drag = { x: e.clientX, y: e.clientY }; });
                el.addEventListener('pointerup', () => { R.drag = null; });
                el.addEventListener('wheel', e => { e.preventDefault(); R.dist = Math.max(5, Math.min(16, R.dist + e.deltaY * 0.01)); }, { passive: false });
                this.resizeTwin(); window.addEventListener('resize', this.resizeTwin);
                this.twin.ready = true;
                R.last = performance.now();
                const loop = (now) => {
                    R.raf = requestAnimationFrame(loop);
                    if (!R.visible || document.hidden) { R.last = now; return; }
                    const dt = Math.min(0.1, (now - R.last) / 1000); R.last = now;
                    const v = this.twinView, wind = typeof v.wind === 'number' ? v.wind : 0;
                    R.rpmNow += ((v.rpm || 0) - R.rpmNow) * Math.min(1, dt * 0.8);    // inersia rotor: tidak melompat saat slider digeser
                    R.angle += R.rpmNow / 60 * 2 * Math.PI * dt * 0.25;               // diperlambat 4x agar terbaca mata
                    R.rotor.rotation.x = R.angle;
                    const target = -((v.dir || 0) * Math.PI / 180);
                    R.yawNow += Math.atan2(Math.sin(target - R.yawNow), Math.cos(target - R.yawNow)) * Math.min(1, dt * 1.5);
                    R.yaw.rotation.y = R.yawNow;
                    // angin datang dari depan rotor (+x lokal) menuju ekor, jadi partikel bergerak berlawanan arah hadap rotor
                    const p = R.particles.geometry.attributes.position, dx = -Math.cos(R.yawNow) * wind * dt * 0.9, dz = Math.sin(R.yawNow) * wind * dt * 0.9;
                    for (let i = 0; i < p.count; i++) {
                        let x = p.getX(i) + dx, z = p.getZ(i) + dz;
                        if (x > 5) x -= 10; if (x < -5) x += 10; if (z > 5) z -= 10; if (z < -5) z += 10;
                        p.setX(i, x); p.setZ(i, z);
                    }
                    p.needsUpdate = true;
                    R.particles.material.opacity = 0.2 + Math.min(0.7, wind / 6);
                    if (!R.drag) R.az += dt * 0.05;
                    R.camera.position.set(R.dist * Math.cos(R.el) * Math.sin(R.az), 2.6 + R.dist * Math.sin(R.el), R.dist * Math.cos(R.el) * Math.cos(R.az));
                    R.camera.lookAt(0, 2.6, 0);
                    R.renderer.render(R.scene, R.camera);
                };
                R.raf = requestAnimationFrame(loop);
            } catch (e) {
                this.twin.error = 'Model 3D tidak dapat dimuat (butuh akses internet ke cdn.jsdelivr.net).';
            }
        },
        resizeTwin() {
            const R = this.twinRuntime, box = this.$refs.twinBox;
            if (!R.renderer || !box) return;
            const w = box.clientWidth || 600, h = box.clientHeight || 360;
            R.renderer.setSize(w, h, false); R.camera.aspect = w / h; R.camera.updateProjectionMatrix();
        },
        disposeTwin() {
            const R = this.twinRuntime;
            if (R.raf) cancelAnimationFrame(R.raf);
            if (R.observer) R.observer.disconnect();
            window.removeEventListener('resize', this.resizeTwin);
            if (R.renderer) { R.renderer.dispose(); if (R.renderer.domElement && R.renderer.domElement.parentNode) R.renderer.domElement.parentNode.removeChild(R.renderer.domElement); }
            if (R.scene) R.scene.traverse(o => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); });
            Object.assign(R, { raf: null, observer: null, renderer: null, scene: null, started: false });
        },
        nonNegativeNumber(value) {
"""

MOUNT_ANCHOR = "        this.observeMapSection();\n"
MOUNT_ADD = ("        this.observeMapSection();\n        this.observeTwin();\n"
             "        // minta hasil terakhir setelah widget siap (pesan saat socket tersambung bisa tertimpa wec_live);\n"
             "        // topik wec/replay tidak cocok dengan switch Genis, jadi tidak memicu baca Google Sheet\n"
             "        setTimeout(() => { try { this.send({ topic: 'wec/replay' }); } catch (e) { /* pratinjau tanpa Node-RED */ } }, 1500);\n")

CLEAN_ANCHOR = "        cleanupDashboard() {\n"
CLEAN_ADD = "        cleanupDashboard() {\n            this.disposeTwin();\n"

CSS_ADD = """
    /* ---------- Wind Edge Chip: panel ML, status, baterai, digital twin ---------- */
    .wec-metrics { grid-template-columns: repeat(4, minmax(0, 1fr)); }
    .wec-detail summary { cursor: pointer; list-style: none; }
    .wec-detail summary::-webkit-details-marker { display: none; }
    .wec-detail-buka { text-decoration: underline; opacity: .75; }
    .wec-detail[open] .wec-detail-buka { display: none; }
    .wec-fpga { display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; margin: 12px 0 4px; font-size: .8rem; color: var(--text-muted); }
    .wec-fpga.wec-fpga-on { color: var(--text-main); }
    .wec-sub { display: block; margin-top: 6px; font-style: normal; font-size: .74rem; color: var(--text-muted); }
    .wec-two { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
    .wec-two > .card { margin: 0; }
    .wec-gauge-row { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 12px; }
    .wec-chip.wec-ok { color: #15803d; border-color: #15803d55; }
    .wec-chip.wec-low { color: #b45309; border-color: #b4530955; }
    .wec-chip.wec-high { color: #b91c1c; border-color: #b91c1c55; }
    .wec-chip.wec-idle { color: var(--text-muted); }
    .wec-ratio { margin-top: 14px; }
    .wec-ratio-track { position: relative; height: 10px; border-radius: 5px; background: var(--card-bg); border: 1px solid var(--card-border); }
    .wec-ratio-ok { position: absolute; top: 0; bottom: 0; background: #15803d33; border-radius: 5px; }
    .wec-ratio-dot { position: absolute; top: -4px; width: 16px; height: 16px; margin-left: -8px; border-radius: 50%; background: var(--text-main); border: 2px solid var(--card-bg-inner); transition: left .6s ease; }
    .wec-ratio-labels { display: flex; justify-content: space-between; font-size: .72rem; color: var(--text-muted); margin-top: 6px; font-variant-numeric: tabular-nums; }
    .wec-soc { position: relative; height: 14px; border-radius: 7px; background: var(--card-bg); border: 1px solid var(--card-border); overflow: hidden; margin-top: 12px; }
    .wec-soc-fill { height: 100%; background: linear-gradient(90deg, #0f766e, #14b8a6); transition: width .8s ease; }
    .wec-soc-next { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--text-main); opacity: .7; }
    .wec-toggle { display: inline-flex; border: 1px solid var(--card-border); border-radius: 8px; overflow: hidden; }
    .wec-toggle button { min-height: 36px; padding: 6px 14px; border: 0; background: transparent; color: var(--text-muted); font-weight: 600; cursor: pointer; }
    .wec-toggle button.on { background: var(--card-bg-inner); color: var(--text-main); }
    .wec-twin-wrap { display: grid; grid-template-columns: minmax(0, 1fr) 260px; gap: 16px; margin-top: 12px; }
    .wec-twin { position: relative; height: 380px; border-radius: 10px; border: 1px solid var(--card-border); background: linear-gradient(180deg, var(--card-bg-inner), var(--card-bg)); overflow: hidden; }
    .wec-twin canvas { width: 100% !important; height: 100% !important; display: block; cursor: grab; }
    .wec-twin-msg { position: absolute; inset: 0; display: grid; place-items: center; margin: 0; }
    .wec-twin-side { display: grid; gap: 10px; align-content: start; }
    .wec-twin-side .feature-metric { padding: 12px 14px; }
    .wec-twin-side .feature-metric strong { font-size: 1.4rem; }
    .wec-sliders { display: grid; gap: 10px; padding: 12px 14px; border: 1px solid var(--card-border); border-radius: 8px; background: var(--card-bg-inner); }
    .wec-sliders label { display: grid; gap: 6px; font-size: .8rem; color: var(--text-muted); }
    .wec-sliders input[type=range] { width: 100%; accent-color: #0f766e; }
    .wec-flow { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-top: 14px; }
    .wec-node { display: grid; padding: 8px 12px; border: 1px solid var(--card-border); border-radius: 8px; background: var(--card-bg-inner); font-size: .74rem; color: var(--text-muted); min-width: 84px; }
    .wec-node b { font-size: .95rem; color: var(--text-main); font-variant-numeric: tabular-nums; }
    .wec-pln { margin-left: auto; }
    .wec-pln.on { border-color: #b4530988; }
    .wec-flow i { flex: 1 1 24px; min-width: 24px; height: 2px; background: repeating-linear-gradient(90deg, var(--card-border) 0 6px, transparent 6px 12px); }
    .wec-flow i.run { background: repeating-linear-gradient(90deg, #0f766e 0 6px, transparent 6px 12px); background-size: 24px 2px; animation: wecFlow 1s linear infinite; }
    @keyframes wecFlow { from { background-position: 0 0; } to { background-position: 24px 0; } }
    @media (max-width: 1024px) {
        .wec-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .wec-twin-wrap { grid-template-columns: 1fr; }
        .wec-twin-side { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .wec-sliders { grid-column: 1 / -1; }
    }
    @media (max-width: 640px) {
        .wec-metrics, .wec-two, .wec-gauge-row { grid-template-columns: 1fr; }
        .wec-twin { height: 300px; }
        .wec-pln { margin-left: 0; }
    }
"""


def patch(src):
    s = src
    def rep(a, b, label):
        nonlocal s
        assert s.count(a) == 1, f"anchor '{label}' ditemukan {s.count(a)} kali; template sudah berubah"
        s = s.replace(a, b)
    a = s.index(PRED_START)
    b = s.index("</section>", a) + len("</section>")
    assert s.count(PRED_START) == 1, "panel prediksi tidak tunggal"
    s = s[:a] + NEW_PANELS.rstrip() + s[b:]
    rep(DATA_ANCHOR, DATA_ADD, "data")
    rep(COMPUTED_ANCHOR, COMPUTED_ADD, "computed")
    rep(WATCH_ANCHOR, WATCH_ADD, "watch")
    rep(METHODS_ANCHOR, METHODS_ADD, "methods")
    rep(MOUNT_ANCHOR, MOUNT_ADD, "mounted")
    rep(CLEAN_ANCHOR, CLEAN_ADD, "cleanup")
    i = s.rindex("</style>")
    s = s[:i] + CSS_ADD + s[i:]
    return s


if __name__ == "__main__":
    src = open(sys.argv[1]).read()
    out = patch(src)
    open(sys.argv[2], "w").write(out)
    print(f"template {len(src)} -> {len(out)} karakter")
