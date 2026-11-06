#!/usr/bin/env bash
# Jalankan InfluxDB lokal + subscriber MQTT (untuk demo di laptop). Aman dijalankan ulang.
#   dashboard/db/start.sh         # start
#   dashboard/db/start.sh stop    # hentikan keduanya
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
INFLUX_HOME="${INFLUX_HOME:-$HOME/tools/influxdb}"
LOG="$INFLUX_HOME/data"
PY="$REPO/ml/.venv/bin/python"

if [ "${1:-}" = "stop" ]; then
    pkill -f "dashboard/db/mqtt_to_influx.py" && echo "subscriber dihentikan" || true
    pkill -x influxd && echo "influxd dihentikan" || true
    exit 0
fi

if ! curl -sf -m 3 http://127.0.0.1:8086/health >/dev/null; then
    cd "$INFLUX_HOME"
    nohup bin/influxd --bolt-path data/influxd.bolt --engine-path data/engine \
        --http-bind-address 127.0.0.1:8086 --reporting-disabled >>"$LOG/influxd.log" 2>&1 &
    for _ in $(seq 30); do curl -sf -m 2 http://127.0.0.1:8086/health >/dev/null && break; sleep 1; done
fi
curl -sf -m 3 http://127.0.0.1:8086/health >/dev/null && echo "influxd siap: http://127.0.0.1:8086"

if pgrep -f "dashboard/db/mqtt_to_influx.py" >/dev/null; then
    echo "subscriber sudah berjalan"
else
    nohup "$PY" "$REPO/dashboard/db/mqtt_to_influx.py" >>"$LOG/mqtt_to_influx.log" 2>&1 &
    echo "subscriber dijalankan (log: $LOG/mqtt_to_influx.log)"
fi
