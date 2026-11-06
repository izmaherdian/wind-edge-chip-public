"""Patch panel INA219 pada template hackathon yang sudah dibuat/deploy.

Dipakai juga oleh skin_hackathon agar panel V/A/W konsisten pada deploy berikutnya.
Tidak mengubah panel daya turbin PZEM maupun mesin ML.
"""

PANEL = '''<section class="card glass-panel feature-panel mt-3 relative-z" aria-labelledby="computePowerTitle">
            <!-- wec-power-vaw-v5 -->
            <div class="feature-heading"><div><h3 id="computePowerTitle">Daya Perangkat · Raspberry Pi vs FPGA + ESP32-S3</h3>
                <p class="feature-note">Pembacaan INA219 setiap detik · tegangan, arus, dan daya.</p></div></div>
            <div class="compute-grid">
                <article v-for="device in computeDevices" :key="device.key" class="compute-device">
                    <div class="feature-heading"><h4>{{ device.label }}</h4><span class="feature-status" :class="{'feature-warning': sensorStatus(device.key) !== 'DATA TERBACA'}" :title="computePower[device.key].error || ''">{{ sensorStatus(device.key) }}</span></div>
                    <div class="compute-watts">{{ displayMetric(computeMetric(device.key, 'power_w'), 2) }} <small>W</small></div>
                    <div style="display:flex;flex-wrap:wrap;gap:12px 24px;margin:12px 0">
                        <div><span class="feature-note">Tegangan</span><div><strong>{{ displayMetric(computeMetric(device.key, 'voltage_v'), 2) }}</strong> V</div></div>
                        <div><span class="feature-note">Arus</span><div><strong>{{ displayMetric(computeMetric(device.key, 'current_a'), 3) }}</strong> A</div></div>
                    </div>
                    <p class="feature-note" v-if="computePower[device.key].installed === false">Kanal INA219 perangkat ini belum dipasang.</p>
                    <p class="feature-note" v-else-if="sensorStatus(device.key) === 'MENTAH · BELUM VALID'">Nilai mentah sensor, belum valid: {{ computePower[device.key].error }}</p>
                    <p class="feature-note">Sampel: {{ displayTimestamp(computePower[device.key].timestamp) }}</p>
                </article>
            </div>
            <p class="feature-note">Daya seluruh perangkat pada jalur INA219. Nilai yang gagal validasi ditampilkan sebagai nilai mentah berlabel; lebih dari 30 detik ditampilkan sebagai —. Arus dan daya belum diverifikasi dengan alat ukur pembanding.</p>
        </section>'''

METHODS = '''updateComputeSensor(key, payload) {
            const previous = this.computePower[key];
            if (!previous) return;
            const now = Date.now();
            this.nowMs = now;
            const data = payload && typeof payload === 'object' && !Array.isArray(payload) ? payload : {};
            const timestamp = data.timestamp === undefined ? now : this.parseTimestamp(data.timestamp);
            if (timestamp !== null && previous.timestamp !== null && timestamp < previous.timestamp) return;
            const finite = v => typeof v === 'number' && Number.isFinite(v);
            const { voltage_v: voltage, current_a: current, power_w: power } = data;
            const raw = data.raw && typeof data.raw === 'object' ? data.raw : {};
            const rawOk = ['voltage_v', 'current_a'].some(k => finite(raw[k]));
            const valid = data.installed !== false && timestamp !== null && timestamp <= now + 5000
                && data.measurement_valid === true && [voltage, current, power].every(finite)
                && voltage >= 4 && voltage <= 6 && current >= -0.01 && current < 3.2 && power >= 0
                && Math.abs(power - voltage * current) <= 0.03;
            this.computePower[key] = {
                power_w: valid ? power : null, voltage_v: valid ? voltage : null, energy_wh: null,
                installed: data.installed !== false,
                current_a: valid ? current : null,
                timestamp: timestamp !== null && timestamp <= now + 5000 ? timestamp : null,
                current_note: data.current_note || (valid ? 'Arus belum diverifikasi alat ukur.' : 'Pembacaan arus tidak tersedia / tidak valid.'),
                raw: !valid && rawOk ? { voltage_v: finite(raw.voltage_v) ? raw.voltage_v : null, current_a: finite(raw.current_a) ? raw.current_a : null, power_w: finite(raw.power_w) ? raw.power_w : null } : null,
                error: valid ? '' : (data.error || 'Pembacaan sensor atau waktu sampel tidak valid.')
            };
        },
        sensorStatus(key) {
            const sample = this.computePower[key];
            if (sample.installed === false) return 'BELUM DIPASANG';
            if (sample.error) return sample.raw && sample.timestamp !== null && this.nowMs - sample.timestamp <= this.sensorStaleMs ? 'MENTAH · BELUM VALID' : 'DATA TIDAK VALID';
            if (sample.timestamp === null || sample.current_a === null) return 'MENUNGGU SENSOR';
            return this.nowMs - sample.timestamp > this.sensorStaleMs ? 'DATA LAMA' : 'DATA TERBACA';
        },
        computeMetric(key, field) {
            const st = this.sensorStatus(key);
            if (st === 'MENTAH · BELUM VALID') return this.computePower[key].raw[field];
            return st === 'DATA TERBACA' ? this.computePower[key][field] : null;
        },
        computeBarWidth(key) { return 0; },
        '''


def patch_current_panel(template):
    if '<!-- wec-power-vaw-v5 -->' in template:
        return template
    default = "fpga: { power_w: null, voltage_v: null, current_a: null, energy_wh: null, timestamp: null, error: '' }"
    if default in template:
        assert template.count(default) == 1
        template = template.replace(default, "fpga: { installed: false, current_note: 'Kanal INA219 perangkat ini belum dipasang.', power_w: null, voltage_v: null, current_a: null, energy_wh: null, timestamp: null, error: '' }", 1)
    anchor = 'aria-labelledby="computePowerTitle"'
    assert template.count(anchor) == 1, 'panel INA219 tidak tunggal'
    i = template.rindex('<section', 0, template.index(anchor))
    j = template.index('</section>', i) + len('</section>')
    template = template[:i] + PANEL + template[j:]
    a, b = 'updateComputeSensor(key, payload) {', 'restoreCameraSettings() {'
    assert template.count(a) == template.count(b) == 1, 'anchor metode INA219 berubah'
    i, j = template.index(a), template.index(b)
    template = template[:i] + METHODS + template[j:]
    return template
