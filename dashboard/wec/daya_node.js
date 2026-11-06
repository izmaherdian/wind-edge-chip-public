// Function node "INA219 -> panel Konsumsi Daya": MQTT WEC/daya dari ESP32 (edge/esp32 env esp32_daya)
// diubah ke format panel template: topic "compute_power", payload { raspberry_pi: {...}, fpga: {...} }.
// Bacaan gagal membatalkan nilai sebelumnya agar tidak tampak LIVE.
let d;
try { d = typeof msg.payload === "string" ? JSON.parse(msg.payload) : msg.payload; } catch (e) { return null; }
if (!d || typeof d !== "object") return null;
// Pemasangan fisik 21 Okt: INA di I2C 18/19 (dikirim firmware sebagai "fpga") terpasang ke Raspberry Pi, dan sebaliknya.
// Ditukar di sini agar firmware tidak perlu di-upload ulang. Ubah ke false bila kabel/firmware sudah disesuaikan.
const TUKAR = true;
// 22 Okt: laptop -> INA -> FPGA sudah dipasang, jadi kedua kanal aktif.
const TERPASANG = { raspberry_pi: true, fpga: true };
if (TUKAR) d = { ...d, raspberry_pi: d.fpga, fpga: d.raspberry_pi };
const ts = typeof d.t === "number" ? d.t : Date.now();
const out = {};
for (const key of ["raspberry_pi", "fpga"]) {
  const x = d[key];
  if (!x) continue;
  const finite = v => typeof v === "number" && Number.isFinite(v);
  const PESAN = { voltage_outside_5v_rail: "tegangan di luar jalur 5 V (cek GND bersama)", power_mismatch: "daya tidak sama dengan V × A",
                  conversion_timeout: "konversi sensor timeout", math_overflow: "arus melebihi rentang sensor" };
  let error = PESAN[x.error] || x.error || "";
  if (x.sensor_ok === false) error = "Sensor tidak terhubung / transaksi I2C gagal.";
  else if (x.measurement_valid === false) error = error || "Konversi sensor tidak valid.";
  else if (![x.voltage_v, x.current_a, x.power_w].every(finite)) error = "Bacaan sensor tidak lengkap.";
  // Also validate legacy firmware, which only reports sensor_ok from begin().
  else if (x.voltage_v < 4 || x.voltage_v > 6) error = "Tegangan di luar rentang pemeriksaan jalur 5 V; periksa INA219 dan ground.";
  else if (x.current_a < -0.01 || x.current_a >= 3.2 || x.power_w < 0) error = "Arus di luar rentang / arah shunt terbalik.";
  else if (Math.abs(x.power_w - x.voltage_v * x.current_a) > 0.03) error = "Daya tidak konsisten dengan tegangan × arus.";
  // Keep current available independently when only bus voltage/power is invalid.
  // Legacy sensor_ok merely confirms startup ACK, so this is not calibration proof.
  const currentAvailable = TERPASANG[key] && x.sensor_ok !== false && finite(x.current_a)
    && x.current_a >= -0.01 && x.current_a < 3.2
    && (!x.error || x.error === "voltage_outside_5v_rail" || x.error === "power_mismatch")
    && !(x.measurement_valid === false && !x.error);
  out[key] = {
    voltage_v: finite(x.voltage_v) ? x.voltage_v : null,
    current_a: finite(x.current_a) ? x.current_a : null,
    current_available: currentAvailable,
    installed: TERPASANG[key],
    current_note: !TERPASANG[key] ? "Kanal INA219 perangkat ini belum dipasang." : currentAvailable ? "Arus INA219; belum diverifikasi alat ukur." : "Pembacaan arus tidak tersedia / tidak valid.",
    power_w: error ? null : x.power_w,
    // Nilai mentah selalu dikirim; panel menampilkannya dengan label "mentah · belum valid" bila ada error.
    raw: { voltage_v: finite(x.voltage_v) ? x.voltage_v : null, current_a: finite(x.current_a) ? x.current_a : null,
           power_w: finite(x.voltage_v) && finite(x.current_a) ? x.voltage_v * x.current_a : null },
    energy_wh: finite(x.energy_wh) ? x.energy_wh : null,
    timestamp: ts, measurement_valid: !error, error
  };
}
if (!Object.keys(out).length) return null;
node.status({ fill: Object.values(out).some(v => !v.current_available) ? "red" : "yellow", shape: "dot", text: Object.entries(out).map(([k, v]) => `${k === "fpga" ? "FPGA" : "RPi"} ${v.current_available ? v.current_a.toFixed(3) + " A (belum diverifikasi)" : "arus tidak valid"}`).join(" · ") });
return { topic: "compute_power", payload: out };
