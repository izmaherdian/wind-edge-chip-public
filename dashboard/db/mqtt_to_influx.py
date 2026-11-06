"""Subscriber MQTT citaitb.com -> InfluxDB lokal (jalan terus; paralel dengan Google Sheets milik Genis).

  TurbinAngin/<besaran>, TurbinAngin2/<besaran>, TurbinAnginESP/<besaran>
                                                 -> bucket turbin, measurement turbin_live (tag turbin=1|2|esp32)
      Satu titik per batch Raspi (±5 detik): topik dikumpulkan, ditulis setelah 1,5 detik tanpa pesan baru.
      "OFF" ditulis sebagai turbin_on=0 dan daya 0 W (aturan sama dengan preprocessing).
  WEC/prediksi, WEC/status, WEC/baterai          -> bucket wec, measurement wec_prediksi|wec_status|wec_baterai
      JSON dari mesin ML Node-RED; waktu dari kolom t (ms).
  WEC/esp32/<nama>                               -> measurement wec_<nama>, tag sumber=esp32 (edge/esp32)

Pemakaian: ml/.venv/bin/python dashboard/db/mqtt_to_influx.py   (biasanya lewat dashboard/db/start.sh)
"""

import os
import json
import sys
import threading
import time
from pathlib import Path

import paho.mqtt.client as mqtt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from influx_io import Writer, line, load_env  # noqa: E402

BROKER, PORT = "citaitb.com", 1883
MQTT_USER, MQTT_PASS = os.environ.get("MQTT_USER", "cita"), os.environ.get("MQTT_PASS", "")
IDLE_S = 1.5
# Pemasangan 21 Okt: INA di I2C 18/19 (label firmware "fpga") terpasang ke Raspberry Pi, dan sebaliknya.
TUKAR_DAYA = True
TURBIN = {"TurbinAngin": "1", "TurbinAngin2": "2", "TurbinAnginESP": "esp32"}   # awalan topik -> tag turbin
# Raspi mengirim voltage/current/power/energy huruf kecil; versi kapital tetap diterima
NAMA = {"voltage": "voltage_v", "current": "current_a", "power": "power_w", "energy": "energy_wh",
        "Voltage": "voltage_v", "Current": "current_a", "Power": "power_w", "Energy": "energy_wh", "Windspeed": "wind_arduino_ms",
        "windspeedstation": "wind_ms", "winddirdeg": "dir_deg", "humidity": "humidity_pct", "temperature": "temp_c",
        "noise": "noise_db", "rainfall": "rain_mm", "ML_Status": "ml_status"}

cfg = load_env()
w_turbin, w_wec = Writer("turbin", cfg), Writer("wec", cfg)
buf, last, lock = {}, {}, threading.Lock()
stat = {"titik": 0, "galat": 0}


def to_field(key, raw):
    s = raw.decode(errors="replace").strip()
    name = NAMA.get(key, key.lower())
    if s.upper() == "OFF":
        return name, "OFF"
    if key == "ML_Status":
        return name, s
    try:
        return name, float(s)
    except ValueError:
        return name + "_teks", s


def flush(turbin, fields, t_s):
    off = any(v == "OFF" for v in fields.values())
    f = {k: v for k, v in fields.items() if v != "OFF"}
    if off:
        f["power_w"] = 0.0
    f["turbin_on"] = 0 if off else (1 if "power_w" in f else None)
    if f.get("dir_deg") == -115.0:          # sentinel stasiun
        f["dir_deg"] = None
    return line("turbin_live", {"turbin": turbin}, f, t_s)


def flusher():
    while True:
        time.sleep(0.5)
        now = time.time()
        out = []
        with lock:
            for tb in [k for k, t in last.items() if now - t > IDLE_S]:
                fields = buf.pop(tb, {})
                last.pop(tb, None)
                if fields:
                    out.append(flush(tb, fields, int(fields.pop("_t"))))
        if out:
            try:
                stat["titik"] += w_turbin.write(out)
            except Exception as e:  # Influx mati sebentar: catat, jalan terus
                stat["galat"] += 1
                print("tulis turbin gagal:", e, flush=True)


def flat(d, pre=""):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(flat(v, f"{pre}{k}_"))
        elif isinstance(v, (int, float, str, bool)) and k != "t":
            out[pre + k] = float(v) if isinstance(v, int) and not isinstance(v, bool) else v
    return out


def on_message(client, userdata, m):
    parts = m.topic.split("/")
    if parts[0] in TURBIN and len(parts) == 2:
        tb = TURBIN[parts[0]]
        name, val = to_field(parts[1], m.payload)
        with lock:
            b = buf.setdefault(tb, {"_t": time.time()})
            b[name] = val
            last[tb] = time.time()
    elif parts[0] == "WEC" and len(parts) in (2, 3):
        try:
            d = json.loads(m.payload)
            t_s = int(d.get("t", time.time() * 1000) / 1000)
            tags = {"sumber": parts[1]} if len(parts) == 3 else {}       # WEC/esp32/<nama> dari edge node
            if parts[-1] == "daya" and TUKAR_DAYA:                         # sama dengan dashboard/wec/daya_node.js
                d["raspberry_pi"], d["fpga"] = d.get("fpga"), d.get("raspberry_pi")
            stat["titik"] += w_wec.write([line("wec_" + parts[-1], tags, flat(d), t_s)])
        except Exception as e:
            stat["galat"] += 1
            print("WEC gagal:", m.topic, e, flush=True)


def on_connect(client, userdata, flags, rc, props=None):
    print("MQTT tersambung:", rc, flush=True)
    for t in [k + "/#" for k in TURBIN] + ["WEC/#"]:
        client.subscribe(t)


if __name__ == "__main__":
    threading.Thread(target=flusher, daemon=True).start()
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"wec-influx-{int(time.time())}")
    c.username_pw_set(MQTT_USER, MQTT_PASS)
    c.on_connect, c.on_message = on_connect, on_message
    c.reconnect_delay_set(1, 60)
    c.connect_async(BROKER, PORT, 30)
    c.loop_start()
    try:
        while True:
            time.sleep(300)
            print(time.strftime("%H:%M:%S"), stat, flush=True)
    except KeyboardInterrupt:
        c.loop_stop()
