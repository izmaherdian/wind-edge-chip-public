"""Rekam dashboard live (cadangan demo bila internet putus) -> video-dashboard.mp4 + video-dashboard.jpg (poster).

Chrome headless + CDP screencast, halaman digulir: hero -> panel ML -> perbandingan Raspi/chip -> daya -> digital twin.
Rekam saat ESP32-S3 + FPGA dan ESP32 INA219 online, supaya baris "Chip: Tang Nano 4K" dan panel daya terisi.
Pemakaian: ml/.venv/bin/python docs/presentasi/hackathon-2026/demo-day/rekam_dashboard.py [--detik 28] [--keluar video-dashboard]
Butuh: google-chrome, ffmpeg, websocket-client. *.mp4 tidak masuk git.
"""
import argparse
import base64
import json
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

import websocket

HERE = Path(__file__).resolve().parent
URL = "http://citaitb.com:1880/dashboard/hackathon"
PORT = 9381
# (detik mulai, judul panel yang dituju; None = puncak halaman)
ADEGAN = [(0, None), (6, "Prediksi ML"), (12, "Perbandingan Inferensi"), (17, "Daya Perangkat"), (22, "Digital Twin")]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--detik", type=float, default=28)
    ap.add_argument("--keluar", default="video-dashboard")
    a = ap.parse_args()
    kerja = Path(tempfile.mkdtemp(prefix="rekam-"))
    chrome = subprocess.Popen(["google-chrome", "--headless=new", "--no-sandbox", f"--user-data-dir={kerja / 'profil'}",
                               f"--remote-debugging-port={PORT}", f"--remote-allow-origins=http://127.0.0.1:{PORT}",
                               "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--hide-scrollbars", "about:blank"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json")); break
            except OSError:
                time.sleep(0.2)
        ws = websocket.create_connection([t for t in tabs if t["type"] == "page"][0]["webSocketDebuggerUrl"], timeout=60)
        kunci, nomor, bingkai = threading.Lock(), [0], []
        hasil = {}

        def kirim(metode, **p):
            with kunci:
                nomor[0] += 1; i = nomor[0]
                ws.send(json.dumps({"id": i, "method": metode, "params": p}))
            return i

        def penerima():
            while True:
                try:
                    m = json.loads(ws.recv())
                except Exception:
                    return
                if m.get("method") == "Page.screencastFrame":
                    p = m["params"]
                    bingkai.append((p["metadata"]["timestamp"], base64.b64decode(p["data"])))   # waktu render, bukan waktu tiba
                    kirim("Page.screencastFrameAck", sessionId=p["sessionId"])
                elif "id" in m:
                    hasil[m["id"]] = m.get("result", {})

        threading.Thread(target=penerima, daemon=True).start()
        kirim("Emulation.setDeviceMetricsOverride", width=1280, height=720, deviceScaleFactor=1, mobile=False)
        kirim("Page.enable"); kirim("Page.navigate", url=URL)
        time.sleep(22)                                     # data live + replay masuk
        kirim("Page.startScreencast", format="jpeg", quality=85, maxWidth=1280, maxHeight=720, everyNthFrame=1)
        t0 = time.monotonic()
        for mulai, judul in ADEGAN:
            while time.monotonic() - t0 < mulai:
                time.sleep(0.05)
            js = ("window.scrollTo({top: 0, behavior: 'instant'})" if judul is None else
                  "(() => { const h = [...document.querySelectorAll('h2,h3')].find(e => e.innerText.includes(%s));"
                  " if (h) (h.closest('section') || h).scrollIntoView({behavior: 'instant', block: 'start'}); })()" % json.dumps(judul))
            kirim("Runtime.evaluate", expression=js)
        while time.monotonic() - t0 < a.detik:
            time.sleep(0.1)
        kirim("Page.stopScreencast"); time.sleep(3)
        if bingkai:
            awal = bingkai[0][0]
            bingkai = [b for b in bingkai if b[0] - awal <= a.detik]
        # tulis bingkai dengan durasi sebenarnya (screencast hanya mengirim saat layar berubah)
        daftar = []
        for i, (t, data) in enumerate(bingkai):
            f = kerja / f"b{i:05d}.jpg"; f.write_bytes(data)
            akhir = bingkai[i + 1][0] if i + 1 < len(bingkai) else bingkai[0][0] + a.detik
            daftar.append(f"file '{f}'\nduration {max(akhir - t, 0.04):.3f}\n")
        (kerja / "daftar.txt").write_text("".join(daftar) + f"file '{kerja / f'b{len(bingkai) - 1:05d}.jpg'}'\n")
        keluar = HERE / f"{a.keluar}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(kerja / "daftar.txt"),
                        "-vf", "fps=25,format=yuv420p", "-c:v", "libx264", "-crf", "23", "-movflags", "+faststart", str(keluar)], check=True)
        shutil.copy(kerja / "b00000.jpg", HERE / f"{a.keluar}.jpg")
        print(f"{keluar.name}: {len(bingkai)} bingkai, {a.detik:.0f} dtk, {keluar.stat().st_size / 1e6:.1f} MB")
    finally:
        chrome.terminate()
        shutil.rmtree(kerja, ignore_errors=True)


if __name__ == "__main__":
    main()
