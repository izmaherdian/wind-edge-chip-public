"""Logger prakiraan cuaca BMKG (API publik, tanpa API key).

BMKG tidak menyediakan arsip prakiraan, jadi skrip ini harus dijalankan berkala
(misalnya cron tiap 3 jam) supaya nanti ada data latih. Setiap pemanggilan menyimpan
respons mentah + waktu ambil ke data/external/bmkg/AAAA-BB-HHTjj.json (tidak masuk git).

Kode adm4 kampus ITB Ganesha: 32.73.02.1006 (Lebak Siliwangi, Coblong), perlu dikonfirmasi.
Contoh cron:  0 */3 * * *  cd /path/repo && ml/.venv/bin/python ml/common/fetch_bmkg.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "external" / "bmkg"
URL = "https://api.bmkg.go.id/publik/prakiraan-cuaca"
ADM4 = "32.73.02.1006"


def main():
    now = datetime.now(timezone.utc)
    try:
        r = requests.get(URL, params={"adm4": ADM4}, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"gagal mengambil BMKG: {e}", file=sys.stderr)
        sys.exit(1)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{now:%Y-%m-%dT%H%M}Z.json"
    path.write_text(json.dumps({"diambil_utc": now.isoformat(), "adm4": ADM4, "respons": r.json()}, ensure_ascii=False))
    print(f"tersimpan: {path}")


if __name__ == "__main__":
    main()
