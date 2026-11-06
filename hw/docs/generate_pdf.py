import os
import math
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon, Circle


class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        if self._pageNumber > 1:
            self.setFont("Times-Roman", 10)
            text = f"Halaman {self._pageNumber} dari {page_count}"
            self.drawRightString(A4[0] - 2.8*cm, 1.8*cm, text)


def add_arrow(d, x1, y1, x2, y2, color=colors.HexColor('#222222'), stroke=0.9, head_len=0.17*cm, head_w=0.085*cm, dashed=False):
    line = Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=stroke)
    if dashed:
        line.strokeDashArray = [3, 2]
    d.add(line)
    angle = math.atan2(y2 - y1, x2 - x1)
    bx = x2 - head_len * math.cos(angle)
    by = y2 - head_len * math.sin(angle)
    px1 = bx + head_w * math.sin(angle)
    py1 = by - head_w * math.cos(angle)
    px2 = bx - head_w * math.sin(angle)
    py2 = by + head_w * math.cos(angle)
    d.add(Polygon([x2, y2, px1, py1, px2, py2], fillColor=color, strokeColor=color, strokeWidth=0.4))


def add_uml_port(d, x, y, size=0.20*cm, fill=colors.white, stroke=colors.HexColor('#1F3A60')):
    d.add(Rect(x - size/2, y - size/2, size, size, fillColor=fill, strokeColor=stroke, strokeWidth=0.8))


def add_uml_component_icon(d, x, y):
    d.add(Rect(x, y, 0.30*cm, 0.36*cm, fillColor=colors.white, strokeColor=colors.HexColor('#285591'), strokeWidth=0.6))
    d.add(Rect(x - 0.08*cm, y + 0.21*cm, 0.16*cm, 0.07*cm, fillColor=colors.white, strokeColor=colors.HexColor('#285591'), strokeWidth=0.6))
    d.add(Rect(x - 0.08*cm, y + 0.07*cm, 0.16*cm, 0.07*cm, fillColor=colors.white, strokeColor=colors.HexColor('#285591'), strokeWidth=0.6))


def build_progress_timeline_diagram():
    """Gambar 1: Garis Progres (Dot-Line Milestone) Posisi Program Sekarang vs MVP & Rencana Improvisasi"""
    W, H = 15.4*cm, 4.7*cm
    d = Drawing(W, H)

    # Outer Box
    d.add(Rect(0, 0, W, H, fillColor=colors.HexColor('#F8FAFC'), strokeColor=colors.HexColor('#285591'), strokeWidth=0.9, rx=4, ry=4))
    d.add(Rect(0, H - 0.52*cm, W, 0.52*cm, fillColor=colors.HexColor('#285591'), strokeColor=colors.HexColor('#285591'), strokeWidth=0.5))
    d.add(String(W/2, H - 0.37*cm, "PETA GARIS PROGRES (DOT-LINE TIMELINE): POSISI PROGRAM SEKARANG TERHADAP MVP & RENCANA IMPROVISASI",
                 fontName='Times-Bold', fontSize=6.8, fillColor=colors.white, textAnchor='middle'))

    y_line = 2.40*cm
    xs = [1.50*cm, 4.45*cm, 7.50*cm, 11.10*cm, 14.00*cm]

    # Completed solid green line (Node 1 -> Node 2 -> Node 3)
    d.add(Line(xs[0], y_line, xs[2], y_line, strokeColor=colors.HexColor('#2D783C'), strokeWidth=3.2))
    # Upcoming dashed orange/blue line (Node 3 -> Node 4 -> Node 5)
    l_next1 = Line(xs[2], y_line, xs[3], y_line, strokeColor=colors.HexColor('#D97706'), strokeWidth=2.4)
    l_next1.strokeDashArray = [4, 3]
    d.add(l_next1)
    l_next2 = Line(xs[3], y_line, xs[4], y_line, strokeColor=colors.HexColor('#285591'), strokeWidth=2.4)
    l_next2.strokeDashArray = [4, 3]
    d.add(l_next2)

    # Vertical MVP Threshold Line between Node 3 and Node 4
    x_mvp = 9.35*cm
    mvp_line = Line(x_mvp, 0.25*cm, x_mvp, 4.02*cm, strokeColor=colors.HexColor('#C53030'), strokeWidth=1.1)
    mvp_line.strokeDashArray = [2, 2]
    d.add(mvp_line)
    d.add(Rect(x_mvp - 1.05*cm, 3.68*cm, 2.10*cm, 0.34*cm, fillColor=colors.HexColor('#FFF5F5'), strokeColor=colors.HexColor('#C53030'), strokeWidth=0.7, rx=2, ry=2))
    d.add(String(x_mvp, 3.77*cm, "BATAS SYARAT MVP", fontName='Times-Bold', fontSize=5.8, fillColor=colors.HexColor('#C53030'), textAnchor='middle'))

    # Nodes 1 & 2 (Completed)
    for idx, (x, top_lbl, top_sub, b1, b2, b3) in enumerate([
        (xs[0], "TAHAP 1", "(Selesai / Done)", "Golden Model AI", "Kuantisasi INT8/INT32", "Ekspor weights32.hex"),
        (xs[1], "TAHAP 2", "(Selesai / Done)", "RTL & Pre-Silicon", "6 Modul Verilog Murni", "2.000 Uji (100% Match)")
    ]):
        d.add(Circle(x, y_line, 0.24*cm, fillColor=colors.HexColor('#2D783C'), strokeColor=colors.white, strokeWidth=1.2))
        d.add(String(x, y_line - 0.08*cm, str(idx + 1), fontName='Times-Bold', fontSize=7.5, fillColor=colors.white, textAnchor='middle'))
        d.add(String(x, y_line + 0.65*cm, top_lbl, fontName='Times-Bold', fontSize=7.0, fillColor=colors.HexColor('#22543D'), textAnchor='middle'))
        d.add(String(x, y_line + 0.36*cm, top_sub, fontName='Times-Bold', fontSize=6.2, fillColor=colors.HexColor('#2D783C'), textAnchor='middle'))
        d.add(Rect(x - 1.30*cm, 0.30*cm, 2.60*cm, 1.42*cm, fillColor=colors.HexColor('#DEF2E1'), strokeColor=colors.HexColor('#2D783C'), strokeWidth=0.6, rx=3, ry=3))
        d.add(String(x, 1.38*cm, b1, fontName='Times-Bold', fontSize=6.5, textAnchor='middle'))
        d.add(String(x, 0.99*cm, b2, fontName='Times-Roman', fontSize=6.0, textAnchor='middle'))
        d.add(String(x, 0.60*cm, b3, fontName='Times-Roman', fontSize=6.0, textAnchor='middle'))

    # Node 3: POSISI SEKARANG (Highlighted Halo Dot!)
    x3 = xs[2]
    d.add(Circle(x3, y_line, 0.37*cm, fillColor=colors.HexColor('#FEFCBF'), strokeColor=colors.HexColor('#D69E2E'), strokeWidth=1.2))
    d.add(Circle(x3, y_line, 0.24*cm, fillColor=colors.HexColor('#2D783C'), strokeColor=colors.white, strokeWidth=1.2))
    d.add(String(x3, y_line - 0.08*cm, "3", fontName='Times-Bold', fontSize=7.8, fillColor=colors.white, textAnchor='middle'))
    # Badge above Node 3
    d.add(Rect(x3 - 1.35*cm, y_line + 0.44*cm, 2.70*cm, 0.76*cm, fillColor=colors.HexColor('#FFF6D6'), strokeColor=colors.HexColor('#B45A1E'), strokeWidth=1.0, rx=3, ry=3))
    d.add(String(x3, y_line + 0.88*cm, "POSISI SEKARANG", fontName='Times-Bold', fontSize=6.7, fillColor=colors.HexColor('#9C4221'), textAnchor='middle'))
    d.add(String(x3, y_line + 0.56*cm, "(MVP Inti Chip Tercapai!)", fontName='Times-Bold', fontSize=6.0, fillColor=colors.HexColor('#22543D'), textAnchor='middle'))
    # Detail Box below Node 3
    d.add(Rect(x3 - 1.35*cm, 0.30*cm, 2.70*cm, 1.42*cm, fillColor=colors.HexColor('#FFFBEB'), strokeColor=colors.HexColor('#D69E2E'), strokeWidth=0.9, rx=3, ry=3))
    d.add(String(x3, 1.38*cm, "Chip Fisik & HIL UART", fontName='Times-Bold', fontSize=6.5, textAnchor='middle'))
    d.add(String(x3, 0.99*cm, "Flash embFlash Tang Nano 4K", fontName='Times-Roman', fontSize=5.9, textAnchor='middle'))
    d.add(String(x3, 0.60*cm, "20% LUT | 26,84 mW | 310 clk", fontName='Times-Bold', fontSize=5.9, fillColor=colors.HexColor('#22543D'), textAnchor='middle'))

    # Node 4: Penguatan MVP Sistem
    x4 = xs[3]
    d.add(Circle(x4, y_line, 0.24*cm, fillColor=colors.white, strokeColor=colors.HexColor('#D97706'), strokeWidth=1.8))
    d.add(String(x4, y_line - 0.08*cm, "4", fontName='Times-Bold', fontSize=7.5, fillColor=colors.HexColor('#B45A1E'), textAnchor='middle'))
    d.add(String(x4, y_line + 0.65*cm, "TAHAP 4", fontName='Times-Bold', fontSize=7.0, fillColor=colors.HexColor('#B45A1E'), textAnchor='middle'))
    d.add(String(x4, y_line + 0.36*cm, "(Penguatan MVP)", fontName='Times-Italic', fontSize=6.2, fillColor=colors.HexColor('#B45A1E'), textAnchor='middle'))
    d.add(Rect(x4 - 1.35*cm, 0.32*cm, 2.70*cm, 1.45*cm, fillColor=colors.HexColor('#FDE9D9'), strokeColor=colors.HexColor('#D97706'), strokeWidth=0.6, rx=3, ry=3))
    d.add(String(x4, 1.42*cm, "Hardening Protokol", fontName='Times-Bold', fontSize=6.6, textAnchor='middle'))
    d.add(String(x4, 1.02*cm, "Framing 0xAA + CRC-8", fontName='Times-Roman', fontSize=6.1, textAnchor='middle'))
    d.add(String(x4, 0.62*cm, "Watchdog FSM & Uji INA219", fontName='Times-Roman', fontSize=6.1, textAnchor='middle'))

    # Node 5: Improvisasi Melebihi MVP (Beyond MVP)
    x5 = xs[4]
    d.add(Circle(x5, y_line, 0.24*cm, fillColor=colors.white, strokeColor=colors.HexColor('#285591'), strokeWidth=1.8))
    d.add(String(x5, y_line - 0.08*cm, "5", fontName='Times-Bold', fontSize=7.5, fillColor=colors.HexColor('#285591'), textAnchor='middle'))
    d.add(String(x5, y_line + 0.65*cm, "TAHAP 5", fontName='Times-Bold', fontSize=7.0, fillColor=colors.HexColor('#1A365D'), textAnchor='middle'))
    d.add(String(x5, y_line + 0.36*cm, "(Melebihi MVP)", fontName='Times-Italic', fontSize=6.2, fillColor=colors.HexColor('#285591'), textAnchor='middle'))
    d.add(Rect(x5 - 1.35*cm, 0.32*cm, 2.70*cm, 1.45*cm, fillColor=colors.HexColor('#E1EEFC'), strokeColor=colors.HexColor('#285591'), strokeWidth=0.6, rx=3, ry=3))
    d.add(String(x5, 1.42*cm, "Improvisasi Lanjut", fontName='Times-Bold', fontSize=6.6, textAnchor='middle'))
    d.add(String(x5, 1.02*cm, "Quad-SPI & Dynamic BSRAM", fontName='Times-Roman', fontSize=6.0, textAnchor='middle'))
    d.add(String(x5, 0.62*cm, "Clock-Gating, Getaran, ASIC", fontName='Times-Roman', fontSize=6.0, textAnchor='middle'))

    return d


def build_uml_system_diagram():
    """Gambar 2: UML 2.5 Component & Deployment Diagram Sistem Terintegrasi WindEdgeChip"""
    W, H = 15.4*cm, 7.5*cm
    d = Drawing(W, H)

    d.add(Rect(0, 0, W, H, fillColor=colors.HexColor('#FAFCFF'), strokeColor=colors.HexColor('#285591'), strokeWidth=1.0))
    tab_w = 10.6*cm
    d.add(Polygon([0, H, tab_w, H, tab_w, H - 0.40*cm, tab_w - 0.25*cm, H - 0.56*cm, 0, H - 0.56*cm],
                  fillColor=colors.HexColor('#285591'), strokeColor=colors.HexColor('#285591'), strokeWidth=0.6))
    d.add(String(0.25*cm, H - 0.41*cm, "cmp  Sistem_Terintegrasi_WindEdgeChip [UML 2.5 Component Diagram]",
                 fontName='Times-Bold', fontSize=8, fillColor=colors.white))

    # 1. Sensor Subsystem
    d.add(Rect(0.4*cm, 4.25*cm, 3.8*cm, 2.35*cm, fillColor=colors.HexColor('#F2F4F7'), strokeColor=colors.HexColor('#4A5568'), strokeWidth=0.8))
    add_uml_component_icon(d, 3.76*cm, 6.12*cm)
    d.add(String(2.1*cm, 6.16*cm, "<<subsystem>>", fontName='Times-Italic', fontSize=7.2, textAnchor='middle', fillColor=colors.HexColor('#333333')))
    d.add(String(2.1*cm, 5.78*cm, "Akuisisi Sensor Turbin", fontName='Times-Bold', fontSize=8.2, textAnchor='middle'))
    d.add(Line(0.4*cm, 5.58*cm, 4.2*cm, 5.58*cm, strokeColor=colors.HexColor('#CBD5E0'), strokeWidth=0.5))
    d.add(String(0.55*cm, 5.22*cm, "+ PZEM-017 (V, I, Daya DC)", fontName='Times-Roman', fontSize=7, textAnchor='start'))
    d.add(String(0.55*cm, 4.86*cm, "+ Anemometer Optikal (v)", fontName='Times-Roman', fontSize=7, textAnchor='start'))
    d.add(String(0.55*cm, 4.50*cm, "+ Weather Station (T, RH, arah)", fontName='Times-Roman', fontSize=7, textAnchor='start'))
    add_uml_port(d, 4.2*cm, 5.40*cm)

    # 2. BMKG Cloud API
    d.add(Rect(0.4*cm, 2.10*cm, 3.8*cm, 1.75*cm, fillColor=colors.HexColor('#F2F4F7'), strokeColor=colors.HexColor('#4A5568'), strokeWidth=0.8))
    add_uml_component_icon(d, 3.76*cm, 3.38*cm)
    d.add(String(2.1*cm, 3.44*cm, "<<external_service>>", fontName='Times-Italic', fontSize=7.2, textAnchor='middle', fillColor=colors.HexColor('#333333')))
    d.add(String(2.1*cm, 3.08*cm, "API Cuaca Terbuka BMKG", fontName='Times-Bold', fontSize=8.2, textAnchor='middle'))
    d.add(Line(0.4*cm, 2.90*cm, 4.2*cm, 2.90*cm, strokeColor=colors.HexColor('#CBD5E0'), strokeWidth=0.5))
    d.add(String(0.55*cm, 2.56*cm, "+ Prakiraan Cuaca 3 Jam", fontName='Times-Roman', fontSize=7, textAnchor='start'))
    d.add(String(0.55*cm, 2.24*cm, "+ adm4: 32.73.02.1006 (ITB)", fontName='Times-Roman', fontSize=7, textAnchor='start'))
    add_uml_port(d, 4.2*cm, 2.95*cm)

    # 3. ESP32 Host MCU
    d.add(Rect(5.65*cm, 2.10*cm, 4.0*cm, 4.5*cm, fillColor=colors.HexColor('#E1EEFC'), strokeColor=colors.HexColor('#285591'), strokeWidth=0.9))
    add_uml_component_icon(d, 9.22*cm, 6.12*cm)
    d.add(String(7.5*cm, 6.16*cm, "<<mcu_node>>", fontName='Times-Italic', fontSize=7.2, textAnchor='middle', fillColor=colors.HexColor('#1A365D')))
    d.add(String(7.5*cm, 5.78*cm, "ESP32 Host Controller", fontName='Times-Bold', fontSize=8.4, textAnchor='middle'))
    d.add(Line(5.65*cm, 5.56*cm, 9.65*cm, 5.56*cm, strokeColor=colors.HexColor('#90CDF4'), strokeWidth=0.6))
    d.add(String(5.82*cm, 5.20*cm, "+ feature_vec[16] : int8", fontName='Times-Roman', fontSize=7, textAnchor='start'))
    d.add(String(5.82*cm, 4.86*cm, "+ pred_watt : float32", fontName='Times-Roman', fontSize=7, textAnchor='start'))
    d.add(Line(5.65*cm, 4.66*cm, 9.65*cm, 4.66*cm, strokeColor=colors.HexColor('#90CDF4'), strokeWidth=0.6))
    d.add(String(5.82*cm, 4.32*cm, "+ read_modbus_sensors()", fontName='Times-Roman', fontSize=7, textAnchor='start'))
    d.add(String(5.82*cm, 3.98*cm, "+ quantize_fp32_to_int8()", fontName='Times-Roman', fontSize=7, textAnchor='start'))
    d.add(String(5.82*cm, 3.64*cm, "+ dequantize_to_watt()", fontName='Times-Roman', fontSize=7, textAnchor='start'))
    d.add(String(5.82*cm, 3.30*cm, "+ fallback_tflite_micro()", fontName='Times-Roman', fontSize=7, textAnchor='start'))
    d.add(String(5.82*cm, 2.96*cm, "+ publish_mqtt_telemetry()", fontName='Times-Roman', fontSize=7, textAnchor='start'))
    d.add(String(5.82*cm, 2.40*cm, "[Daya < 0,5 W | Mode Cadangan]", fontName='Times-Italic', fontSize=6.7, textAnchor='start', fillColor=colors.HexColor('#2B6CB0')))

    add_uml_port(d, 5.65*cm, 5.40*cm)
    add_uml_port(d, 5.65*cm, 2.95*cm)
    add_uml_port(d, 9.65*cm, 4.95*cm)
    add_uml_port(d, 9.65*cm, 4.10*cm)
    add_uml_port(d, 7.65*cm, 2.10*cm)

    # 4. FPGA SoC Accelerator
    d.add(Rect(11.35*cm, 2.10*cm, 3.7*cm, 4.5*cm, fillColor=colors.HexColor('#DEF2E1'), strokeColor=colors.HexColor('#2D783C'), strokeWidth=1.0))
    add_uml_component_icon(d, 14.62*cm, 6.12*cm)
    d.add(String(13.05*cm, 6.16*cm, "<<fpga_soc>>", fontName='Times-Italic', fontSize=7.2, textAnchor='middle', fillColor=colors.HexColor('#1C4532')))
    d.add(String(13.05*cm, 5.78*cm, "Sipeed Tang Nano 4K", fontName='Times-Bold', fontSize=8.3, textAnchor='middle'))
    d.add(String(13.05*cm, 5.46*cm, "(Gowin GW1NSR-LV4C)", fontName='Times-Roman', fontSize=7.1, textAnchor='middle'))
    d.add(Line(11.35*cm, 5.28*cm, 15.05*cm, 5.28*cm, strokeColor=colors.HexColor('#68D391'), strokeWidth=0.6))
    d.add(String(11.50*cm, 4.94*cm, "+ top_soc.v @ 27 MHz", fontName='Times-Bold', fontSize=6.9, textAnchor='start'))
    d.add(String(11.50*cm, 4.58*cm, "+ u_uart_rx / u_uart_tx", fontName='Times-Roman', fontSize=6.9, textAnchor='start'))
    d.add(String(11.50*cm, 4.22*cm, "+ u_fsm (310 clk = 11,48 us)", fontName='Times-Roman', fontSize=6.9, textAnchor='start'))
    d.add(String(11.50*cm, 3.86*cm, "+ u_weights_rom (1 BSRAM)", fontName='Times-Roman', fontSize=6.9, textAnchor='start'))
    d.add(String(11.50*cm, 3.50*cm, "+ u_mac4 (4x Mult + Adder)", fontName='Times-Roman', fontSize=6.9, textAnchor='start'))
    d.add(String(11.50*cm, 3.14*cm, "+ u_post (Bias+Shift+ReLU)", fontName='Times-Roman', fontSize=6.9, textAnchor='start'))
    d.add(String(11.50*cm, 2.40*cm, "[20% LUT | Daya: 26,84 mW]", fontName='Times-Bold', fontSize=6.7, textAnchor='start', fillColor=colors.HexColor('#22543D')))

    add_uml_port(d, 11.35*cm, 4.95*cm)
    add_uml_port(d, 11.35*cm, 4.10*cm)

    # 5. Server & Dashboard L1
    d.add(Rect(0.4*cm, 0.25*cm, 9.25*cm, 1.25*cm, fillColor=colors.HexColor('#FFF6D6'), strokeColor=colors.HexColor('#A57D14'), strokeWidth=0.8))
    d.add(String(5.02*cm, 1.12*cm, "<<application_layer>>  L1: Server Node-RED + InfluxDB + Dashboard Vue.js", fontName='Times-Bold', fontSize=7.9, textAnchor='middle'))
    d.add(String(5.02*cm, 0.74*cm, "+ Visualisasi Real-Time Daya Aktual vs. Prediksi 1 Jam Ke Depan + Digital Twin Replay 11 Bulan", fontName='Times-Roman', fontSize=6.9, textAnchor='middle'))
    d.add(String(5.02*cm, 0.40*cm, "+ Peta Multilokasi Turbin & Integrasi Kamera Validasi Lapangan (Atap Gedung PAU ITB)", fontName='Times-Roman', fontSize=6.9, textAnchor='middle'))
    add_uml_port(d, 7.65*cm, 1.50*cm)

    # 6. Power Audit Rig INA219
    d.add(Rect(11.35*cm, 0.25*cm, 3.7*cm, 1.25*cm, fillColor=colors.HexColor('#FDE9D9'), strokeColor=colors.HexColor('#B45A1E'), strokeWidth=0.8))
    d.add(String(13.20*cm, 1.12*cm, "<<measurement_instrument>>", fontName='Times-Italic', fontSize=6.9, textAnchor='middle'))
    d.add(String(13.20*cm, 0.78*cm, "Rig Sensor Arus INA219", fontName='Times-Bold', fontSize=7.9, textAnchor='middle'))
    d.add(String(13.20*cm, 0.42*cm, "Audit Energi: E = V*I*t (~0,31 uJ)", fontName='Times-Roman', fontSize=6.7, textAnchor='middle'))

    # Connectors
    add_arrow(d, 4.30*cm, 5.40*cm, 5.55*cm, 5.40*cm)
    d.add(String(4.92*cm, 5.58*cm, "<<Modbus RTU>>", fontName='Times-Bold', fontSize=6.4, textAnchor='middle'))
    d.add(String(4.92*cm, 5.08*cm, "RS-485", fontName='Times-Roman', fontSize=6.2, textAnchor='middle'))

    add_arrow(d, 4.30*cm, 2.95*cm, 5.55*cm, 2.95*cm)
    d.add(String(4.92*cm, 3.14*cm, "<<HTTPS JSON>>", fontName='Times-Bold', fontSize=6.4, textAnchor='middle'))
    d.add(String(4.92*cm, 2.64*cm, "WiFi", fontName='Times-Roman', fontSize=6.2, textAnchor='middle'))

    add_arrow(d, 9.75*cm, 4.95*cm, 11.25*cm, 4.95*cm)
    d.add(String(10.50*cm, 5.14*cm, "16B Fitur INT8", fontName='Times-Bold', fontSize=6.3, textAnchor='middle'))

    add_arrow(d, 11.25*cm, 4.10*cm, 9.75*cm, 4.10*cm)
    d.add(String(10.50*cm, 4.42*cm, "<<UART/QSPI>>", fontName='Times-Italic', fontSize=6.2, textAnchor='middle'))
    d.add(String(10.50*cm, 3.74*cm, "3B (Pred+Cycles)", fontName='Times-Bold', fontSize=6.3, textAnchor='middle'))

    add_arrow(d, 7.65*cm, 2.00*cm, 7.65*cm, 1.60*cm)
    d.add(String(8.50*cm, 1.74*cm, "<<MQTT>>", fontName='Times-Bold', fontSize=6.6, textAnchor='middle'))

    add_arrow(d, 13.20*cm, 1.50*cm, 13.20*cm, 2.10*cm, color=colors.HexColor('#B45A1E'), dashed=True)
    d.add(String(14.08*cm, 1.74*cm, "<<power_probe>>", fontName='Times-Italic', fontSize=6.2, textAnchor='middle', fillColor=colors.HexColor('#B45A1E')))

    return d


def build_uml_ibd_diagram():
    """Gambar 3: UML 2.5 Composite Structure / Internal Block Diagram (IBD) top_soc.v"""
    W, H = 15.4*cm, 8.2*cm
    d = Drawing(W, H)

    d.add(Rect(0, 0, W, H, fillColor=colors.HexColor('#F4FAF5'), strokeColor=colors.HexColor('#2D783C'), strokeWidth=1.1))
    tab_w = 10.6*cm
    d.add(Polygon([0, H, tab_w, H, tab_w, H - 0.40*cm, tab_w - 0.25*cm, H - 0.56*cm, 0, H - 0.56*cm],
                  fillColor=colors.HexColor('#2D783C'), strokeColor=colors.HexColor('#2D783C'), strokeWidth=0.6))
    d.add(String(0.25*cm, H - 0.41*cm, "ibd  [<<fpga_soc>> top_soc.v — Gowin GW1NSR-LV4C @ 27 MHz]",
                 fontName='Times-Bold', fontSize=8, fillColor=colors.white))

    # Left External Ports
    add_uml_port(d, 0.12*cm, 6.95*cm)
    d.add(String(0.32*cm, 6.87*cm, "clk (Pin 45: 27MHz)", fontName='Times-Bold', fontSize=6.5, textAnchor='start'))
    add_uml_port(d, 0.12*cm, 6.40*cm)
    d.add(String(0.32*cm, 6.32*cm, "rst_n (Pin 14: Key S1)", fontName='Times-Bold', fontSize=6.5, textAnchor='start'))
    add_uml_port(d, 0.12*cm, 4.10*cm)
    d.add(String(0.32*cm, 5.45*cm, "rx_pin (Pin 44)", fontName='Times-Bold', fontSize=6.5, textAnchor='start'))

    # Top-Right External Ports
    add_uml_port(d, W - 0.12*cm, 7.80*cm)
    d.add(String(W - 0.32*cm, 7.72*cm, "led_busy (Pin 10: Active-Low)", fontName='Times-Bold', fontSize=6.4, textAnchor='end'))
    add_uml_port(d, W - 0.12*cm, 7.38*cm)
    d.add(String(W - 0.32*cm, 7.30*cm, "led_done (Pin 13: Done Toggle)", fontName='Times-Bold', fontSize=6.4, textAnchor='end'))

    # Bottom-Right External Port
    add_uml_port(d, W - 0.12*cm, 0.85*cm)
    d.add(String(W - 0.32*cm, 1.15*cm, "tx_pin (Pin 46)", fontName='Times-Bold', fontSize=6.5, textAnchor='end'))

    # 1. UART RX Transceiver Block
    d.add(Rect(0.55*cm, 2.65*cm, 2.65*cm, 2.50*cm, fillColor=colors.HexColor('#E1EEFC'), strokeColor=colors.HexColor('#285591'), strokeWidth=0.85))
    d.add(String(1.87*cm, 4.80*cm, "<<transceiver>>", fontName='Times-Italic', fontSize=6.6, textAnchor='middle'))
    d.add(String(1.87*cm, 4.46*cm, "u_uart_rx : uart_rx.v", fontName='Times-Bold', fontSize=7.2, textAnchor='middle'))
    d.add(Line(0.55*cm, 4.30*cm, 3.20*cm, 4.30*cm, strokeColor=colors.HexColor('#90CDF4'), strokeWidth=0.5))
    d.add(String(1.87*cm, 3.96*cm, "115200 bps, 8-N-1", fontName='Times-Roman', fontSize=6.4, textAnchor='middle'))
    d.add(String(1.87*cm, 3.62*cm, "+ rx_byte[7:0], valid", fontName='Times-Roman', fontSize=6.4, textAnchor='middle'))
    d.add(String(1.87*cm, 3.28*cm, "+ rx_count[3:0] (0..15)", fontName='Times-Roman', fontSize=6.4, textAnchor='middle'))
    d.add(String(1.87*cm, 2.88*cm, "Auto-trigger start", fontName='Times-Bold', fontSize=6.4, textAnchor='middle', fillColor=colors.HexColor('#2B6CB0')))

    # Inner Composite Box: u_accelerator_core : top.v
    d.add(Rect(3.85*cm, 1.75*cm, 11.10*cm, 5.35*cm, fillColor=colors.white, strokeColor=colors.HexColor('#285591'), strokeWidth=0.9, strokeDashArray=[4, 2]))
    d.add(String(4.05*cm, 6.82*cm, "<<ip_core>>  u_accelerator_core : top.v (Inti Akselerator Inferensi MLP INT8)",
                 fontName='Times-Bold', fontSize=7.3, textAnchor='start', fillColor=colors.HexColor('#1A365D')))

    # 2. FSM Controller
    d.add(Rect(4.10*cm, 4.75*cm, 3.25*cm, 1.90*cm, fillColor=colors.HexColor('#E1EEFC'), strokeColor=colors.HexColor('#285591'), strokeWidth=0.8))
    d.add(String(5.72*cm, 6.32*cm, "<<controller>>", fontName='Times-Italic', fontSize=6.6, textAnchor='middle'))
    d.add(String(5.72*cm, 6.00*cm, "u_fsm : fsm_controller.v", fontName='Times-Bold', fontSize=7.1, textAnchor='middle'))
    d.add(Line(4.10*cm, 5.84*cm, 7.35*cm, 5.84*cm, strokeColor=colors.HexColor('#90CDF4'), strokeWidth=0.5))
    d.add(String(5.72*cm, 5.52*cm, "+ State: S_IDLE..S_DONE (8)", fontName='Times-Roman', fontSize=6.3, textAnchor='middle'))
    d.add(String(5.72*cm, 5.20*cm, "+ neuron_cnt[5:0], step_cnt[3:0]", fontName='Times-Roman', fontSize=6.3, textAnchor='middle'))
    d.add(String(5.72*cm, 4.88*cm, "+ cycle_count[15:0] = 310", fontName='Times-Bold', fontSize=6.3, textAnchor='middle'))

    # 3. BSRAM Weights & Bias ROM
    d.add(Rect(8.15*cm, 4.75*cm, 3.45*cm, 1.90*cm, fillColor=colors.HexColor('#FFF6D6'), strokeColor=colors.HexColor('#A57D14'), strokeWidth=0.8))
    d.add(String(9.87*cm, 6.32*cm, "<<memory_bram>>", fontName='Times-Italic', fontSize=6.6, textAnchor='middle'))
    d.add(String(9.87*cm, 6.00*cm, "u_weights_rom : weights_rom.v", fontName='Times-Bold', fontSize=7.0, textAnchor='middle'))
    d.add(Line(8.15*cm, 5.84*cm, 11.60*cm, 5.84*cm, strokeColor=colors.HexColor('#ECC94B'), strokeWidth=0.5))
    d.add(String(9.87*cm, 5.52*cm, "+ 1x Gowin BSRAM SPX9 (pROM)", fontName='Times-Roman', fontSize=6.3, textAnchor='middle'))
    d.add(String(9.87*cm, 5.20*cm, "+ 260x32-bit (1.040 Bobot INT8)", fontName='Times-Roman', fontSize=6.3, textAnchor='middle'))
    d.add(String(9.87*cm, 4.88*cm, "+ bias_mem[0:48] : signed[31:0]", fontName='Times-Roman', fontSize=6.3, textAnchor='middle'))

    # 4. Activation Ping-Pong RAM
    d.add(Rect(4.10*cm, 2.15*cm, 3.25*cm, 2.10*cm, fillColor=colors.HexColor('#FFF6D6'), strokeColor=colors.HexColor('#A57D14'), strokeWidth=0.8))
    d.add(String(5.72*cm, 3.92*cm, "<<register_file>>", fontName='Times-Italic', fontSize=6.6, textAnchor='middle'))
    d.add(String(5.72*cm, 3.60*cm, "Ping-Pong Activation RAM", fontName='Times-Bold', fontSize=7.1, textAnchor='middle'))
    d.add(Line(4.10*cm, 3.44*cm, 7.35*cm, 3.44*cm, strokeColor=colors.HexColor('#ECC94B'), strokeWidth=0.5))
    d.add(String(5.72*cm, 3.12*cm, "+ in_buf[0:15] : signed[7:0]", fontName='Times-Roman', fontSize=6.3, textAnchor='middle'))
    d.add(String(5.72*cm, 2.82*cm, "+ h1_buf[0:31] : signed[7:0]", fontName='Times-Roman', fontSize=6.3, textAnchor='middle'))
    d.add(String(5.72*cm, 2.52*cm, "+ h2_buf[0:15] : signed[7:0]", fontName='Times-Roman', fontSize=6.3, textAnchor='middle'))
    d.add(String(5.72*cm, 2.24*cm, "Mux 4-Byte -> mac_in0..3", fontName='Times-Bold', fontSize=6.2, textAnchor='middle'))

    # 5. MAC4 Engine
    d.add(Rect(8.15*cm, 2.15*cm, 3.45*cm, 2.10*cm, fillColor=colors.HexColor('#DEF2E1'), strokeColor=colors.HexColor('#2D783C'), strokeWidth=0.9))
    d.add(String(9.87*cm, 3.92*cm, "<<datapath_unit>>", fontName='Times-Italic', fontSize=6.6, textAnchor='middle'))
    d.add(String(9.87*cm, 3.60*cm, "u_mac4 : mac4_engine.v", fontName='Times-Bold', fontSize=7.2, textAnchor='middle'))
    d.add(Line(8.15*cm, 3.44*cm, 11.60*cm, 3.44*cm, strokeColor=colors.HexColor('#68D391'), strokeWidth=0.5))
    d.add(String(9.87*cm, 3.12*cm, "Tahap 1: 4x Mult (INT8*INT8)", fontName='Times-Roman', fontSize=6.3, textAnchor='middle'))
    d.add(String(9.87*cm, 2.82*cm, "Tahap 2: Adder Tree 4:1 (INT18)", fontName='Times-Roman', fontSize=6.3, textAnchor='middle'))
    d.add(String(9.87*cm, 2.52*cm, "Tahap 3: Akumulator INT32", fontName='Times-Roman', fontSize=6.3, textAnchor='middle'))
    d.add(String(9.87*cm, 2.24*cm, "[2x DSP MULTADDALU18X18]", fontName='Times-Bold', fontSize=6.1, textAnchor='middle', fillColor=colors.HexColor('#22543D')))

    # 6. Post-Processing Unit
    d.add(Rect(12.25*cm, 2.15*cm, 2.50*cm, 2.55*cm, fillColor=colors.HexColor('#FDE9D9'), strokeColor=colors.HexColor('#B45A1E'), strokeWidth=0.85))
    d.add(String(13.50*cm, 4.38*cm, "<<datapath_unit>>", fontName='Times-Italic', fontSize=6.4, textAnchor='middle'))
    d.add(String(13.50*cm, 4.06*cm, "u_post", fontName='Times-Bold', fontSize=7.2, textAnchor='middle'))
    d.add(String(13.50*cm, 3.78*cm, "(post_process.v)", fontName='Times-Roman', fontSize=6.3, textAnchor='middle'))
    d.add(Line(12.25*cm, 3.62*cm, 14.75*cm, 3.62*cm, strokeColor=colors.HexColor('#F6AD55'), strokeWidth=0.5))
    d.add(String(13.50*cm, 3.30*cm, "1. + cur_bias[31:0]", fontName='Times-Roman', fontSize=6.2, textAnchor='middle'))
    d.add(String(13.50*cm, 2.98*cm, "2. * mult_scale (32)", fontName='Times-Roman', fontSize=6.2, textAnchor='middle'))
    d.add(String(13.50*cm, 2.66*cm, "3. >>> shift_scale (8)", fontName='Times-Roman', fontSize=6.2, textAnchor='middle'))
    d.add(String(13.50*cm, 2.32*cm, "4. ReLU & Clamp[127]", fontName='Times-Bold', fontSize=6.2, textAnchor='middle'))

    # 7. UART TX + Output Frame FSM
    d.add(Rect(3.85*cm, 0.28*cm, 8.90*cm, 1.15*cm, fillColor=colors.HexColor('#E1EEFC'), strokeColor=colors.HexColor('#285591'), strokeWidth=0.85))
    d.add(String(8.30*cm, 1.10*cm, "<<transceiver>>  u_uart_tx : uart_tx.v + FSM Paket Balasan 3-Byte",
                 fontName='Times-Bold', fontSize=6.9, textAnchor='middle'))
    d.add(String(8.30*cm, 0.74*cm, "+ Frame 3B: [Byte0: prediction_out(INT8) | Byte1: cycles[15:8] | Byte2: cycles[7:0]]",
                 fontName='Times-Roman', fontSize=6.2, textAnchor='middle'))
    d.add(String(8.30*cm, 0.42*cm, "+ Dilengkapi Pulse Stretcher 23-bit (5.400.000 clk = 0,2 s) untuk LED Onboard Pin 10",
                 fontName='Times-Italic', fontSize=6.1, textAnchor='middle', fillColor=colors.HexColor('#2B6CB0')))

    # Internal Signal Wires & Arrows
    add_arrow(d, 0.22*cm, 4.10*cm, 0.55*cm, 4.10*cm)
    add_arrow(d, 3.20*cm, 4.55*cm, 4.10*cm, 5.55*cm)
    d.add(String(3.52*cm, 5.28*cm, "start", fontName='Times-Bold', fontSize=6.1, textAnchor='middle'))

    add_arrow(d, 3.20*cm, 3.25*cm, 4.10*cm, 3.25*cm)
    d.add(String(3.52*cm, 3.42*cm, "feat[7:0]", fontName='Times-Roman', fontSize=5.9, textAnchor='middle'))

    add_arrow(d, 7.35*cm, 5.70*cm, 8.15*cm, 5.70*cm)
    d.add(String(7.75*cm, 5.86*cm, "step_addr", fontName='Times-Roman', fontSize=5.9, textAnchor='middle'))

    add_arrow(d, 5.72*cm, 4.75*cm, 5.72*cm, 4.25*cm)
    d.add(String(6.42*cm, 4.45*cm, "layer_sel, idx", fontName='Times-Roman', fontSize=5.9, textAnchor='middle'))

    add_arrow(d, 9.87*cm, 4.75*cm, 9.87*cm, 4.25*cm)
    d.add(String(10.68*cm, 4.45*cm, "weights_q[31:0]", fontName='Times-Bold', fontSize=6.0, textAnchor='middle'))

    add_arrow(d, 7.35*cm, 3.20*cm, 8.15*cm, 3.20*cm)
    d.add(String(7.75*cm, 3.36*cm, "in0..3", fontName='Times-Bold', fontSize=6.0, textAnchor='middle'))

    add_arrow(d, 11.60*cm, 3.20*cm, 12.25*cm, 3.20*cm)
    d.add(String(11.92*cm, 3.38*cm, "acc[31:0]", fontName='Times-Bold', fontSize=5.8, textAnchor='middle'))

    d.add(Line(11.60*cm, 5.45*cm, 13.50*cm, 5.45*cm, strokeColor=colors.HexColor('#222222'), strokeWidth=0.8))
    add_arrow(d, 13.50*cm, 5.45*cm, 13.50*cm, 4.70*cm)
    d.add(String(12.65*cm, 5.58*cm, "cur_bias[31:0]", fontName='Times-Roman', fontSize=6.0, textAnchor='middle'))

    d.add(Line(13.50*cm, 2.15*cm, 13.50*cm, 1.90*cm, strokeColor=colors.HexColor('#B45A1E'), strokeWidth=0.9))
    d.add(Line(13.50*cm, 1.90*cm, 5.72*cm, 1.90*cm, strokeColor=colors.HexColor('#B45A1E'), strokeWidth=0.9))
    add_arrow(d, 5.72*cm, 1.90*cm, 5.72*cm, 2.15*cm, color=colors.HexColor('#B45A1E'))
    add_arrow(d, 11.20*cm, 1.90*cm, 11.20*cm, 1.43*cm, color=colors.HexColor('#B45A1E'))
    d.add(String(9.50*cm, 1.95*cm, "act_post_out[7:0] (Write-back Layer 1/2 & Output Prediksi)", fontName='Times-Bold', fontSize=6.0, textAnchor='middle', fillColor=colors.HexColor('#B45A1E')))

    add_arrow(d, 12.75*cm, 0.85*cm, W - 0.22*cm, 0.85*cm)

    return d


def build_uml_fsm_diagram():
    """Gambar 4: UML 2.5 State Machine Diagram fsm_controller.v"""
    W, H = 15.4*cm, 4.9*cm
    d = Drawing(W, H)

    d.add(Rect(0, 0, W, H, fillColor=colors.HexColor('#FAFCFF'), strokeColor=colors.HexColor('#285591'), strokeWidth=0.9))
    tab_w = 10.6*cm
    d.add(Polygon([0, H, tab_w, H, tab_w, H - 0.40*cm, tab_w - 0.25*cm, H - 0.55*cm, 0, H - 0.55*cm],
                  fillColor=colors.HexColor('#285591'), strokeColor=colors.HexColor('#285591'), strokeWidth=0.6))
    d.add(String(0.25*cm, H - 0.40*cm, "stm  [<<controller>> fsm_controller.v — 8-State Deterministic Sequencer]",
                 fontName='Times-Bold', fontSize=7.8, fillColor=colors.white))

    def draw_state(x, y, w, h, name, line1, line2, fill, stroke):
        d.add(Rect(x, y, w, h, fillColor=fill, strokeColor=stroke, strokeWidth=0.85, rx=4, ry=4))
        d.add(Line(x, y + h - 0.42*cm, x + w, y + h - 0.42*cm, strokeColor=stroke, strokeWidth=0.5))
        d.add(String(x + w/2, y + h - 0.30*cm, name, fontName='Times-Bold', fontSize=7.3, textAnchor='middle'))
        d.add(String(x + w/2, y + h - 0.68*cm, line1, fontName='Times-Roman', fontSize=6.3, textAnchor='middle'))
        d.add(String(x + w/2, y + 0.16*cm, line2, fontName='Times-Italic', fontSize=6.2, textAnchor='middle'))

    draw_state(0.45*cm, 2.65*cm, 2.8*cm, 1.35*cm, "S_IDLE (0)", "entry / busy = 0", "Wait start==1", colors.HexColor('#F2F4F7'), colors.HexColor('#4A5568'))
    draw_state(4.25*cm, 2.65*cm, 3.0*cm, 1.35*cm, "S_L1_STEP (1)", "do / mac_en = 1", "4 langkah/neuron (x32)", colors.HexColor('#E1EEFC'), colors.HexColor('#285591'))
    draw_state(8.25*cm, 2.65*cm, 3.0*cm, 1.35*cm, "S_L2_STEP (3)", "do / mac_en = 1", "8 langkah/neuron (x16)", colors.HexColor('#E1EEFC'), colors.HexColor('#285591'))
    draw_state(12.10*cm, 2.65*cm, 2.85*cm, 1.35*cm, "S_L3_STEP (5)", "do / mac_en = 1", "4 langkah/neuron (x1)", colors.HexColor('#E1EEFC'), colors.HexColor('#285591'))

    draw_state(0.45*cm, 0.45*cm, 2.8*cm, 1.35*cm, "S_DONE (7)", "entry / done = 1", "Total = 310 Siklus", colors.HexColor('#DEF2E1'), colors.HexColor('#2D783C'))
    draw_state(4.25*cm, 0.45*cm, 3.0*cm, 1.35*cm, "S_L1_POST (2)", "do / write_h1_buf", "160 siklus selesai", colors.HexColor('#FFF6D6'), colors.HexColor('#A57D14'))
    draw_state(8.25*cm, 0.45*cm, 3.0*cm, 1.35*cm, "S_L2_POST (4)", "do / write_h2_buf", "144 siklus selesai", colors.HexColor('#FFF6D6'), colors.HexColor('#A57D14'))
    draw_state(12.10*cm, 0.45*cm, 2.85*cm, 1.35*cm, "S_L3_POST (6)", "do / write_pred_out", "5 siklus selesai", colors.HexColor('#FDE9D9'), colors.HexColor('#B45A1E'))

    add_arrow(d, 3.25*cm, 3.32*cm, 4.25*cm, 3.32*cm)
    d.add(String(3.75*cm, 3.48*cm, "[start]", fontName='Times-Bold', fontSize=6.2, textAnchor='middle'))

    add_arrow(d, 6.05*cm, 2.65*cm, 6.05*cm, 1.80*cm)
    d.add(String(6.65*cm, 2.18*cm, "[step==3]", fontName='Times-Roman', fontSize=6.0, textAnchor='middle'))
    add_arrow(d, 5.45*cm, 1.80*cm, 5.45*cm, 2.65*cm)
    d.add(String(4.75*cm, 2.18*cm, "[n < 31]", fontName='Times-Roman', fontSize=6.0, textAnchor='middle'))

    add_arrow(d, 7.25*cm, 1.15*cm, 8.25*cm, 3.15*cm)
    d.add(String(7.68*cm, 2.42*cm, "[n==31]", fontName='Times-Bold', fontSize=6.0, textAnchor='middle'))

    add_arrow(d, 10.05*cm, 2.65*cm, 10.05*cm, 1.80*cm)
    d.add(String(10.65*cm, 2.18*cm, "[step==7]", fontName='Times-Roman', fontSize=6.0, textAnchor='middle'))
    add_arrow(d, 9.45*cm, 1.80*cm, 9.45*cm, 2.65*cm)
    d.add(String(8.75*cm, 2.18*cm, "[n < 15]", fontName='Times-Roman', fontSize=6.0, textAnchor='middle'))

    add_arrow(d, 11.25*cm, 1.15*cm, 12.10*cm, 3.15*cm)
    d.add(String(11.62*cm, 2.42*cm, "[n==15]", fontName='Times-Bold', fontSize=6.0, textAnchor='middle'))

    add_arrow(d, 13.52*cm, 2.65*cm, 13.52*cm, 1.80*cm)
    d.add(String(14.15*cm, 2.18*cm, "[step==3]", fontName='Times-Roman', fontSize=6.0, textAnchor='middle'))

    d.add(Line(13.52*cm, 0.45*cm, 13.52*cm, 0.18*cm, strokeColor=colors.HexColor('#2D783C'), strokeWidth=0.85))
    d.add(Line(13.52*cm, 0.18*cm, 1.85*cm, 0.18*cm, strokeColor=colors.HexColor('#2D783C'), strokeWidth=0.85))
    add_arrow(d, 1.85*cm, 0.18*cm, 1.85*cm, 0.45*cm, color=colors.HexColor('#2D783C'))
    d.add(String(7.7*cm, 0.23*cm, "Selesai Neuron Output -> S_DONE (Picu Transmisi Balasan UART 3 Byte)", fontName='Times-Bold', fontSize=6.1, textAnchor='middle', fillColor=colors.HexColor('#22543D')))

    add_arrow(d, 1.85*cm, 1.80*cm, 1.85*cm, 2.65*cm)
    d.add(String(1.25*cm, 2.18*cm, "[1 clk]", fontName='Times-Roman', fontSize=6.0, textAnchor='middle'))

    return d


def build_pdf(filename):
    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        leftMargin=2.8*cm,
        rightMargin=2.8*cm,
        topMargin=2.5*cm,
        bottomMargin=2.5*cm
    )

    styles = getSampleStyleSheet()

    body_style = ParagraphStyle(
        'FormalBody',
        parent=styles['Normal'],
        fontName='Times-Roman',
        fontSize=11.3,
        leading=16.2,
        alignment=TA_JUSTIFY,
        firstLineIndent=1.15*cm,
        spaceAfter=3
    )

    body_no_indent = ParagraphStyle(
        'FormalBodyNoIndent',
        parent=body_style,
        firstLineIndent=0,
        spaceAfter=4
    )

    quote_box_style = ParagraphStyle(
        'QuoteBox',
        parent=styles['Normal'],
        fontName='Times-Italic',
        fontSize=11,
        leading=16,
        alignment=TA_JUSTIFY,
        leftIndent=0.7*cm,
        rightIndent=0.4*cm,
        spaceBefore=3,
        spaceAfter=6,
        textColor=colors.HexColor('#1A365D')
    )

    section_style = ParagraphStyle(
        'CenteredSection',
        parent=styles['Normal'],
        fontName='Times-Bold',
        fontSize=11.8,
        leading=16.5,
        alignment=TA_CENTER,
        spaceBefore=12,
        spaceAfter=7,
        keepWithNext=True
    )

    subsection_style = ParagraphStyle(
        'LeftSubSection',
        parent=styles['Normal'],
        fontName='Times-Bold',
        fontSize=11.3,
        leading=15.5,
        alignment=TA_LEFT,
        spaceBefore=9,
        spaceAfter=4,
        keepWithNext=True
    )

    bib_style = ParagraphStyle(
        'BibliographyItem',
        parent=styles['Normal'],
        fontName='Times-Roman',
        fontSize=10.5,
        leading=14.5,
        alignment=TA_JUSTIFY,
        leftIndent=0.9*cm,
        firstLineIndent=-0.9*cm,
        spaceAfter=4.5
    )

    table_text = ParagraphStyle(
        'TableText',
        parent=styles['Normal'],
        fontName='Times-Roman',
        fontSize=8.9,
        leading=12.2,
        alignment=TA_LEFT
    )

    table_header = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Times-Bold',
        fontSize=8.9,
        leading=12.2,
        alignment=TA_CENTER
    )

    caption_style = ParagraphStyle(
        'CaptionStyle',
        parent=styles['Normal'],
        fontName='Times-Bold',
        fontSize=9.3,
        leading=13,
        alignment=TA_CENTER,
        spaceBefore=4,
        spaceAfter=5
    )

    story = []

    # --- COVER PAGE ---
    cover_title = ParagraphStyle('CoverTitle', fontName='Times-Bold', fontSize=14, leading=21, alignment=TA_CENTER)
    cover_subtitle = ParagraphStyle('CoverSubTitle', fontName='Times-Roman', fontSize=11.5, leading=17, alignment=TA_CENTER)

    story.append(Spacer(1, 1.4*cm))
    story.append(Paragraph("LAPORAN TEKNIS DAN DOKUMEN PERANCANGAN ARSITEKTUR CHIP", cover_title))
    story.append(Spacer(1, 0.7*cm))
    story.append(Paragraph("PERANCANGAN AKSELERATOR NEURAL NETWORK BERBASIS FPGA (<i>STANDALONE PIPELINED MAC4</i>) UNTUK PREDIKSI DAYA TURBIN ANGIN PADA KOMPUTASI TEPI HEMAT DAYA", cover_title))
    story.append(Spacer(1, 0.9*cm))
    story.append(Paragraph("Peta Progres terhadap MVP, Ringkasan Masalah, Ide Solusi Silikon, Diagram Blok Sistem Berstandar UML 2.5, Evaluasi Arsitektur Eksisting, Rencana Improvisasi Chip, serta Pertanyaan Lapangan kepada Mentor DeepTech", cover_subtitle))
    story.append(Spacer(1, 2.8*cm))
    story.append(Paragraph(
        "<b>Fokus Sub-Proyek Lapisan 3 (L3 — Semikonduktor &amp; FPGA Edge Accelerator):</b><br/>"
        "Proyek <i>WindEdgeChip</i> — DeepTech for Smart-X Hackathon 2026<br/>"
        "Kategori Peningkatan <i>Renewable Energy</i>: <i>Wind Power Output Forecasting</i>",
        cover_subtitle
    ))
    story.append(Spacer(1, 4.0*cm))
    story.append(Paragraph("<b>TIM CHITATO (WINDEDGECHIP)</b><br/><b>INSTITUT TEKNOLOGI BANDUNG</b><br/><b>OKTOBER 2026</b>", cover_title))
    story.append(PageBreak())

    # =========================================================================
    # BAB 1: PEMBUKAAN — POSISI PROGRAM SEKARANG (TIMELINE DOT-LINE)
    # =========================================================================
    story.append(Paragraph("1. PEMBUKAAN: POSISI CAPAIAN PROGRAM CHIP SAAT INI", section_style))
    story.append(Paragraph(
        "Laporan ini merangkum perancangan perangkat keras akselerator jaringan saraf tiruan pada papan FPGA "
        "<b>Sipeed Tang Nano 4K (Gowin GW1NSR-LV4C)</b> dalam proyek <i>WindEdgeChip</i>. Gambar 1 memetakan posisi kode "
        "<i>Register-Transfer Level</i> (RTL) yang telah selesai diprogram saat ini terhadap standar "
        "<i>Minimum Viable Product</i> (MVP) dan rencana pengembangannya.",
        body_style
    ))
    story.append(KeepTogether([
        Spacer(1, 3),
        build_progress_timeline_diagram(),
        Paragraph("Gambar 1. Garis Progres (Milestone Dot-Line) Posisi Program Chip Saat Ini terhadap Standar MVP dan Rencana Improvisasi", caption_style)
    ]))
    story.append(Paragraph(
        "Mengacu pada syarat MVP Lapisan 3 (tersedianya desain sirkuit terpadu/<i>IP Core</i> yang teruji fungsional beserta "
        "profil daya dan latensi), <b>program chip yang kami bangun saat ini (Titik 3) sudah memenuhi syarat MVP perangkat keras</b>. "
        "Seluruh modul RTL telah disintesis, ditanamkan ke memori <i>embFlash</i> FPGA, dan diuji secara fisik melalui "
        "<i>Hardware-in-the-Loop</i> (HIL). Oleh karena itu, tahapan kerja selanjutnya difokuskan pada <b>penyempurnaan "
        "ketahanan protokol sistem (Titik 4)</b> dan <b>pengembangan fitur tambahan di luar MVP (Titik 5)</b> dengan memanfaatkan "
        "sekitar 80% kapasitas logika FPGA yang masih tersedia.",
        body_style
    ))

    # =========================================================================
    # BAB 2: RINGKASAN MASALAH
    # =========================================================================
    story.append(Paragraph("2. RINGKASAN MASALAH", section_style))
    story.append(Paragraph(
        "Turbin angin skala mikro di lingkungan perkotaan menghadapi aliran udara yang sangat fluktuatif akibat halangan bangunan. "
        "Secara aerodinamika, daya mekanis turbin berbanding lurus dengan pangkat tiga kecepatan angin (<b>P = 0,5 × ρ × A × v³ × Cp</b>). "
        "Berdasarkan rekaman data 11 bulan di Gedung PAU ITB [1], kenaikan kecepatan angin dari 2,05 m/s menjadi 3,80 m/s (1,85×) "
        "menaikkan daya keluaran dari 5,6 W menjadi 158,7 W (<b>28× lipat</b>). Tanpa prediksi daya satu jam ke depan, pengelola "
        "mikrogrid kesulitan mengatur penyimpanan baterai dan pencadangan beban [7], sehingga energi turbin saat ini masih dibuang "
        "ke resistor beban (<i>dump load</i>). Penerapan model prediksi langsung pada perangkat tepi (<i>edge</i>) menghadapi "
        "empat kendala perangkat keras:",
        body_style
    ))
    story.append(Paragraph(
        "1. <b>Konsumsi Daya Statis Komputer Mini yang Tidak Proporsional:</b> Sistem pemantauan terdahulu [1] menggunakan "
        "Raspberry Pi 4 Model B. Meski rata-rata utilisasi CPU hanya ~2% dan RAM ~8%, perangkat tersebut tetap menyerap daya "
        "<b>3–5 Watt</b> secara terus-menerus. Saat angin lemah dan turbin hanya menghasilkan 5–10 W, sebagian besar energi "
        "habis dikonsumsi oleh perangkat pemantaunya sendiri.<br/>"
        "2. <b>Inefisiensi Siklus Instruksi Berurutan (<i>Von Neumann</i>):</b> Prosesor umum mengeksekusi instruksi satu per satu "
        "melalui tahapan <i>fetch-decode-execute</i>. Untuk jaringan saraf dengan ribuan operasi perkalian-akumulasi (MAC), "
        "siklus waktu dan energi banyak terbuang pada lalu lintas bus instruksi.<br/>"
        "3. <b>Keterbatasan Ruang untuk Prosesor Lunak (<i>Soft-Core CPU</i>) pada FPGA Kecil:</b> Pendekatan seperti "
        "<i>CFU Playground</i> [4] menanamkan prosesor RISC-V di dalam FPGA. Namun, pada FPGA berkapasitas kecil (4.000–5.000 LUT), "
        "prosesor lunak tersebut menyita lebih dari 70% gerbang logika, sehingga menyisakan ruang yang sempit untuk unit akselerator.<br/>"
        "4. <b>Risiko Ketergantungan Koneksi Cloud:</b> Pengiriman data mentah ke server eksternal rentan terputus saat gangguan "
        "jaringan, sedangkan pengendalian pembangkit membutuhkan waktu respons yang pasti (<i>deterministic latency</i>) di lokasi.",
        body_no_indent
    ))

    # =========================================================================
    # BAB 3: IDE SOLUSI PERANGKAT KERAS & CHIP
    # =========================================================================
    story.append(Paragraph("3. IDE SOLUSI: ARSITEKTUR HETEROGEN DAN AKSELERATOR MAC4", section_style))
    story.append(Paragraph(
        "Kami memisahkan tugas komunikasi dan tugas komputasi matriks ke dalam dua perangkat keras yang bekerja berdampingan:",
        body_style
    ))
    story.append(Paragraph(
        "• <b>ESP32 sebagai Pengendali I/O dan Prapemrosesan (&lt; 0,5 W):</b> Membaca sensor arus-tegangan PZEM-017 dan stasiun "
        "cuaca melalui Modbus RTU (RS-485), mengambil data cuaca BMKG [2], menyusun 16 fitur masukan, mengkuantisasinya ke format "
        "bilangan bulat 8-bit bertanda (<i>signed INT8</i>) [3], lalu mengirimkan hasilnya ke dashboard melalui MQTT.<br/>"
        "• <b>FPGA Sipeed Tang Nano 4K (Gowin GW1NSR-LV4C) sebagai Ko-Prosesor Inferensi:</b> Menjalankan modul "
        "<b>Standalone Pipelined MAC4 Engine</b> yang dirancang langsung pada tingkat gerbang logika (RTL) tanpa bantuan prosesor "
        "lunak [5]. Empat jalur perkalian-akumulasi bekerja paralel di bawah kendali mesin status terbatas (FSM), sehingga "
        "seluruh jaringan saraf selesai dihitung secara deterministik dengan daya puluhan miliwatt.",
        body_no_indent
    ))

    col_widths = [3.6*cm, 4.4*cm, 3.7*cm, 3.7*cm]
    table_data = [
        [
            Paragraph("Paradigma Arsitektur", table_header),
            Paragraph("Mekanisme Eksekusi", table_header),
            Paragraph("Keunggulan Utama", table_header),
            Paragraph("Keterbatasan pada Edge Kecil", table_header)
        ],
        [
            Paragraph("<b>1. Soft-Core RISC-V + CFU</b>", table_text),
            Paragraph("Menanam CPU lunak (VexRiscv) di FPGA ditambah instruksi kustom [4].", table_text),
            Paragraph("Fleksibel; pemrograman berbasis bahasa C/C++.", table_text),
            Paragraph("CPU lunak menyita &gt;70% LUT FPGA kecil; percepatan terbatas.", table_text)
        ],
        [
            Paragraph("<b>2. Systolic Array (TPU-like)</b>", table_text),
            Paragraph("Kisi 2D unit pemroses (PE) yang mengalirkan data antar-tetangga [6].", table_text),
            Paragraph("Throughput tinggi untuk matriks berdimensi besar.", table_text),
            Paragraph("Penjadwalan rumit; utilisasi rendah pada vektor kecil (N = 16).", table_text)
        ],
        [
            Paragraph("<b>3. Recurrent Engine (LSTM)</b>", table_text),
            Paragraph("Sirkuit sekuensial dengan tabel pencari (LUT) fungsi tanh/sigmoid.", table_text),
            Paragraph("Menangkap memori urutan waktu secara intrinsik.", table_text),
            Paragraph("Galat aproksimasi non-linier; boros area logika dan blok DSP.", table_text)
        ],
        [
            Paragraph("<b>4. Standalone Pipelined MAC4 (Desain Kami)</b>", table_text),
            Paragraph("Jalur pipa 4 pengali paralel + pohon penjumlah yang diatur FSM.", table_text),
            Paragraph("<b>Tanpa beban CPU; hemat area logika (20% LUT) dan daya</b> [5].", table_text),
            Paragraph("Topologi terikat jadwal FSM; perubahan layer butuh sintesis ulang.", table_text)
        ]
    ]
    t1 = Table(table_data, colWidths=col_widths, repeatRows=1)
    t1.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#E1EEFC')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#285591')),
        ('TOPPADDING', (0,0), (-1,-1), 3.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3.5),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(KeepTogether([
        Paragraph("Tabel 1. Perbandingan Pendekatan Arsitektur Akselerasi ML pada FPGA", caption_style),
        t1
    ]))
    story.append(Spacer(1, 5))

    # =========================================================================
    # BAB 4: DIAGRAM BLOK SISTEM BERSTANDAR UML 2.5
    # =========================================================================
    story.append(Paragraph("4. DIAGRAM BLOK SISTEM DAN CHIP BERSTANDAR UML 2.5", section_style))
    story.append(Paragraph(
        "Spesifikasi antarmuka antara subsistem mikrokontroler (<i>edge/</i>), model pembelajaran mesin (<i>ml/</i>), dan perangkat "
        "keras FPGA (<i>hw/</i>) didokumentasikan menggunakan standar <b>Unified Modeling Language (UML 2.5)</b> [8] pada tiga tingkat abstraksi:",
        body_style
    ))

    story.append(Paragraph("4.1 UML Component Diagram: Arsitektur Sistem Terintegrasi", subsection_style))
    story.append(Paragraph(
        "Gambar 2 menunjukkan hubungan antar-komponen fisik sistem menggunakan stereotip UML standar beserta protokol komunikasinya "
        "(Modbus RTU, UART 115200 bps, dan MQTT).",
        body_style
    ))
    story.append(KeepTogether([
        Spacer(1, 2),
        build_uml_system_diagram(),
        Paragraph("Gambar 2. Diagram Blok Komponen Sistem Terintegrasi (UML 2.5 Component Diagram) WindEdgeChip", caption_style)
    ]))

    story.append(Paragraph("4.2 UML Composite Structure / Internal Block Diagram (IBD): Arsitektur Internal Chip", subsection_style))
    story.append(Paragraph(
        "Gambar 3 merinci struktur internal entitas puncak <b>top_soc.v</b> pada chip Gowin GW1NSR-LV4C, memperlihatkan aliran bus "
        "data bertanda (<i>signed [7:0]</i> dan <i>signed [31:0]</i>) serta sinyal kendali di antara ketujuh sub-modul RTL.",
        body_style
    ))
    story.append(KeepTogether([
        Spacer(1, 2),
        build_uml_ibd_diagram(),
        Paragraph("Gambar 3. Diagram Struktur Komposit Internal (UML 2.5 Internal Block Diagram) pada Chip FPGA top_soc.v", caption_style)
    ]))

    story.append(Paragraph("4.3 UML State Machine Diagram: Kendali Urutan Eksekusi FSM", subsection_style))
    story.append(Paragraph(
        "Gambar 4 memetakan transisi kedelapan status pada modul <b>fsm_controller.v</b>. Setiap neuron diproses melalui siklus "
        "perkalian-akumulasi (4 siklus pada Lapisan 1 dan 3; 8 siklus pada Lapisan 2) ditambah 1 siklus pasca-pemrosesan (<i>POST</i>). "
        "Total eksekusi seluruh jaringan selalu konstan pada <b>310 siklus clock</b> (160 + 144 + 5 + 1).",
        body_style
    ))
    story.append(KeepTogether([
        Spacer(1, 2),
        build_uml_fsm_diagram(),
        Paragraph("Gambar 4. Diagram Mesin Status (UML 2.5 State Machine Diagram) Pengendali Urutan fsm_controller.v", caption_style)
    ]))

    # =========================================================================
    # BAB 5: KONDISI ARSITEKTUR EKSISTING, EVALUASI MVP, & RENCANA IMPROVISASI
    # =========================================================================
    story.append(Paragraph("5. ARSITEKTUR CHIP EKSISTING, EVALUASI MVP, DAN RENCANA IMPROVISASI", section_style))

    story.append(Paragraph("5.1 Kondisi Arsitektur Chip yang Sudah Diprogram Saat Ini (Existing RTL)", subsection_style))
    story.append(Paragraph(
        "Implementasi RTL saat ini terdiri atas enam berkas Verilog (IEEE 1364-2001) di direktori <i>hw/rtl/</i> yang dikelompokkan "
        "ke dalam tiga fungsi utama:",
        body_style
    ))
    story.append(Paragraph(
        "1. <b>Antarmuka Serial Berkecepatan Tinggi &amp; Pengemas Paket Berbingkai (<i>top_soc.v, uart_rx.v, uart_tx.v</i>):</b> "
        "Beroperasi pada clock kristal <b>27 MHz</b> dengan laju komunikasi berkecepatan tinggi <b>921.600 bps (8-N-1)</b>, "
        "memangkas waktu transmisi dari ~1,65 ms menjadi hanya <b>~206 μs (8× lebih cepat)</b>. Protokol mengadopsi bingkai paket "
        "(<i>packet framing</i>) 19-byte <b>[0xAA, 0x55, 16 Byte Fitur INT8, CRC-8]</b> dengan proteksi kesalahan perangkat keras "
        "<b>CRC-8 CCITT (Polinomial 0x07, Inisialisasi 0x00)</b> dan <i>Watchdog Timeout</i> (10 ms). Jika paket korup atau terputus di tengah, "
        "FSM otomatis kembali ke <i>WAIT_SYNC1</i> dan mengirim kode status <i>0xE1</i> tanpa memproses data sampah. Saat komputasi selesai, "
        "modul membalas dengan paket berbingkai 7-byte: <b>[0x55, 0xAA, STATUS (0x00), PREDIKSI, CYC_MSB, CYC_LSB, CRC-8]</b>.<br/>"
        "2. <b>Memori Bobot BSRAM 32-Bit dengan <i>Prefetch</i> Alamat (<i>weights_rom.v, top.v</i>):</b> Sebanyak 1.040 bobot "
        "INT8 dikemas menjadi 260 kata 32-bit (<i>weights32.hex</i>) di dalam satu blok memori keras <b>Gowin BSRAM SPX9</b> "
        "(mode <i>pROM</i>). Untuk mengimbangi latensi baca BSRAM sebesar 1 siklus clock, penunjuk alamat <i>prefetch</i> "
        "(<i>step_addr</i>) dimajukan satu siklus lebih awal saat sinyal <i>start</i> aktif, sehingga 4 bobot INT8 dapat "
        "diumpankan ke pengali setiap siklus tanpa jeda (<i>zero wait-state</i>).<br/>"
        "3. <b>Jalur Hitung MAC4 (<i>mac4_engine.v</i>) dan Pasca-Pemrosesan (<i>post_process.v</i>):</b> Empat pasang aktivasi "
        "dan bobot INT8 dikalikan secara paralel dan dijumlahkan ke akumulator 32-bit. Pada siklus akhir tiap neuron, hasil "
        "akumulasi ditambahkan dengan bias 32-bit (<i>bias.hex</i>), dikalikan faktor skala tetap (<i>mult_scale = 32</i>), "
        "digeser ke kanan 8-bit (<b>&gt;&gt;&gt; 8</b>), melewati fungsi aktivasi ReLU, dan dibatasi pada rentang [0, +127].",
        body_no_indent
    ))

    res_data = [
        [
            Paragraph("Sumber Daya / Parameter", table_header),
            Paragraph("Pemakaian Aktual", table_header),
            Paragraph("Persentase / Nilai", table_header),
            Paragraph("Peran dalam Arsitektur Eksisting", table_header)
        ],
        [
            Paragraph("<b>Gerbang Logika (LUT4 + ALU)</b>", table_text),
            Paragraph("1.091 / 4.608 unit (1.014 LUT, 77 ALU)", table_text),
            Paragraph("<b>24%</b>", table_header),
            Paragraph("Logika FSM, kalkulator CRC-8 hardware, watchdog, dan UART 921.6k.", table_text)
        ],
        [
            Paragraph("<b>Register Flip-Flop (DFF)</b>", table_text),
            Paragraph("773 / 3.573 register (0 Latch)", table_text),
            Paragraph("<b>22%</b>", table_header),
            Paragraph("Penyimpan buffer in_buf[16], h1_buf[32], h2_buf[16], FSM framing, &amp; akumulator.", table_text)
        ],
        [
            Paragraph("<b>Embedded Block SRAM (BSRAM)</b>", table_text),
            Paragraph("1 / 10 blok (Mode pROM SPX9)", table_text),
            Paragraph("<b>10%</b>", table_header),
            Paragraph("Memori bobot 260×32-bit (mengeluarkan 4 bobot INT8 per siklus).", table_text)
        ],
        [
            Paragraph("<b>Blok DSP (MULTADDALU18X18)</b>", table_text),
            Paragraph("2 / 8 unit pengali keras", table_text),
            Paragraph("<b>25%</b>", table_header),
            Paragraph("Unit perkalian paralel MAC4 dan pengali skala pasca-proses.", table_text)
        ],
        [
            Paragraph("<b>Waktu Eksekusi &amp; Latensi</b>", table_text),
            Paragraph("310 siklus clock @ 27 MHz", table_text),
            Paragraph("<b>11,48 μs</b>", table_header),
            Paragraph("L1: 160 siklus, L2: 144 siklus, L3: 5 siklus, DONE: 1 siklus.", table_text)
        ],
        [
            Paragraph("<b>Round-Trip Latency Total</b>", table_text),
            Paragraph("Transmisi 19B (204 μs) + Hitung (11,48 μs) + Balas 7B (75 μs)", table_text),
            Paragraph("<b>290,74 μs</b>", table_header),
            Paragraph("<b>7,8× lebih cepat</b> dibanding legacy 115.2k (2.264 μs); throughput ~3.440 pkt/s.", table_text)
        ],
        [
            Paragraph("<b>Konsumsi Daya &amp; Energi</b>", table_text),
            Paragraph("Statis: 26,02 mW | Dinamis: 0,85 mW", table_text),
            Paragraph("<b>26,87 mW</b>", table_header),
            Paragraph("Energi inferensi ≈ 0,31 μJ per prediksi (&gt;110× lebih rendah dari Raspi 4).", table_text)
        ],
        [
            Paragraph("<b>Pinout Fisik QFN48P (LVCMOS18)</b>", table_text),
            Paragraph("clk:45 | rst_n:14 | rx:44 | tx:46", table_text),
            Paragraph("<b>6 / 39 I/O (16%)</b>", table_header),
            Paragraph("Pin 10: led_busy (Active-Low), Pin 13: led_done, UART 921600 bps.", table_text)
        ]
    ]
    t2 = Table(res_data, colWidths=[3.8*cm, 4.1*cm, 2.3*cm, 5.2*cm], repeatRows=1)
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#DEF2E1')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#2D783C')),
        ('TOPPADDING', (0,0), (-1,-1), 3.2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3.2),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(KeepTogether([
        Paragraph("Tabel 2. Hasil Sintesis, Pemetaan Pin (tang_nano_4k.cst), dan Profil Kinerja Aktual pada Gowin GW1NSR-LV4C", caption_style),
        t2
    ]))
    story.append(Spacer(1, 5))

    story.append(Paragraph("5.2 Evaluasi terhadap MVP dan Keterbatasan Desain Saat Ini", subsection_style))
    story.append(Paragraph(
        "Secara fungsionalitas perangkat keras inti (L3), <b>program yang ada sekarang sudah memenuhi target MVP secara andal</b>: "
        "seluruh komputasi berjalan di atas silikon fisik Tang Nano 4K, komunikasi serial telah diproteksi penuh oleh bingkai paket "
        "dan CRC-8, serta laju baudrate telah diakselerasi ke 921.600 bps. Adapun fokus penyempurnaan berikutnya diarahkan pada:",
        body_style
    ))
    story.append(Paragraph(
        "• <b>Parameter Skala Kuantisasi Masih Seragam:</b> Nilai <i>mult_scale = 32</i> masih disamakan untuk semua lapisan, dan "
        "neuron keluaran masih melewati pemotongan ReLU positif.<br/>"
        "• <b>Bobot Model Bersifat Statis di <i>pROM</i>:</b> Pembaruan bobot hasil pelatihan ulang musiman masih memerlukan sintesis "
        "dan <i>flashing</i> ulang bitstream FPGA.",
        body_no_indent
    ))

    story.append(Paragraph("5.3 Rencana Improvisasi Chip Selanjutnya", subsection_style))
    story.append(Paragraph(
        "Dengan utilisasi silikon yang masih sangat lapang (<b>24% LUT, 22% Register, dan 10% BSRAM</b>), rencana pengembangan "
        "selanjutnya dipetakan pada Tabel 3.",
        body_style
    ))

    imp_data = [
        [
            Paragraph("Tahapan", table_header),
            Paragraph("Fokus Improvisasi", table_header),
            Paragraph("Implementasi RTL dan Manfaat di Lapangan", table_header)
        ],
        [
            Paragraph("<b>Tahap A: Penguatan MVP Sistem</b>", table_text),
            Paragraph("<b>1. Framing 0xAA/0x55, CRC-8, &amp; 921.6 kbps UART</b>", table_text),
            Paragraph("<b>[SELESAI &amp; LOLOS AUDIT]</b> Paket 19B berbingkai + CRC-8 hardware menolak paket korup (status 0xE1); baudrate 921600 bps memangkas latensi transfer dari 1,65 ms ke 206 μs.", table_text)
        ],
        [
            Paragraph("<b>Tahap A: Penguatan MVP Sistem</b>", table_text),
            Paragraph("<b>2. Skala Kuantisasi Per-Lapisan (<i>Per-Layer Scale</i>)</b>", table_text),
            Paragraph("Menambahkan multiplexer <i>mult_scale[layer_sel]</i> untuk tiap lapisan serta opsi melewati ReLU (<i>linear bypass</i>) pada lapisan output ke-3 guna menjaga presisi regresi.", table_text)
        ],
        [
            Paragraph("<b>Tahap B: Pengembangan Melebihi MVP (<i>Beyond MVP</i>)</b>", table_text),
            Paragraph("<b>3. Pembaruan Bobot via UART (<i>Writable BSRAM</i>)</b>", table_text),
            Paragraph("Mengubah konfigurasi BSRAM dari <i>pROM</i> menjadi <b>Dual-Port SRAM</b> sehingga ESP32 dapat memperbarui bobot model di lapangan melalui paket khusus (header 0xBB) tanpa <i>re-flashing</i>.", table_text)
        ],
        [
            Paragraph("<b>Tahap B: Pengembangan Melebihi MVP (<i>Beyond MVP</i>)</b>", table_text),
            Paragraph("<b>4. Antarmuka SPI Cepat &amp; <i>Clock-Gating</i></b>", table_text),
            Paragraph("Menambahkan jalur SPI Slave untuk memangkas waktu transfer data menjadi &lt;10 μs dan mematikan sinyal clock ke <i>mac4_engine</i> saat status IDLE untuk menekan daya dinamis.", table_text)
        ],
        [
            Paragraph("<b>Tahap B: Pengembangan Melebihi MVP (<i>Beyond MVP</i>)</b>", table_text),
            Paragraph("<b>5. Analisis Getaran Turbin &amp; Sintesis ASIC</b>", table_text),
            Paragraph("Memanfaatkan sisa LUT dan DSP kosong untuk memproses sinyal getaran mekanis bantalan turbin (deteksi anomali dini), serta memetakan RTL ke alur <b>OpenLane + SkyWater SKY130 (130 nm)</b>.", table_text)
        ]
    ]
    t3 = Table(imp_data, colWidths=[3.4*cm, 4.1*cm, 7.9*cm], repeatRows=1)
    t3.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#FFF6D6')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#A57D14')),
        ('TOPPADDING', (0,0), (-1,-1), 3.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3.5),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(KeepTogether([
        Paragraph("Tabel 3. Rencana Improvisasi Arsitektur Chip FPGA", caption_style),
        t3
    ]))
    story.append(Spacer(1, 6))

    # =========================================================================
    # BAB 6: TIGA PERTANYAAN MAHASISWA KEPADA MENTOR DEEPTECH (TANPA JAWABAN)
    # =========================================================================
    story.append(Paragraph("6. DAFTAR PERTANYAAN KEPADA MENTOR DEEPTECH (PERSPEKTIF MAHASISWA TERHADAP REALITAS LAPANGAN)", section_style))
    story.append(Paragraph(
        "Sebagai mahasiswa yang mengembangkan purwarupa ini di lingkungan laboratorium kampus, kami ingin memahami kondisi "
        "operasional yang sesungguhnya di industri. Berikut adalah tiga pertanyaan yang ingin kami diskusikan bersama Mentor:",
        body_style
    ))

    story.append(Paragraph("6.1 Pertanyaan 1: Perangkat Eksisting, Kendala, dan Kebutuhan Riil di Lapangan Saat Ini", subsection_style))
    story.append(Paragraph(
        "“Sejauh ini pengalaman kami masih terbatas pada pengamatan turbin angin skala kecil di lingkungan kampus yang sebelumnya "
        "dipantau menggunakan Raspberry Pi. Kami ingin bertanya kepada Bapak/Ibu Mentor: pada instalasi pembangkit energi terbarukan "
        "atau mikrogrid di lapangan saat ini, perangkat pemroses dan pengontrol apa yang sebenarnya paling umum digunakan? Apa "
        "kendala utama dari perangkat yang dipakai sekarang, dan fitur atau kemampuan apa yang paling dibutuhkan oleh operator di lapangan?”",
        quote_box_style
    ))

    story.append(Paragraph("6.2 Pertanyaan 2: Kecukupan Solusi Sederhana vs. Kebutuhan Penggunaan FPGA di Lapangan", subsection_style))
    story.append(Paragraph(
        "“Dalam proyek ini kami merancang akselerator pada chip FPGA untuk mendampingi mikrokontroler dalam memprediksi daya secara "
        "cepat dan hemat energi. Menurut pandangan Bapak/Ibu Mentor, jika melihat dinamika masalah di lapangan saat ini, apakah "
        "kebutuhan pemantauan dan prediksi daya sebenarnya sudah cukup diselesaikan dengan pendekatan yang lebih sederhana—seperti "
        "mikrokontroler standar atau PLC industri—ataukah memang terdapat kondisi kasus lapangan tertentu yang menuntut penggunaan "
        "perangkat keras tingkat lanjut seperti FPGA ini?”",
        quote_box_style
    ))

    story.append(Paragraph("6.3 Pertanyaan 3: Prioritas Pengembangan Perangkat Keras untuk Menghadapi Kondisi Lapangan", subsection_style))
    story.append(Paragraph(
        "“Saat ini desain inti pada FPGA kami sudah berjalan memenuhi fungsi dasar (MVP) dan masih menyisakan sekitar 80% kapasitas "
        "chip yang kosong. Mengingat kondisi lingkungan lapangan yang berat—mulai dari derau kelistrikan generator, fluktuasi catu "
        "daya, cuaca ekstrem, hingga perubahan karakteristik mekanis turbin seiring waktu—menurut pengalaman Bapak/Ibu Mentor, "
        "bagian mana yang sebaiknya menjadi prioritas improvisasi perangkat keras kami agar sistem ini benar-benar andal saat "
        "diterapkan di lapangan?”",
        quote_box_style
    ))

    # =========================================================================
    # BAB 7: KESIMPULAN & DAFTAR PUSTAKA
    # =========================================================================
    story.append(Paragraph("7. KESIMPULAN", section_style))
    story.append(Paragraph(
        "Arsitektur akselerator <b>Standalone Pipelined MAC4</b> yang diimplementasikan pada FPGA <b>Gowin GW1NSR-LV4C "
        "(Sipeed Tang Nano 4K)</b> saat ini telah memenuhi target MVP perangkat keras dengan latensi terukur 11,48 μs, konsumsi "
        "daya 26,84 mW, dan penggunaan ruang logika 20% LUT. Melalui rencana penyempurnaan protokol komunikasi serta masukan dari "
        "Mentor terkait dinamika operasional di lapangan, rancangan ini diharapkan dapat berkembang menjadi modul komputasi tepi "
        "yang praktis dan andal untuk sistem energi terbarukan.",
        body_style
    ))

    story.append(Spacer(1, 5))
    story.append(Paragraph("DAFTAR PUSTAKA", section_style))
    references = [
        "[1] G. G. Hartanto, \"Sistem Monitoring Kinerja PLTB Berbasis IoT Menggunakan Metode Support Vector Machine Melalui Protokol Modbus,\" Tugas Akhir, Program Studi Sarjana Terapan Teknik Elektronika, Politeknik Negeri Bandung, 2026.",
        "[2] Badan Meteorologi, Klimatologi, dan Geofisika (BMKG), \"Data Prakiraan Cuaca Terbuka Berbasis Wilayah Administrasi Kelurahan,\" https://api.bmkg.go.id/publik/prakiraan-cuaca, diakses Okt. 2026.",
        "[3] B. Jacob et al., \"Quantization and training of neural networks for efficient integer-arithmetic-only inference,\" in Proc. IEEE Conf. on Computer Vision and Pattern Recognition (CVPR), 2018, pp. 2704-2713.",
        "[4] S. Prakash et al., \"CFU Playground: Full-stack open-source framework for Tiny Machine Learning (TinyML) acceleration on FPGAs,\" in 2023 IEEE Int. Symp. on Performance Analysis of Systems and Software (ISPASS), 2023, pp. 157-167.",
        "[5] H. Borras et al., \"Open-source FPGA-ML codesign for the MLPerf Tiny benchmark,\" arXiv preprint arXiv:2206.11791, 2022.",
        "[6] N. P. Jouppi et al., \"In-datacenter performance of a tensor processing unit,\" in Proc. 44th Annual Int. Symp. on Computer Architecture (ISCA), 2017, pp. 1-12.",
        "[7] PT PLN (Persero), Rencana Usaha Penyediaan Tenaga Listrik (RUPTL) 2025-2034, Kementerian Energi dan Sumber Daya Mineral Republik Indonesia, 2025.",
        "[8] Object Management Group (OMG), OMG Unified Modeling Language (OMG UML) Specification, Version 2.5.1, formal/2017-12-05, 2017."
    ]
    for ref in references:
        story.append(Paragraph(ref, bib_style))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF berhasil diperbarui: {filename}")


if __name__ == '__main__':
    output_pdf = r"c:\Users\ThinkPad\Documents\wind-edge-chip\hw\docs\riset_akselerasi_fpga.pdf"
    build_pdf(output_pdf)
