"""Bangun demoday.pptx dari template panitia (master, logo, Tahoma tetap); isi sama dengan demoday.tex.

Teks berupa shape asli (bisa diedit). Gambar TikZ dari aset/*.png (buat_aset.py); lampiran diagram LaTeX
(arsitektur, chip, benchmark) dipotong dari halaman demoday.pdf. Catatan pembicara dari naskah.md ("## Slide N").
Urutan: ml/.venv/bin/python .../demo-day/buat_aset.py -> latexmk -xelatex demoday.tex -> buat_pptx.py
"""
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

HERE = Path(__file__).resolve().parent
ASET = HERE / "aset"
FOTO = HERE.parents[2] / "proposal" / "gambar" / "foto-turbin-atap.jpeg"
TEMPLATE = HERE.parent / "template-pitch-deck-demo-day.pptx"
OUT = HERE / "demoday.pptx"
VIDEO = {"turbin": (HERE.parent / "video-turbin.mp4", HERE.parent / "poster-video.jpg"),
         "dashboard": (HERE / "video-dashboard.mp4", HERE / "video-dashboard.jpg"),
         "chip": (HERE / "video-chip.mp4", HERE / "video-chip.jpg")}

GELAP, TEAL, AMBER, MUDA, ABU, TEKS, PUTIH = "15242B", "285052", "E8A317", "DCE8E8", "8A9499", "1E2B30", "FFFFFF"
FONT = "Tahoma"
ATAS, BAWAH, W = 0.99, 6.93, 13.333     # pita konten di antara header logo dan footer mitra (inci)


def rgb(h):
    return RGBColor.from_string(h)


def kotak(sl, x, y, w, h, isi=None, garis=None, bulat=False, gradien=None, putus=False):
    s = sl.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if bulat else MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    if bulat:
        s.adjustments[0] = 0.06
    if gradien:
        s.fill.gradient(); s.fill.gradient_angle = 0
        s.fill.gradient_stops[0].color.rgb = rgb(gradien[0]); s.fill.gradient_stops[1].color.rgb = rgb(gradien[1])
    elif isi:
        s.fill.solid(); s.fill.fore_color.rgb = rgb(isi)
    else:
        s.fill.background()
    if garis:
        s.line.color.rgb = rgb(garis); s.line.width = Pt(1.5)
        if putus:
            s.line.dash_style = 4
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    return s


def teks(sl, x, y, w, h, paragraf, ukuran=16, warna=TEKS, rata=PP_ALIGN.LEFT, jangkar=MSO_ANCHOR.TOP, spasi=1.0, shape=None, margin=0.05):
    """paragraf: list; item = str, list run (teks, opsi), atau dict {'p': runs, 'size', 'color', 'bold', 'rata', 'sebelum'}."""
    s = shape or sl.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = s.text_frame
    tf.word_wrap = True; tf.vertical_anchor = jangkar
    for sisi in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, sisi, Inches(margin))
    for i, par in enumerate(paragraf):
        o = par if isinstance(par, dict) else {"p": par}
        runs = [(o["p"], {})] if isinstance(o["p"], str) else o["p"]
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = o.get("rata", rata); p.line_spacing = o.get("spasi", spasi)
        if o.get("sebelum"):
            p.space_before = Pt(o["sebelum"])
        for t, ro in runs:
            r = p.add_run(); r.text = t
            f = r.font; f.name = FONT; f.size = Pt(ro.get("size", o.get("size", ukuran)))
            f.bold = ro.get("bold", o.get("bold", False)); f.italic = ro.get("italic", False)
            f.color.rgb = rgb(ro.get("color", o.get("color", warna)))
    return s


def gambar(sl, path, x, y, w, h):
    """Pasang gambar di kotak (x, y, w, h) inci, rasio dijaga, rata tengah."""
    iw, ih = Image.open(path).size
    sk = min(w / iw, h / ih)
    gw, gh = iw * sk, ih * sk
    return sl.shapes.add_picture(str(path), Inches(x + (w - gw) / 2), Inches(y + (h - gh) / 2), Inches(gw), Inches(gh))


def logo(sl, x, y, h):
    iw, ih = Image.open(ASET / "logo-cita.png").size
    w = h * iw / ih
    kotak(sl, x, y, w + 0.08, h + 0.08, isi=PUTIH, bulat=True)
    sl.shapes.add_picture(str(ASET / "logo-cita.png"), Inches(x + 0.04), Inches(y + 0.04), Inches(w), Inches(h))


def judul(sl, kicker, judul_teks, rubrik=None):
    teks(sl, 0.45, 1.06, 8.6, 0.32, [[(kicker, {"bold": True, "color": AMBER})]], ukuran=11)
    if rubrik:
        teks(sl, 7.4, 1.06, 5.5, 0.32, [[("Rubrik: " + rubrik, {"color": ABU})]], ukuran=10, rata=PP_ALIGN.RIGHT)
    teks(sl, 0.45, 1.32, 12.4, 0.62, [[(judul_teks, {"bold": True, "color": GELAP})]], ukuran=28)


def kaki(sl, nomor):
    logo(sl, 0.2, 7.04, 0.2)
    teks(sl, 1.35, 7.03, 3.0, 0.3, [[("Tim Chitato • Wind Edge Chip", {"color": PUTIH})]], ukuran=9)
    teks(sl, 12.4, 7.03, 0.7, 0.3, [[(str(nomor), {"color": PUTIH, "bold": True})]], ukuran=9, rata=PP_ALIGN.RIGHT)


def pita_gelap(sl):
    kotak(sl, 0, ATAS, W, BAWAH - ATAS, gradien=(GELAP, TEAL))


def video(sl, nama, x, y, w, h, placeholder):
    vid, poster = VIDEO[nama]
    if vid.exists():
        if not poster.exists():
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(vid), "-frames:v", "1", str(poster)], check=True)
        sl.shapes.add_movie(str(vid), Inches(x), Inches(y), Inches(w), Inches(h), poster_frame_image=str(poster), mime_type="video/mp4")
    else:
        k = kotak(sl, x, y, w, h, garis=ABU, bulat=True, putus=True)
        teks(sl, 0, 0, 0, 0, [{"p": placeholder, "rata": PP_ALIGN.CENTER}], ukuran=12, warna=ABU, jangkar=MSO_ANCHOR.MIDDLE, shape=k)


def potong_pdf(halaman, tujuan):
    """Ambil area konten (di bawah judul, di atas footer) dari halaman demoday.pdf."""
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["pdftoppm", "-r", "200", "-png", "-singlefile", "-f", str(halaman), "-l", str(halaman),
                        str(HERE / "demoday.pdf"), f"{d}/h"], check=True)
        im = Image.open(f"{d}/h.png"); w, h = im.size
        im.crop((int(0.02 * w), int(0.325 * h), int(0.98 * w), int(0.915 * h))).save(tujuan)


def catatan():
    out, cur = {}, None
    for baris in (HERE / "naskah.md").read_text().splitlines():
        m = re.match(r"## Slide (\d+)", baris)
        if m:
            cur = int(m.group(1)); out[cur] = [baris[3:]]
        elif baris.startswith("## "):
            cur = None
        elif cur:
            out[cur].append(baris)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def halaman_lampiran():
    """Nomor halaman lampiran di demoday.pdf menurut judulnya."""
    txt = subprocess.run(["pdftotext", "-layout", str(HERE / "demoday.pdf"), "-"], capture_output=True, text=True, check=True).stdout
    hal = {}
    for i, isi in enumerate(txt.split("\f"), 1):
        for kunci in ("Arsitektur teknis", "akselerator MAC4", "Perbandingan metode prediksi"):
            if kunci in isi and "LAMPIRAN" in isi:
                hal[kunci] = i
    return hal


def main():
    prs = Presentation(TEMPLATE)
    daftar = prs.slides._sldIdLst
    for sid in list(daftar):                      # buang 11 slide contoh, master tetap
        prs.part.drop_rel(sid.rId); daftar.remove(sid)
    kosong = prs.slide_layouts[6]
    slides = []

    def baru():
        sl = prs.slides.add_slide(kosong); slides.append(sl); return sl

    # 1 JUDUL -----------------------------------------------------------
    sl = baru(); pita_gelap(sl)
    lf = 5.6
    p = sl.shapes.add_picture(str(FOTO), Inches(W - lf), Inches(ATAS), Inches(lf))
    tampak = (BAWAH - ATAS) / (lf * 1280 / 960)
    p.crop_top, p.crop_bottom = 0.02, 1 - tampak - 0.02; p.height = Inches(BAWAH - ATAS)
    kotak(sl, W - lf - 0.05, ATAS, 0.05, BAWAH - ATAS, isi=AMBER)
    logo(sl, 0.6, 1.25, 0.42)
    teks(sl, 0.6, 1.85, 7.0, 4.6, [
        [("DEEPTECH FOR SMART-X HACKATHON 2026 • RENEWABLE ENERGY", {"bold": True, "color": AMBER, "size": 11})],
        {"p": [("Tim Chitato:", {"bold": True, "color": PUTIH, "size": 20})], "sebelum": 10},
        [("Wind Edge Chip", {"bold": True, "color": PUTIH, "size": 44})],
        {"p": [("Sistem pintar ", {}), ("hemat daya", {"bold": True, "color": AMBER}),
               (" untuk turbin angin: chip rancangan sendiri yang memprediksi, mengatur baterai*, dan menjaga turbin.", {})],
         "size": 18, "color": PUTIH, "sebelum": 8},
        {"p": [("Anggota: ", {"bold": True}), ("Izma Alhazmi Herdian (ketua) • Genis Gusvian Hartanto • Alif Muhammad Rizky • Shania Argiliana", {})],
         "size": 12, "color": MUDA, "sebelum": 16},
        {"p": [("Pembimbing: ", {"bold": True}), ("Ir. Estiyanti Ekawati, M.T., Ph.D.", {})], "size": 12, "color": MUDA},
        {"p": "* kontrol baterai: pengembangan selanjutnya", "size": 10, "color": MUDA, "sebelum": 6},
    ])
    teks(sl, 0.6, 6.45, 6.0, 0.35, ["Institut Teknologi Bandung | 21–23 Oktober 2026"], ukuran=11, warna=MUDA)
    lb = kotak(sl, W - 4.05, BAWAH - 0.5, 3.9, 0.34, isi=AMBER)
    teks(sl, 0, 0, 0, 0, [[("LIVE • turbin atap Gedung CRIMSE ITB", {"bold": True, "color": GELAP})]], ukuran=12,
         rata=PP_ALIGN.CENTER, jangkar=MSO_ANCHOR.MIDDLE, shape=lb)

    # 2 KONDISI SAAT INI -------------------------------------------------
    sl = baru(); judul(sl, "01 • KONDISI SAAT INI", "Turbin butuh “otak” pengatur energi", "problem-solution fit 20%"); kaki(sl, 2)
    video(sl, "turbin", 0.6, 2.05, 2.5, 4.45, "video turbin")
    teks(sl, 0.4, 6.52, 2.9, 0.35, [{"p": "turbin TA kami, atap CRIMSE ITB", "rata": PP_ALIGN.CENTER}], ukuran=10, warna=ABU)
    for i, (bg, fg, kc, a, b) in enumerate([(MUDA, TEKS, TEAL, "Energi angin tumbuh", "RUPTL 2025–2034 menargetkan +7,2 GW pembangkit angin; PLTB kecil dipasang di rumah, kawasan, dan daerah terpencil"),
                                           ("F7DFA6", TEKS, GELAP, "Turbin perlu dipantau dan diatur", "kapan mengisi baterai, kapan membuang kelebihan ke dump load, kapan memakai PLN"),
                                           (GELAP, PUTIH, AMBER, "Di turbin TA kami (sejak Maret 2026)", "“otaknya” Raspberry Pi 4 + internet + Google Sheets; keluaran ke dump load 35 Ω, berikutnya baterai 12 V 50 Ah")]):
        k = kotak(sl, 3.6, 2.05 + i * 1.6, 9.3, 1.45, isi=bg, bulat=True)
        teks(sl, 0, 0, 0, 0, [[(a, {"bold": True, "color": kc, "size": 17})], {"p": b, "sebelum": 3}], ukuran=14, warna=fg,
             shape=k, margin=0.15, jangkar=MSO_ANCHOR.MIDDLE)

    # 3 PROBLEM ---------------------------------------------------------
    sl = baru(); judul(sl, "02 • PROBLEM", "Masalahnya: “otak” turbin mahal, boros, rapuh", "problem-solution fit 20%"); kaki(sl, 3)
    gambar(sl, ASET / "anggaran.png", 1.2, 2.0, 10.9, 2.75)
    for i, (a, b) in enumerate([("Mahal", "Satu set komputer mini ±Rp3,3 jt per turbin."),
                                ("Boros", "Memakan ≈¼ energi turbin saat angin ringan, padahal tugasnya hanya mencatat dan memprediksi."),
                                ("Rapuh", "Internet putus → Raspi reboot, data dan prediksi hilang (2.787 kali, Apr–Okt).")]):
        teks(sl, 0.55 + i * 4.15, 4.95, 3.9, 1.9, [[(a, {"bold": True, "color": GELAP, "size": 17})], {"p": b, "sebelum": 3}], ukuran=15)

    # 4 PROBLEM STATEMENT -----------------------------------------------
    sl = baru(); pita_gelap(sl)
    teks(sl, 1.3, 1.2, 8, 0.35, [[("03 • PROBLEM STATEMENT", {"bold": True, "color": AMBER})]], ukuran=12)
    teks(sl, 0.35, 1.4, 1.0, 1.2, [[("“", {"bold": True, "color": AMBER})]], ukuran=72)
    teks(sl, 1.3, 1.75, 11.4, 3.6, [[("Bagaimana membuat “otak” turbin yang ", {}), ("murah", {"color": AMBER}), (", ", {}), ("hemat daya", {"color": AMBER}),
                                     (", tetap jalan ", {}), ("tanpa internet", {"color": AMBER}), (", dan bisa ", {}), ("mengatur baterai", {"color": AMBER}), ("?", {})]],
         ukuran=32, warna=PUTIH, spasi=1.1)
    for par in sl.shapes[-1].text_frame.paragraphs:
        for r in par.runs:
            r.font.bold = True
    kotak(sl, 1.3, 5.9, 1.6, 0.04, isi=AMBER)
    teks(sl, 1.3, 6.0, 11.5, 0.8, [[("Siapa: ", {"bold": True}), ("pemilik PLTB rumah menengah ke atas dan perusahaan dengan banyak turbin     •     ", {}),
                                    ("Kendala: ", {"bold": True}), ("komputer mahal dan boros, internet putus, angin tak pasti", {})]], ukuran=13, warna=MUDA)

    # 5-8 diagram penuh -----------------------------------------------------
    for nomor, (kick, jud, rub, png) in enumerate([
            ("04 • PILIHAN TEKNOLOGI", "Kenapa ESP32 + chip FPGA, bukan komputer mini?", "inovasi 15% • TKDN 10%", "banding.png"),
            ("05 • SOLUTION", "Sistem kami: Wind Edge Kit + Platform", "inovasi 15% • fungsional 25%", "sistem.png"),
            ("06 • PRODUK", "Yang kami jual: sistem, bukan turbin", "hilirisasi 10%", "paket.png"),
            ("07 • CARA SISTEM BEKERJA UNTUK PELANGGAN", "Satu hari bersama Wind Edge Chip", "dampak 15%", "alur.png")], 5):
        sl = baru(); judul(sl, kick, jud, rub); kaki(sl, nomor)
        gambar(sl, ASET / png, 0.45, 2.0, 12.45, 4.85)

    # 9 DEMO ------------------------------------------------------------
    sl = baru(); judul(sl, "08 • LIVE DEMO • 2 MENIT", "Demo live: sistem jalan sekarang", "fungsional prototipe 25%"); kaki(sl, 9)
    langkah = [("Dashboard", ": turbin detik ini dan prediksi 1 jam."), ("Chip di plant", ": terpasang di turbin, menjawab tiap menit, “identik dengan CPU”."),
               ("Baterai* & status", ": isi baterai 1 jam lagi, kondisi turbin."), ("Hemat daya", ": Raspberry Pi vs chip, diukur live.")]
    teks(sl, 0.5, 2.1, 6.2, 2.9, [{"p": [(f"{i + 1}.  ", {"bold": True, "color": TEAL}), (a, {"bold": True}), (b, {})], "sebelum": 0 if i == 0 else 8}
                                  for i, (a, b) in enumerate(langkah)], ukuran=17)
    gambar(sl, ASET / "qr-dashboard.png", 0.55, 5.1, 1.6, 1.6)
    teks(sl, 2.3, 5.2, 4.2, 1.4, ["pindai untuk ikut membuka di ponsel", {"p": "citaitb.com:1880/dashboard/hackathon", "size": 11, "color": TEAL, "sebelum": 4}], ukuran=13)
    teks(sl, 0.5, 6.72, 6.2, 0.3, ["* Pengembangan selanjutnya. Saat ini: prediksi live, baterai masih simulasi di dashboard."], ukuran=10, warna=ABU)
    for i, (nama, jud, ket) in enumerate([("dashboard", "Rekaman dashboard", "cadangan bila internet putus (20 detik, klik untuk memutar)"),
                                          ("chip", "Papan chip di plant", "ESP32-S3 + Tang Nano 4K FPGA + sensor daya INA219")]):
        video(sl, nama, 6.75, 2.0 + i * 2.4, 4.0, 2.25, jud)
        teks(sl, 10.9, 2.0 + i * 2.4, 2.1, 2.25, [[(jud, {"bold": True, "size": 13})], {"p": ket, "size": 11, "color": ABU, "sebelum": 3}],
             ukuran=12, jangkar=MSO_ANCHOR.MIDDLE)

    # 10 BUKTI ----------------------------------------------------------
    sl = baru(); judul(sl, "09 • BUKTI", "Bukan janji: sudah diukur", "fungsional 25% • problem-solution fit 20%"); kaki(sl, 10)
    gambar(sl, ASET / "bukti.png", 0.45, 2.15, 12.45, 3.6)
    teks(sl, 0.45, 6.05, 12.45, 0.5, [{"p": "Prediksi chip mengikuti daya aktual turbin (lampiran) • angka lengkap dan sumbernya di lampiran", "rata": PP_ALIGN.CENTER}], ukuran=14)

    # 11 LEBIH MURAH, LEBIH BANYAK ENERGI --------------------------------------------------
    sl = baru(); judul(sl, "10 • BISNIS", "Lebih murah, lebih banyak energi", "hilirisasi 10% • dampak 15%"); kaki(sl, 11)
    gambar(sl, ASET / "uang.png", 0.45, 1.95, 12.45, 4.95)

    # 12 PASAR ----------------------------------------------------------
    sl = baru(); judul(sl, "11 • PASAR", "Mulai dari rumah, berkembang ke armada", "hilirisasi 10% • dampak 15%"); kaki(sl, 12)
    gambar(sl, ASET / "pasar.png", 0.45, 2.0, 12.45, 4.05)
    teks(sl, 0.45, 6.2, 12.45, 0.55, [{"p": [("Pendapatan: ", {"bold": True, "color": TEAL}),
                                             ("Edge Kit (sekali beli) • langganan Platform per turbin • layanan pemasangan & integrasi PLTS", {})], "rata": PP_ALIGN.CENTER}], ukuran=15)

    # 13 KENAPA KAMI ----------------------------------------------------
    sl = baru(); judul(sl, "12 • INOVASI, TKDN & PETA JALAN", "Kenapa kami, dan langkah berikutnya", "inovasi 15% • TKDN 10%"); kaki(sl, 13)
    for i, (bg, fg, kc, a, b) in enumerate([(GELAP, PUTIH, AMBER, "Chip & IP sendiri", "RTL, firmware, model: TKDN, jalur ke ASIC"),
                                           (TEAL, PUTIH, AMBER, "Tanpa internet", "prediksi & kontrol* tetap jalan di turbin"),
                                           (MUDA, TEKS, TEAL, "Satu kit lengkap", "sensor sampai dashboard + digital twin"),
                                           ("F7DFA6", TEKS, GELAP, "Pengaman bawaan*", "baterai & generator dijaga otomatis")]):
        k = kotak(sl, 0.45 + i * 3.15, 2.05, 2.95, 1.45, isi=bg, bulat=True)
        teks(sl, 0, 0, 0, 0, [[(a, {"bold": True, "color": kc, "size": 15})], {"p": b, "sebelum": 2}], ukuran=13, warna=fg, shape=k, margin=0.12,
             jangkar=MSO_ANCHOR.MIDDLE)
    gambar(sl, ASET / "peta.png", 0.9, 3.65, 11.5, 2.95)
    teks(sl, 0.45, 6.62, 12.4, 0.3, ["* Pengembangan selanjutnya. Saat ini: prediksi live, baterai masih simulasi di dashboard."], ukuran=10, warna=ABU)

    # 12 PENUTUP --------------------------------------------------------
    sl = baru(); pita_gelap(sl)
    teks(sl, 0.8, 1.2, 8, 0.35, [[("RINGKASAN", {"bold": True, "color": AMBER})]], ukuran=12)
    teks(sl, 0.8, 1.5, 8.8, 1.7, [[("Otak hemat daya", {"bold": True, "color": PUTIH})], [("di setiap turbin.", {"bold": True, "color": AMBER})]], ukuran=40, spasi=0.95)
    teks(sl, 0.8, 3.3, 8.8, 2.0, [
        [("✓ ", {"color": AMBER}), ("Sistem lengkap", {"bold": True}), (": Edge Kit + Platform + Layanan.", {})],
        {"p": [("✓ ", {"color": AMBER}), ("17× lebih hemat", {"bold": True}), (", hasil chip identik, jalan di turbin nyata.", {})], "sebelum": 6},
        {"p": [("✓ ", {"color": AMBER}), ("Mulai dari ", {}), ("rumah", {"bold": True}), (", berkembang ke ", {}), ("armada B2B", {"bold": True}),
               (" dan ", {}), ("hybrid PLTS", {"bold": True}), (".", {})], "sebelum": 6},
    ], ukuran=17, warna=PUTIH)
    teks(sl, 0.8, 5.35, 8.9, 1.5, [[("Tim Chitato: ", {"bold": True, "color": PUTIH}), ("“Angin boleh berubah, keputusanmu tidak lagi menebak.”", {"bold": True, "italic": True, "color": PUTIH})],
                                   {"p": "Izma Alhazmi Herdian • Genis Gusvian Hartanto • Alif Muhammad Rizky • Shania Argiliana", "sebelum": 5},
                                   "Pembimbing: Ir. Estiyanti Ekawati, M.T., Ph.D."], ukuran=12, warna=MUDA)
    kotak(sl, 10.15, 1.5, 2.3, 2.3, isi=PUTIH, bulat=True)
    gambar(sl, ASET / "qr-dashboard.png", 10.25, 1.6, 2.1, 2.1)
    teks(sl, 9.6, 3.9, 3.4, 0.7, [{"p": "Dashboard live", "rata": PP_ALIGN.CENTER}, {"p": "citaitb.com:1880/dashboard/hackathon", "rata": PP_ALIGN.CENTER, "size": 10}], ukuran=12, warna=PUTIH)
    logo(sl, 10.2, 4.8, 0.42)

    # LAMPIRAN ----------------------------------------------------------
    no = 15
    sl = baru(); judul(sl, "LAMPIRAN A", "Angka lengkap dan sumbernya"); kaki(sl, no); no += 1
    import json
    e = json.loads((HERE.parents[3] / "ml/results/energi_harian.json").read_text()); k = e["konsumsi_komputer"]
    data = [["Besaran", "Nilai", "Sumber"],
            ["Energi turbin per hari", f"median {e['median_wh_per_hari']:.0f} Wh (separuh hari {e['kuartil_wh_per_hari'][0]:.0f}–{e['kuartil_wh_per_hari'][1]:.0f} Wh)", f"register PZEM bersih, {e['hari_lengkap']} hari"],
            ["Raspberry Pi / papan chip", "2,96 W / 0,17 W", "INA219 22 Okt, rata-rata seluruh papan, tanpa multimeter"],
            ["Porsi energi turbin untuk komputer", f"Raspi {k['raspi_persen_median']:.0f}% ({k['raspi_persen_rentang_kuartil'][0]:.0f}–{k['raspi_persen_rentang_kuartil'][1]:.0f}%), chip {k['chip_persen_median']:.1f}%".replace(".", ","), f"{k['raspi_wh_per_hari']:.0f} Wh vs {k['chip_wh_per_hari']:.1f} Wh per hari".replace(".", ",")],
            ["Energi per prediksi", "182 J vs 10,4 J (≈17×)", "pencatat Raspi 22 Okt, 1 prediksi per menit"],
            ["Hemat per turbin", f"≈{k['hemat_kwh_per_tahun_per_turbin']:.0f} kWh per tahun", "(2,96 − 0,17) W × 24 jam × 365"],
            ["Inferensi chip identik", "5.373/5.373, 309 siklus", "uji HIL 21 Okt"],
            ["Akurasi prediksi 1 jam", "MAE 5,48 W vs persistence 8,67 W (−37%)", "uji 1–20 Okt"],
            ["Tahan gangguan", "sensor daya mati: MAE 5,14 W (normal 5,07 W); 20% data hilang: prediksi ada 97,7% waktu", "tes test_tanpa_pzem.js, test_celah.js"],
            ["Raspi reboot karena internet", "2.787 kali (Apr–Okt)", "log_reboot.txt Raspi"]]
    t = sl.shapes.add_table(len(data), 3, Inches(0.45), Inches(2.0), Inches(12.4), Inches(4.6)).table
    for j, lw in enumerate((3.6, 5.0, 3.8)):
        t.columns[j].width = Inches(lw)
    for i, baris in enumerate(data):
        for j, v in enumerate(baris):
            c = t.cell(i, j); c.fill.solid(); c.fill.fore_color.rgb = rgb(MUDA if i == 0 else PUTIH)
            c.margin_top = c.margin_bottom = Inches(0.02)
            p = c.text_frame.paragraphs[0]; p.text = ""; r = p.add_run(); r.text = v
            r.font.name = FONT; r.font.size = Pt(11); r.font.bold = i == 0; r.font.color.rgb = rgb(TEKS)
    for kick, jud, png in [("LAMPIRAN B", "Energi harian turbin (median per bulan)", "energi.png"),
                           ("LAMPIRAN C", "Contoh prediksi 1 jam: chip vs daya aktual", "prediksi.png"),
                           ("LAMPIRAN C2", "Alur data dan database", "alurdata.png")]:
        sl = baru(); judul(sl, kick, jud); kaki(sl, no); no += 1
        gambar(sl, ASET / png, 0.45, 2.0, 12.45, 4.4 if kick == "LAMPIRAN B" else 4.85)
        if kick == "LAMPIRAN B":
            teks(sl, 0.45, 6.4, 12.45, 0.5, [{"p": "“Total Energy” di dashboard = register PZEM sejak reset terakhir, bukan per hari. Energi harian = kenaikan register yang dibersihkan; pada data tanpa celah sama dengan integrasi daya (rasio 1,01).", "rata": PP_ALIGN.CENTER}], ukuran=11)
    hal = halaman_lampiran()
    for kunci, kick, jud in [("Arsitektur teknis", "LAMPIRAN D", "Arsitektur teknis"), ("akselerator MAC4", "LAMPIRAN E", "Chip: akselerator MAC4 rancangan sendiri"),
                             ("Perbandingan metode prediksi", "LAMPIRAN F", "Perbandingan metode prediksi (uji 1–20 Okt)")]:
        if kunci not in hal:
            continue
        png = ASET / f"lampiran-{kick[-1].lower()}.png"
        potong_pdf(hal[kunci], png)
        sl = baru(); judul(sl, kick, jud); kaki(sl, no); no += 1
        gambar(sl, png, 0.45, 2.0, 12.45, 4.85)
    sl = baru(); judul(sl, "LAMPIRAN G", "Inferensi live: Raspberry Pi vs chip"); kaki(sl, no)
    gambar(sl, ASET / "dash-banding.png", 1.4, 2.0, 10.5, 2.4)
    gambar(sl, ASET / "dash-daya.png", 1.4, 4.5, 10.5, 2.3)

    notes = catatan()
    for i, s in enumerate(slides, 1):
        if i in notes:
            s.notes_slide.notes_text_frame.text = notes[i]
    prs.save(OUT)
    print("tersimpan:", OUT.name, len(slides), "slide")


if __name__ == "__main__":
    main()
