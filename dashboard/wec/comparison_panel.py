"""Live comparison from the independent Raspberry Pi recorder."""

PANEL = '''<!-- wec-comparison-v1 -->
        <section class="card glass-panel feature-panel mt-3 relative-z" aria-labelledby="comparisonTitle">
            <div class="feature-heading"><div><h3 id="comparisonTitle">Perbandingan Inferensi · Input INT8 yang Sama</h3>
                <p class="feature-note">Model native C++ di Raspi dan model di FPGA menerima fitur yang sama melalui MQTT.</p></div>
                <span class="feature-status">{{ !computeComparison ? 'MENUNGGU DATA' : comparisonIsFresh() ? 'PENCATAT AKTIF' : 'DATA LAMA' }}</span></div>
            <p class="feature-note">{{ computeComparison ? computeComparison.matched_pairs + ' pasangan hasil cocok · ' + computeComparison.mismatches + ' berbeda · periode ' + displayMetric(computeComparison.observed_seconds / 60, 1) + ' menit' : 'Menunggu pasangan hasil baru dari kedua perangkat.' }}</p>
            <div class="compute-grid">
                <article v-for="device in computeDevices" :key="device.key" class="compute-device">
                    <h4>{{ device.label }}</h4>
                    <div class="compute-watts">{{ displayMetric(comparisonTiming(device.key), 2) }} <small>µs</small></div>
                    <p class="feature-note">{{ device.key === 'raspberry_pi' ? 'Median waktu hitung model C++ (di luar komunikasi).' : 'Median UART pulang-pergi ESP32-S3 ↔ FPGA (termasuk komunikasi).' }}</p>
                    <dl class="sensor-details">
                        <div><dt>Daya rata-rata</dt><dd>{{ displayMetric(comparisonEnergy(device.key, 'average_w'), 3) }} W</dd></div>
                        <div><dt>Proyeksi 24 jam</dt><dd>{{ displayMetric(comparisonEnergy(device.key, 'projected_wh_per_day_at_this_workload'), 2) }} Wh/hari</dd></div>
                        <div><dt>Energi total / prediksi</dt><dd>{{ displayMetric(comparisonEnergy(device.key, 'total_j_per_prediction'), 3) }} J</dd></div>
                    </dl>
                </article>
            </div>
            <p class="feature-note">Batas waktu hitung dan UART berbeda; bukan rasio percepatan. Raspi juga tetap membaca sensor dan menjalankan program TA.</p>
            <p class="feature-note">{{ computeComparison && computeComparison.energy_comparison_ready ? 'Wh/hari adalah proyeksi pada beban yang teramati; J/prediksi mencakup idle dan pekerjaan latar.' : 'Pengukuran energi belum lengkap: bacaan daya INA219 belum tervalidasi (lihat panel Daya Perangkat).' }}</p>
            <p class="feature-note">Energi tambahan per prediksi dihitung terpisah melalui uji kondisi dasar; belum tersedia sebelum alat ukur tervalidasi.</p>
        </section>
        '''

METHODS = '''comparisonIsFresh() {
            const t = this.computeComparison && this.computeComparison.generated_at_ms;
            return typeof t === 'number' && this.nowMs - t >= -5000 && this.nowMs - t < 30000;
        },
        comparisonTiming(key) {
            if (!this.comparisonIsFresh()) return null;
            return this.computeComparison[key === 'raspberry_pi' ? 'rpi_core_us_median' : 'fpga_uart_us_median'];
        },
        comparisonEnergy(key, field) {
            if (!this.comparisonIsFresh()) return null;
            const d = this.computeComparison.energy && this.computeComparison.energy[key === 'raspberry_pi' ? 'rpi' : 'fpga'];
            return d && d.valid ? d[field] : null;
        },
        '''


def patch_comparison(template):
    if '<!-- wec-comparison-v1 -->' in template:
        # 22 Okt: kanal FPGA sudah dipasang; perbarui teks pada template yang sudah dideploy.
        return template.replace("'Pengukuran energi belum lengkap: kanal INA219 FPGA belum dipasang dan bacaan daya belum tervalidasi.'", "'Pengukuran energi belum lengkap: bacaan daya INA219 belum tervalidasi (lihat panel Daya Perangkat).'")
    anchor = 'aria-labelledby="computePowerTitle"'
    assert template.count(anchor) == 1
    i = template.rindex('<section',0,template.index(anchor))
    template = template[:i] + PANEL + template[i:]
    for a,b in [
        ('computePower: {','computeComparison: null,\n            computePower: {'),
        ("if (newMsg.topic === 'compute_power') {", """if (newMsg.topic === 'WEC/comparison/summary') {
                let d = newMsg.payload;
                try { if (typeof d === 'string') d = JSON.parse(d); } catch (e) { return; }
                if (d && d.kind === 'normal_live' && typeof d.generated_at_ms === 'number' && (!this.computeComparison || d.generated_at_ms >= this.computeComparison.generated_at_ms)) {
                    this.computeComparison = d; this.nowMs = Date.now();
                }
                return;
            }
            if (newMsg.topic === 'compute_power') {"""),
        ('    methods: {\n','    methods: {\n        '+METHODS),
    ]:
        assert template.count(a)==1, a
        template=template.replace(a,b,1)
    return template
