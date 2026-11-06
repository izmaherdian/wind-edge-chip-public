# edge/ta/raspi/ — Salinan program dari Raspi turbin

Ditarik 20 Okt 2026 lewat SSH dari `citamonitoring2025@raspberrypi` (`10.18.117.195`; di `~/.ssh/config` sebagai `RASPI-TURBIN`). Isinya salinan apa adanya, hanya untuk acuan. Tidak ada yang diubah di Raspi.

| File di sini | Asal di Raspi | Isi |
|---|---|---|
| `nodered_duadata.py` | `~/Desktop/NodeRED_DuaData.py` | **Program yang sedang berjalan.** Isinya sama persis dengan `../akuisisi_raspi.py` (md5 `845ff2d0…`): PZEM-017 + stasiun cuaca (Modbus), Arduino (serial), SVM, MQTT `TurbinAngin/*` tiap 3 detik |
| `turbine2.py` | `~/Desktop/Turbine2.py` | Varian untuk Turbin 2: PZEM + Arduino + SVM, MQTT `TurbinAngin2/*` |
| `nodered_duadata_gpio.py` | `~/Downloads/NodeRED_DuaData.py` | Varian: anemometer langsung di GPIO 17 (18 celah, faktor 2,3), interval 1 detik, tanpa Arduino |
| `nodered_duadata_lama.py` | `~/Desktop/NodeRED_DuaData.py.save` | Versi lama (Mar 2026), tanpa ML |
| `nodered_uji_mqtt.py` | `~/Desktop/NodeRED.py` | Uji kirim data acak ke MQTT |
| `modbus_config.py`, `settingpzem.py` | `~/Desktop/` | Utilitas membaca/mengatur parameter PZEM lewat Modbus |
| `nodered_duadata.service` | `/etc/systemd/system/` | Service systemd: menjalankan `NodeRED_DuaData.py` dengan venv, restart otomatis |
| `crontab.txt` | `crontab -l` | **Sejak 22 Okt 2026:** `jaga_sistem.sh` tiap 5 menit, `cek_internet.sh` tiap 10 menit, reboot mingguan Minggu 03.00 (reboot harian 00.00/12.00 dihapus, disetujui Genis; lama: `~/crontab.bak-20261022`) |
| `jaga_sistem.sh` | `~/` | Penjaga berbasis kondisi: program akuisisi tidak mencatat 3 menit → restart service (reboot setelah 3x gagal); konverter USB-serial hilang 2 cek → reboot; memori < 300 MB → reboot; tidak reboot bila uptime < 20 menit. Kernel beku: watchdog hardware `RuntimeWatchdogSec=30s` di `/etc/systemd/system.conf` (lama: `.bak-20261022`) |
| `cek_internet.sh` | `~/` | **Sejak 22 Okt 2026:** ping 8.8.8.8/1.1.1.1; kalau gagal restart `wlan1` dan cek lagi; reboot hanya setelah gagal 3x berturut-turut (±30 menit). Log: `Internet putus, percobaan n/3` = belum reboot. Versi lama di `~/cek_internet.sh.bak-20261022` |
| `wifi_reconnect.sh` | `~/` | Ping 8.8.8.8; kalau gagal, matikan dan nyalakan `wlan1` (tidak dipakai di crontab) |
| `requirements-raspi.txt` | `pip freeze` venv | Versi paket (scikit-learn 1.8.0, numpy 2.4.6, …) |

Model SVM (`*.pkl`) ada di `ml/ta/models/`. Log reboot ada di `data/raw/raspi/log_reboot.txt` (tidak masuk git).

**Temuan:** Raspi tidak menyimpan data secara lokal. Data hanya dikirim lewat MQTT ke `citaitb.com` lalu ditulis Node-RED ke Google Sheets. Antara 5 Apr dan 20 Okt tercatat **2.787 reboot karena internet mati** (1.766 di antaranya di bulan September). Selama internet mati, data hilang. Inilah penyebab sebagian besar celah di data.

Cara masuk ke Raspi, mengecek service, dan membaca log: lihat user guide di `docs/laporan-progress/`.
