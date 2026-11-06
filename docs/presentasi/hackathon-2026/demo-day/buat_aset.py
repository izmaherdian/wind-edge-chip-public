"""Bangun aset deck Demo Day: angka, QR, dan gambar TikZ (PDF untuk demoday.tex, PNG untuk demoday.pptx).

1. gambar/angka.tex  <- ml/results/energi_harian.json (ml/common/energi_harian.py) + angka ukur INA219 22 Okt
2. aset/qr-dashboard.png
3. gambar/*.tex (standalone, gaya.tex) -> gambar/*.pdf -> aset/<nama>.png (300 dpi)
Jalankan dari root repo: ml/.venv/bin/python docs/presentasi/hackathon-2026/demo-day/buat_aset.py
"""
import json
import subprocess
from pathlib import Path

import qrcode

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
GAMBAR, ASET = HERE / "gambar", HERE / "aset"
DASHBOARD = "http://citaitb.com:1880/dashboard/hackathon"
# Dashboard 22 Okt (pencatat Raspi, INA219 tanpa multimeter): energi seluruh papan per prediksi (1 per menit).
J_RASPI, J_CHIP = 182.1, 10.44


def koma(x, d=0):
    return f"{x:.{d}f}".replace(".", ",")


def angka():
    e = json.loads((ROOT / "ml/results/energi_harian.json").read_text())
    k = e["konsumsi_komputer"]
    nilai = {
        "energiTurbin": koma(e["median_wh_per_hari"]), "energiQa": koma(e["kuartil_wh_per_hari"][0]),
        "energiQb": koma(e["kuartil_wh_per_hari"][1]), "hariEnergi": str(e["hari_lengkap"]),
        "raspiWh": koma(k["raspi_wh_per_hari"]), "chipWh": koma(k["chip_wh_per_hari"], 1),
        "raspiPersen": koma(k["raspi_persen_median"]), "chipPersen": koma(k["chip_persen_median"], 1),
        "raspiPersenA": koma(k["raspi_persen_rentang_kuartil"][0]), "raspiPersenB": koma(k["raspi_persen_rentang_kuartil"][1]),
        "raspiPersenNum": f'{k["raspi_persen_median"]:.1f}', "chipPersenNum": f'{k["chip_persen_median"]:.1f}',
        "hematKwh": koma(k["hemat_kwh_per_tahun_per_turbin"]), "kaliHemat": koma(J_RASPI / J_CHIP),
        "jRaspi": koma(J_RASPI), "jChip": koma(J_CHIP, 1), "periodeEnergi": e["periode"].replace(" s.d. ", "--"),
    }
    teks = "% Dibuat otomatis oleh buat_aset.py dari ml/results/energi_harian.json; jangan diedit manual.\n"
    teks += "".join(f"\\newcommand{{\\{n}}}{{{v}}}\n" for n, v in nilai.items())
    (GAMBAR / "angka.tex").write_text(teks)
    return nilai


def qr():
    qrcode.make(DASHBOARD, border=1, box_size=12).save(ASET / "qr-dashboard.png")


def gambar():
    for tex in sorted(GAMBAR.glob("*.tex")):
        if tex.name in ("gaya.tex", "angka.tex"):
            continue
        subprocess.run(["latexmk", "-xelatex", "-interaction=nonstopmode", "-halt-on-error", tex.name],
                       cwd=GAMBAR, check=True, capture_output=True)
        subprocess.run(["pdftoppm", "-r", "300", "-png", "-singlefile", tex.with_suffix(".pdf").name,
                        str(ASET / tex.stem)], cwd=GAMBAR, check=True)
        print("gambar:", tex.stem)


if __name__ == "__main__":
    print(angka())
    qr()
    gambar()
