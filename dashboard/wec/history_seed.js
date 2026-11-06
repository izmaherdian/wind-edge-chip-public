// Merge measured history only. Do not emit predictions, update SoC/evaluations,
// mark historical measurements as live, or overwrite existing MQTT/snapshot data.
if (msg.topic === 'wec/history') {
  const d = msg.payload;
  if (!d || d.source !== 'google-sheet' || !Array.isArray(d.rows) || d.rows.length > 15000) return null;
  const grouped = new Map(), lastClosed = Math.floor(nowMs / MIN) - 1;
  if (!st.sheetHistoryMinutes) st.sheetHistoryMinutes = new Set();
  for (const minute of st.sheetHistoryMinutes) if (minute < lastClosed - 180 || !st.hist.has(minute)) st.sheetHistoryMinutes.delete(minute);
  for (const r of d.rows) {
    const t = r && r.serverTime;
    if (typeof t !== 'number' || !Number.isFinite(t) || t < nowMs - 3 * 3600000 || t > nowMs) continue;
    const minute = Math.floor(t / MIN);
    if (minute > lastClosed || st.hist.has(minute)) continue;
    if (!grouped.has(minute)) grouped.set(minute, []);
    grouped.get(minute).push(E.cleanSample({ ...r, t }));
  }
  for (const [minute, samples] of grouped) { st.hist.set(minute, E.aggregate(samples)); st.sheetHistoryMinutes.add(minute); }
  st.historyRecovery = { source: 'Google Sheets', imported_minutes: grouped.size, loaded_at: nowMs };
  node.status({ fill: 'blue', shape: 'ring', text: `riwayat Sheet: +${grouped.size} menit; live tetap MQTT` });
  return null;
}
