# docs/presentasi/ — Deck hackathon dan bahan bersama

| Folder / file | Isi |
|---|---|
| `hackathon-2026/main.tex` | Deck Beamer 16:9 untuk Hackathon 21–23 Okt (bagian utama mengikuti rubrik + lampiran teknis untuk mentoring/QnA) |
| `hackathon-2026/demo-day/` | **Deck Demo Day 23 Okt** (7 menit pitch + live demo, fokus sistem yang dijual): `demoday.tex/pdf` (Beamer) dan `demoday.pptx` (dibangun dari template panitia, isi sama), `naskah.md` (naskah + QnA, juga speaker notes pptx), `cek-angka.md`, `review-juri.md`. Gambar TikZ di `gambar/` (angka otomatis dari `ml/results/energi_harian.json`). Bangun ulang dari root: `ml/.venv/bin/python docs/presentasi/hackathon-2026/demo-day/buat_aset.py`, lalu `latexmk -xelatex demoday.tex` di folder itu, lalu `buat_pptx.py`; rekaman dashboard: `rekam_dashboard.py` |
| `hackathon-2026/template-pitch-deck-demo-day.pptx` | Briefing Demo Day + template pitch deck dari panitia (7 menit pitch + live demo, 5 menit QnA; ringkasan di `docs/guidelines/README.md`) |
| `diagram/*.tex` | Diagram TikZ bersama (dipakai deck dan `docs/laporan-progress/`) |
| `data/` | CSV dan tabel LaTeX yang **dibuat otomatis** oleh `ml/results/plot_data.py`; jangan diedit manual |

Kompilasi:
```
ml/.venv/bin/python ml/results/plot_data.py      # perbarui data grafik dari hasil ML
cd docs/presentasi/hackathon-2026 && latexmk -xelatex main.tex
```

**Slide hasil FPGA:** jalankan `ml/.venv/bin/python ml/results/export_rtl_predictions.py --hw-root <checkout-integrasi>/hw`
dari root repo sebelum kompilasi. Skrip memerlukan `iverilog` dan `vvp`; RTL berasal dari checkout integrasi,
sedangkan bobot dan 597 vektor memakai ekspor model di checkout ini. Testbench `hw/sim/tb_predictions.v`
memeriksa hidden neuron, keluaran, dan 309 siklus, lalu mencatat keluaran simulator per sampel.
Direktori kerja sementara menyediakan nama pendek `vectors.hex`, `weights32.hex`, dan `bias.hex` untuk
menghindari kegagalan baca memori serta pemotongan path pada testbench lama.
Keluaran: `ml/results/fpga_predictions.json` (prediksi, metrik, hash input/RTL), log lokal `.log`,
`gambar/prediksi-rtl.pdf`/`.png`, dan `data/fpga_ringkas.tex`. Grafik memakai seluruh 597 sampel; ini subset
550 indeks acak + 50 target tertinggi setelah deduplikasi, sehingga metriknya berbeda dari seluruh test set.
Tabel sumber daya berasal dari `hw/docs/laporan_chip_fpga_uml.md` di branch integrasi, bagian 5.1:
LUT+ALU 24%, DSP 2/8, BSRAM 1/10, estimasi daya 26,87 mW (dibulatkan 26,9 mW di slide).
Angka daya bukan hasil ukur papan; 309 siklus adalah hasil simulasi yang dijalankan ulang oleh skrip.

**Video:** `hackathon-2026/video-turbin.mp4` tidak masuk git (`*.mp4` diabaikan). Video asli berorientasi portrait dengan metadata rotasi -90°, yang tidak selalu dibaca pemutar PDF. Karena itu video diencode ulang dengan rotasi langsung ditanam di frame (480×848):
```
ffmpeg -i docs/proposal/gambar/video-turbin-dan-sensor-angin.mp4 -c:v libx264 -crf 23 -pix_fmt yuv420p \
       -c:a aac -movflags +faststart -metadata:s:v:0 rotate=0 docs/presentasi/hackathon-2026/video-turbin.mp4
```
Taruh di folder yang sama dengan `main.pdf`. Video tertanam (anotasi `/Movie`) bisa diputar dengan klik di **Okular, Adobe Reader, atau pdfpc**. Di viewer lain hanya tampil poster, jadi pakai tautan cadangan "buka video-turbin.mp4" di slide yang sama, atau putar file-nya langsung.

**Dashboard HMI:** slide 6 berisi tautan `http://citaitb.com:1880/dashboard` (juga lewat IP `103.102.153.154`) dan QR code-nya (sudah diuji terbaca). Dashboard bisa dibuka publik tanpa login.
