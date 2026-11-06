// Four outputs: bounded Sheet read, history chart, ML seed, retained row cursor.
const H = createSheetHistory(), now = Date.now();
const st = context.get('history3h') || { cursor: HISTORY_SEED_ROW, cache: null, lastFetch: 0, inflight: 0, published: 0, lastAppend: 0 };
context.set('history3h', st);
function chart() {
  return st.cache ? { topic: 'wec/history/chart', payload: st.cache } : null;
}
function fetch() {
  if (st.inflight && now - st.inflight < 45000) return null;
  if (now - st.lastFetch < 30000) return null;
  const cells = H.range(st.cursor);
  if (!cells) return null;
  st.inflight = now; st.lastFetch = now;
  node.status({ fill: 'blue', shape: 'ring', text: 'membaca riwayat 3 jam (maks 15.000 baris)' });
  return { topic: 'wec/history/read', cells, _wecHistoryRead: true, _wecHistoryCursor: st.cursor };
}
if (msg.error && msg._wecHistoryRead) {
  st.inflight = 0;
  node.status({ fill: 'red', shape: 'ring', text: 'Sheet belum tersedia; live MQTT tetap berjalan' });
  return [null, chart(), null, null];
}
if (msg._wecHistoryRead) {
  st.inflight = 0;
  if (!Array.isArray(msg.payload) || msg.payload.length > H.MAX_ROWS) return null;
  const clean = H.normalize(msg.payload, now);
  const points = H.minutes(clean.rows);
  st.cache = { source: 'Google Sheets', window_hours: 3, fetched_at: now, rows: points,
    raw_rows: clean.rows.length, duplicates: clean.duplicates, rejected: clean.rejected,
    oldest_at: clean.rows.length ? clean.rows[0].serverTime : null,
    newest_at: clean.rows.length ? clean.rows[clean.rows.length - 1].serverTime : null };
  node.status({ fill: points.length ? 'green' : 'yellow', shape: 'dot', text: `${points.length} menit tercatat / 3 jam` });
  const status = { topic: 'WEC/history/status', retain: true, payload: JSON.stringify({
    window_hours: 3, minute_rows: points.length, raw_rows: clean.rows.length, duplicates: clean.duplicates,
    fetched_at_ms: now, oldest_at_ms: st.cache.oldest_at, newest_at_ms: st.cache.newest_at,
    last_row: msg._wecHistoryCursor, cells: H.range(msg._wecHistoryCursor), source: 'Google Sheets'
  }) };
  return [null, chart(), { topic: 'wec/history', payload: { source: 'google-sheet', rows: clean.rows } }, status];
}
if (msg.topic === 'WEC/history/cursor') {
  let d; try { d = typeof msg.payload === 'string' ? JSON.parse(msg.payload) : msg.payload; } catch (_) { return null; }
  if (!d || d.v !== 1 || !H.range(d.row) || typeof d.t !== 'number' || d.t > now + 60000 || now - d.t > 7 * 86400000) return null;
  if (d.t > (st.cursorAt || 0)) { st.cursor = d.row; st.cursorAt = d.t; }
  return [st.cache ? null : fetch(), null, null, null];
}
// Existing append node already writes live data; observe only its returned range.
// This function never writes to the spreadsheet.
const updated = msg.payload && (msg.payload.updatedRange || (msg.payload.updates && msg.payload.updates.updatedRange));
if (typeof updated === 'string') {
  const match = updated.match(/!?A(\d+):M(\d+)$/);
  if (!match) return null;
  const resumed = st.lastAppend && now - st.lastAppend > 120000;
  st.lastAppend = now; st.cursor = Number(match[2]); st.cursorAt = now;
  const publish = now - st.published >= 60000;
  if (publish) st.published = now;
  const cursor = publish ? { topic: 'WEC/history/cursor', retain: true, payload: JSON.stringify({ v: 1, row: st.cursor, t: now }) } : null;
  const stale = !st.cache || st.cache.newest_at === null || now - st.cache.newest_at > 90000;
  return [resumed || stale ? fetch() : null, null, null, cursor];
}
if (msg.topic === 'wec/history/request' || msg.topic === 'wec/history/refresh') {
  const expired = !st.cache || now - st.cache.fetched_at > 60000;
  return [expired ? fetch() : null, chart(), null, null];
}
return null;
