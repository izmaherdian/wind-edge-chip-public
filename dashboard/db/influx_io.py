"""Penulis line protocol ke InfluxDB 2.x lewat HTTP API (tanpa pustaka tambahan selain requests).

Kredensial dibaca dari ~/.config/wind-edge-chip/influx.env (INFLUX_URL, INFLUX_ORG, INFLUX_TOKEN); tidak masuk repo.
"""

import math
import os
from pathlib import Path

import requests

ENV = Path(os.environ.get("WEC_INFLUX_ENV", Path.home() / ".config/wind-edge-chip/influx.env"))


def load_env():
    cfg = {}
    for line in ENV.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip().strip('"').strip("'")
    return cfg


def _esc_key(s):
    return str(s).replace("\\", "\\\\").replace(",", "\\,").replace("=", "\\=").replace(" ", "\\ ")


def _field(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int,)) and not isinstance(v, bool):
        return f"{v}i"
    if isinstance(v, float):
        return repr(v)
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


def line(measurement, tags, fields, t_s):
    """Satu baris line protocol; field NaN/None dibuang. Kembalikan None bila tidak ada field."""
    fs = []
    for k, v in fields.items():
        if v is None or (isinstance(v, float) and not math.isfinite(v)):
            continue
        fs.append(f"{_esc_key(k)}={_field(v)}")
    if not fs:
        return None
    tg = "".join(f",{_esc_key(k)}={_esc_key(v)}" for k, v in sorted(tags.items()) if v not in (None, ""))
    return f"{_esc_key(measurement)}{tg} {','.join(fs)} {int(t_s)}"


class Writer:
    def __init__(self, bucket, cfg=None):
        self.cfg = cfg or load_env()
        self.bucket = bucket
        self.s = requests.Session()
        self.s.headers["Authorization"] = "Token " + self.cfg["INFLUX_TOKEN"]

    def write(self, lines, batch=5000):
        lines = [x for x in lines if x]
        for k in range(0, len(lines), batch):
            r = self.s.post(f"{self.cfg['INFLUX_URL']}/api/v2/write",
                            params={"org": self.cfg["INFLUX_ORG"], "bucket": self.bucket, "precision": "s"},
                            data="\n".join(lines[k:k + batch]).encode(), timeout=60)
            if r.status_code >= 300:
                raise RuntimeError(f"tulis gagal {r.status_code}: {r.text[:300]}")
        return len(lines)
