"""History-only chart patch: never drive live gauges from Sheet measurements."""
from pathlib import Path

HERE = Path(__file__).resolve().parent

METHODS = '''
        applyHistory3h(payload, live = false) {
            if (!payload || !Array.isArray(payload.rows)) return;
            const now = Date.now(), start = Math.floor((now - 3 * 3600000) / 60000) * 60000;
            const byMinute = new Map((this.history3h || []).filter(r => r.serverTime >= start).map(r => [r.serverTime, r]));
            for (const row of payload.rows) {
                const t = row && row.serverTime;
                if (typeof t !== 'number' || !Number.isFinite(t) || t < now - 3 * 3600000 || t > now) continue;
                const minute = Math.floor(t / 60000) * 60000, old = byMinute.get(minute);
                if (!live && old && old._live) continue;
                byMinute.set(minute, { ...row, serverTime: minute, _live: live });
            }
            this.history3h = [...byMinute.values()].sort((a, b) => a.serverTime - b.serverTime);
            this.history3hStatus = `Riwayat 3 jam · ${this.history3h.length} menit berisi data · garis kosong berarti tidak ada rekaman. Nilai live tetap dari MQTT.`;
            const lookup = new Map(this.history3h.map(r => [r.serverTime, r]));
            const points = [];
            for (let t = start; t <= now; t += 60000) points.push(lookup.get(t) || { serverTime: t });
            const number = value => typeof value === 'number' && Number.isFinite(value) ? value : null;
            const turbine = this.t1;
            turbine.timeData = points.map(r => new Date(r.serverTime).toLocaleTimeString('id-ID', { timeZone: 'Asia/Jakarta', hour: '2-digit', minute: '2-digit', hour12: false }));
            turbine.voltData = points.map(r => number(r.voltage));
            turbine.currData = points.map(r => number(r.current));
            turbine.windData = points.map(r => number(r.Windspeed));
            turbine.windStationData = points.map(r => number(r.windspeedstation));
            turbine.powerData = points.map(r => number(r.power));
            turbine.sheetLogs = this.history3h.slice().reverse();
            if (this.activeTurbine === 1 && this.chartsReady) this.refreshAllCharts();
        },
'''


def patch_history_panel(template):
    if '<!-- wec-history-3h-v1 -->' in template:
        return template
    anchors = {
        '            activeTurbine: 1,': "            history3h: [], history3hStatus: 'Riwayat 3 jam sedang dimuat; nilai live berasal dari MQTT.',\n            activeTurbine: 1,",
        '            if (!newMsg || typeof newMsg.topic !== \'string\') return;': "            if (!newMsg || typeof newMsg.topic !== 'string') return;\n            if (newMsg.topic === 'wec/history/chart') { this.applyHistory3h(newMsg.payload); return; }\n            if (newMsg.topic === 'history') return; // legacy replay must not overwrite live gauges\n",
        '    methods: {\n': '    methods: {\n' + METHODS,
        'manualSync() { this.send({ topic: "replay" }); this.send({ topic: "replay2" }); },': 'manualSync() { this.send({ topic: "wec/history/request" }); this.send({ topic: "replay2" }); },',
        '        updateLiveCharts(d, targetT) {': '''        updateLiveCharts(d, targetT) {
            if (targetT === 1) {
                this.updateVisuals(d, targetT);
                if (this.activeTurbine === 1 && this.chartsReady) this.updateGaugesOnly(d);
                if (typeof d.energy === 'number' && Number.isFinite(d.energy)) this.t1.energyVal = d.energy.toFixed(0);
                this.applyHistory3h({ rows: [{ ...d, Windspeed: d.Windspeed === undefined ? d.wind : d.Windspeed, serverTime: typeof d.serverTime === 'number' ? d.serverTime : Date.now() }] }, true);
                this.analyzeData(this.t1.currentData, targetT);
                return;
            }''',
        '        <!-- BARIS 1:': '''        <!-- wec-history-3h-v1 -->
        <p class="feature-note relative-z" role="status">{{ history3hStatus }}</p>
        <!-- BARIS 1:''',
    }
    for old, new in anchors.items():
        assert template.count(old) == 1, f'History patch anchor changed: {old[:55]}'
        template = template.replace(old, new, 1)
    return template


def patch_history_seed(engine):
    marker = '// Merge measured history only.'
    anchor = '// --- Open-Meteo per jam ---'
    assert engine.count(anchor) == 1
    if marker not in engine:
        engine = engine.replace(anchor, (HERE / 'history_seed.js').read_text() + '\n' + anchor, 1)
    else:
        start, end = engine.index(marker), engine.index(anchor)
        engine = engine[:start] + (HERE / 'history_seed.js').read_text() + '\n' + engine[end:]
    old = 'if (!st.hist.has(r[0])) { const a = {};'
    new = 'if (!st.hist.has(r[0]) || (st.sheetHistoryMinutes && st.sheetHistoryMinutes.has(r[0]))) { if (st.sheetHistoryMinutes) st.sheetHistoryMinutes.delete(r[0]); const a = {};'
    if old in engine:
        assert engine.count(old) == 1
        engine = engine.replace(old, new, 1)
    assert new in engine
    old_live = 'if (inMin.length) st.hist.set(m, E.aggregate(inMin));'
    new_live = 'if (inMin.length) { st.hist.set(m, E.aggregate(inMin)); if (st.sheetHistoryMinutes) st.sheetHistoryMinutes.delete(m); }'
    if old_live in engine:
        assert engine.count(old_live) == 1
        engine = engine.replace(old_live, new_live, 1)
    assert new_live in engine
    return engine
