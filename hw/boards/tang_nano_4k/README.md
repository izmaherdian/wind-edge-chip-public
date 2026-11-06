# Panduan Sipeed Tang Nano 4K (GW1NSR-LV4C) — Build, Upload & Debug

Dokumen ini menjelaskan prosedur lengkap untuk melakukan **kompilasi (build bitstream)**, **upload / flashing (SRAM & embFlash)**, dan **debugging telemetri hardware** pada board **Sipeed Tang Nano 4K**.

---

## 1. Spesifikasi Hardware & Pinout

* **Chipset**: Gowin GW1NSR-LV4C (`GW1NSR-LV4CQN48PC7/I6`, Paket QFN48P)
* **Kapasitas Logic**: 4.608 LUT4, 3.573 Flip-Flop, 180 kbit Embedded Block RAM (BSRAM)
* **Antarmuka USB**: Onboard FTDI dual-channel (Channel A: JTAG Programmer, Channel B: Virtual COM Port)
* **Konfigurasi Pin Fisik (`tang_nano_4k.cst`)**:

| Sinyal RTL | Pin Fisik QFN48 | Arah / Tipe | Keterangan |
| :--- | :--- | :--- | :--- |
| `clk` | **Pin 45** | Input | Kristal osilator onboard 27 MHz |
| `rst_n` | **Pin 14** | Input (Pull-up) | Tombol fisik Key S1 onboard (*Active-Low*) |
| `rx_pin` | **Pin 44** | Input (Pull-up) | UART RX (115200 bps, 8-N-1) $\leftarrow$ TX Host / ESP32 |
| `tx_pin` | **Pin 46** | Output (Pull-up) | UART TX (115200 bps, 8-N-1) $\rightarrow$ RX Host / ESP32 |
| `led_busy` | **Pin 10** | Output | Indikator LED Onboard (*Active-Low*, menyala saat inferensi berjalan) |
| `led_done` | **Pin 13** | Output | Indikator inferensi selesai (*Toggle* setiap paket selesai) |

> **Catatan Pinout**: Pin 11 pada paket QFN48P bukan merupakan GPIO umum, sehingga sinyal `led_done` dipetakan ke **Pin 13**.

---

## 2a. Alternatif Linux: toolchain open-source (diuji 20 Okt 2026)

Tanpa lisensi, tanpa Gowin EDA. Diuji di Ubuntu dengan OSS CAD Suite 2026-10-20:

```bash
# sekali: unduh OSS CAD Suite ke ~/tools/oss-cad-suite, lalu izin USB (Linux)
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6010", MODE="0664", GROUP="plugdev", TAG+="uaccess"' | sudo tee /etc/udev/rules.d/99-tang-nano.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
sudo usermod -aG dialout $USER

# build (bobot ditulis ulang dari ml/golden_model.py) + flash SRAM
source ~/tools/oss-cad-suite/environment
cd hw/boards/tang_nano_4k && make flash-sram     # make flash = embFlash (permanen)
```

Hasil dengan bobot hasil training (`ml/forecast/model/mlp_int8.json`): LUT4 1.126/4.608 (24%), DFF 733/3.456 (21%),
BSRAM 2/10, MULT9X9 4/32, **Fmax 85,7 MHz** setelah routing (lolos di 27 MHz), flash SRAM CRC sukses.

**Penting:** colok papan **langsung ke port laptop**. Lewat hub/dock bertingkat, chip USB papan gagal saat transfer
JTAG besar (`usb bulk write failed`, `ftdi_usb_reset failed`).

## 2. Persiapan Environment & Lisensi Gowin EDA

Gowin EDA membutuhkan lisensi aktif untuk mensintesis seri chip GW1NSR. Jika menggunakan Sipeed floating license server:

1. Buka file konfigurasi lisensi Gowin EDA:
   `C:\Gowin\Gowin_V1.9.12.04_x64\IDE\bin\gwlicense.ini`
2. Pastikan isi file sesuai format regex parser Gowin (`host:port`):
   ```ini
   [License]
   lic="106.55.34.119:10559"
   ```
3. Uji koneksi programmer ke board:
   ```powershell
   & "C:\Gowin\Gowin_V1.9.12.04_x64\Programmer\bin\programmer_cli.exe" --scan
   ```
   *Output yang diharapkan*: `Target Device: GW1NSR-4C (0x0100981B)`, `1 device(s) found!`.

---

## 3. Kompilasi & Build Bitstream

Eksekusi kompilasi RTL (Sintesis + Place & Route + Bitstream Packing) secara headless via CLI:

```powershell
# Jalankan dari root direktori proyek (c:\Users\ThinkPad\Documents\wind-edge-chip)
& "C:\Gowin\Gowin_V1.9.12.04_x64\IDE\bin\gw_sh.exe" build_tang_nano_4k.tcl
```

File bitstream hasil kompilasi akan berada di:
* `impl/pnr/wind_edge_chip.fs` (ukuran $\approx 1{,}7\ \text{MB}$)

---

## 4. Tata Cara Upload / Flashing ke Board

Gowin Programmer CLI menyediakan dua mode operasi utama:

### A. Mode SRAM (Volatile / Uji Coba Cepat)
* Mengunggah bitstream langsung ke sel SRAM FPGA.
* Sangat cepat ($\approx 25\text{--}30\ \text{detik}$).
* **Karakteristik**: Bitstream langsung berjalan seketika, namun akan terhapus saat daya/kabel USB dicabut.
* **Perintah**:
  ```powershell
  & "C:\Gowin\Gowin_V1.9.12.04_x64\Programmer\bin\programmer_cli.exe" --device GW1NSR-4C --operation_index 2 --fsFile "C:\Users\ThinkPad\Documents\wind-edge-chip\impl\pnr\wind_edge_chip.fs"
  ```

### B. Mode embFlash (Non-Volatile / Permanen)
* Menghapus (*bulk erase*) dan memprogram flash internal chip FPGA.
* Membutuhkan waktu $\approx 100\text{--}110\ \text{detik}$.
* **Karakteristik**: Bitstream tersimpan permanen. Setiap kali papan diberi daya (*power cycle*), FPGA otomatis memuat bitstream dari embFlash tanpa perlu di-flash ulang dari PC.
* **Perintah**:
  ```powershell
  & "C:\Gowin\Gowin_V1.9.12.04_x64\Programmer\bin\programmer_cli.exe" --device GW1NSR-4C --operation_index 5 --fsFile "C:\Users\ThinkPad\Documents\wind-edge-chip\impl\pnr\wind_edge_chip.fs"
  ```

---

## 5. Tata Cara Debugging & Pengujian Hardware

### A. Format Paket Komunikasi UART (Framed Packet & CRC-8)
* **Baudrate**: `921600 bps` (Default High-Speed, ~206 μs transfer) atau `115200 bps` (Legacy), 8-N-1.
* **Paket Kirim (Host $\rightarrow$ FPGA)**:
  * Total **19 byte**:
    * `Byte 0..1`: Sync Header `[0xAA, 0x55]`.
    * `Byte 2..17`: 16 fitur INT8 bertanda (`-128` s.d. `127`), urutan dan skalanya sesuai `docs/kontrak-kuantisasi.md`
      (lag daya, angin, $v^3$, arah, jam, $\rho$, prakiraan Open-Meteo).
    * `Byte 18`: 1 byte Checksum **CRC-8 CCITT** (Polinomial $x^8 + x^2 + x + 1$ / `0x07`, Init: `0x00`) atas 16 byte payload.
* **Paket Balas (FPGA $\rightarrow$ Host)**:
  * Total **7 byte**:
    * `Byte 0..1`: Sync Header `[0x55, 0xAA]`.
    * `Byte 2`: Kode Status (`0x00` = OK/SUCCESS, `0xE1` = CRC_ERROR, `0xE2` = TIMEOUT_ERROR).
    * `Byte 3`: Nilai prediksi daya dalam `signed INT8`.
    * `Byte 4`: Siklus clock komputasi MSB (`cycles[15:8]`).
    * `Byte 5`: Siklus clock komputasi LSB (`cycles[7:0]`).
    * `Byte 6`: Checksum **CRC-8 CCITT** atas 4 byte respons (`[Byte 2..5]`).
  * Total siklus komputasi riil: `(Byte 4 << 8) | Byte 5` ($310$ siklus clock atau $11{,}48\ \mu\text{s}$ @ 27 MHz).

### B. Pengujian Otomatis Hardware-in-the-Loop (HIL)

> **Kabel:** UART akselerator ada di **pin header 44 (RX) dan 46 (TX)**, bukan di USB-C bawaan papan. Untuk uji dari PC,
> pakai adaptor USB-TTL 3,3 V (mis. CP2102): TXD adaptor → pin 44, RXD adaptor → pin 46, GND → GND. Port
> `/dev/ttyUSB1` bawaan papan **tidak** tersambung ke akselerator (uji lewat port itu selalu timeout).
Tersedia skrip pengujian otomatis di `hw/scripts/test_uart_hil.py` untuk menguji paket biner terhadap referensi matematis *Golden Model*:

```powershell
# Jalankan HIL test ke port serial USB FTDI (contoh COM13) pada 921600 bps
python hw/scripts/test_uart_hil.py --port COM13 --baud 921600 --samples 5
```

*Contoh output verifikasi HIL:*
```text
No   | Expected   | FPGA HW    | Status     | Cycles   | Latency    | CRC8     | Hasil
------------------------------------------------------------------------------------
1    | 42         | 42         | OK (0x00)  | 310      |  11.48 us  | MATCH    | LULUS (MATCH)
2    | -18        | -18        | OK (0x00)  | 310      |  11.48 us  | MATCH    | LULUS (MATCH)
```

### C. Troubleshooting Fisik & Masalah Umum

1. **Error: "Cannot find any download cable"**:
   * Buka *Device Manager* di Windows. Pastikan driver FTDI USB Serial Port terinstal.
   * Pastikan kabel USB tipe-C yang digunakan mendukung transfer data (bukan hanya kabel charger daya).
2. **Error: "License check failed" pada `gw_sh.exe`**:
   * Periksa apakah koneksi internet aktif (karena floating server berada di `106.55.34.119:10559`).
   * Pastikan konfigurasi di `gwlicense.ini` tidak memakai format `port@host`.
3. **LED Busy (Pin 10) Terus Menyala**:
   * Menandakan FSM penerima UART belum menerima genap 16 byte.
   * Tekan tombol Reset `S1` (Pin 14) pada board untuk mereset FSM kembali ke kondisi `IDLE`.
4. **Data Prediksi Selalu 0**:
   * Periksa apakah file inisialisasi bobot BRAM `weights.hex` dan `bias.hex` sudah ter-generate di folder `hw/rtl/` sebelum melakukan sintesis.

