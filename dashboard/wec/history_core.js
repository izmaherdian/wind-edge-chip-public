// Read-only Sheet history. WIB parsing is explicit: never use locale date guessing.
function createSheetHistory() {
  const WINDOW_MS = 3 * 3600000, MAX_ROWS = 15000;
  const fields = ['voltage', 'current', 'power', 'energy', 'Windspeed', 'windspeedstation', 'winddirdeg', 'humidity', 'temperature', 'noise', 'rainfall'];
  function timestamp(value) {
    if (typeof value === 'number') return Number.isFinite(value) ? value : null;
    if (typeof value !== 'string') return null;
    const m = value.trim().match(/^(\d{1,2})\/(\d{1,2})\/(\d{4}),?\s+(\d{1,2})[.:](\d{2})[.:](\d{2})$/);
    if (!m) return null;
    const [, day, month, year, hour, minute, second] = m.map(Number);
    const local = Date.UTC(year, month - 1, day, hour, minute, second);
    const d = new Date(local);
    if (d.getUTCFullYear() !== year || d.getUTCMonth() !== month - 1 || d.getUTCDate() !== day || hour > 23 || minute > 59 || second > 59) return null;
    return local - 7 * 3600000;
  }
  function numeric(v) {
    if (v === null || v === undefined || typeof v === 'boolean' || String(v).trim() === '') return null;
    const x = Number(v);
    return Number.isFinite(x) && x >= 0 && x <= 45000 ? x : null;
  }
  function normalize(input, now) {
    const byTime = new Map(); let duplicates = 0, rejected = 0;
    for (const raw of input) {
      if (!Array.isArray(raw)) { rejected++; continue; }
      const t = timestamp(raw[0]);
      if (t === null || t < now - WINDOW_MS || t > now) { rejected++; continue; }
      const row = { serverTime: t, off: String(raw[3]).trim().toUpperCase() === 'OFF' };
      fields.forEach((k, j) => { row[k] = numeric(raw[j + 1]); });
      // Direction has a sensor offset; negative directions except -115 are valid.
      const direction = Number(raw[7]);
      row.winddirdeg = raw[7] !== '' && raw[7] !== null && raw[7] !== undefined && Number.isFinite(direction) && direction !== -115 ? direction : null;
      // The existing writer uses OFF for absent PZEM fields in a weather batch.
      // It is not proof of a stopped turbine: preserve unknown power as null.
      if (row.off) row.power = null;
      row.ML_Status = raw[12] === undefined ? '' : String(raw[12]);
      if (byTime.has(t)) duplicates++;
      byTime.set(t, row);
    }
    return { rows: [...byTime.values()].sort((a, b) => a.serverTime - b.serverTime), duplicates, rejected };
  }
  function minutes(rows) {
    const groups = new Map();
    for (const row of rows) {
      const t = Math.floor(row.serverTime / 60000) * 60000;
      if (!groups.has(t)) groups.set(t, []);
      groups.get(t).push(row);
    }
    return [...groups].map(([serverTime, samples]) => {
      const out = { serverTime, samples: samples.length, ML_Status: samples[samples.length - 1].ML_Status };
      for (const field of fields) {
        const values = samples.map(s => s[field]).filter(v => typeof v === 'number' && Number.isFinite(v));
        out[field] = values.length ? (field === 'energy' ? values[values.length - 1] : values.reduce((a, b) => a + b, 0) / values.length) : null;
      }
      return out;
    }).sort((a, b) => a.serverTime - b.serverTime);
  }
  function range(cursor) {
    if (!Number.isSafeInteger(cursor) || cursor < 2) return null;
    return `Sheet1!A${Math.max(2, cursor - MAX_ROWS + 1)}:M${cursor}`;
  }
  return { WINDOW_MS, MAX_ROWS, timestamp, normalize, minutes, range };
}
if (typeof module !== 'undefined') module.exports = { createSheetHistory };
