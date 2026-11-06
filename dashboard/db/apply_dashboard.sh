#!/usr/bin/env bash
# Pasang/perbarui dashboard InfluxDB dari dashboard.yml (lewat stack "wec", jadi tidak dobel saat diulang).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
INFLUX="${INFLUX_HOME:-$HOME/tools/influxdb}/bin/influx"
set -a; . "$HOME/.config/wind-edge-chip/influx.env"; set +a
A=(--host "$INFLUX_URL" --token "$INFLUX_TOKEN" --org "$INFLUX_ORG")

"$INFLUX" template validate -f "$HERE/dashboard.yml"
STACK=$("$INFLUX" stacks "${A[@]}" --stack-name wec --json | python3 -I -c "import json,sys; d=json.load(sys.stdin); print(d[0]['id'] if d else '')")
if [ -z "$STACK" ]; then
    STACK=$("$INFLUX" stacks init "${A[@]}" --stack-name wec --json | python3 -I -c "import json,sys; print(json.load(sys.stdin)['id'])")
fi
"$INFLUX" apply "${A[@]}" --stack-id "$STACK" -f "$HERE/dashboard.yml" --force yes </dev/null >/dev/null   # tanpa stdin: jangan menunggu konfirmasi
echo "dashboard terpasang (stack $STACK): $INFLUX_URL -> Dashboards -> 'Wind Edge Chip · Turbin 1'"
