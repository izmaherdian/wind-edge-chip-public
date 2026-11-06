#!/bin/bash
# Cek internet tiap 10 menit (crontab). Versi 22 Okt 2026: lebih sabar, Raspi tidak langsung reboot
# setiap internet putus sesaat (tiap reboot membuat data turbin berlubang).
#   1) ping 8.8.8.8 atau 1.1.1.1 berhasil  -> penghitung gagal direset, selesai.
#   2) gagal -> restart wlan1 (cara wifi_reconnect.sh), tunggu 30 detik, cek lagi.
#   3) reboot hanya bila gagal 3 kali berturut-turut (±30 menit tanpa internet).
# Versi lama (reboot pada kegagalan pertama): ~/cek_internet.sh.bak-20261022 di Raspi.

LOG=/home/citamonitoring2025/log_reboot.txt
GAGAL=/home/citamonitoring2025/.cek_internet_gagal

ada_internet() {
    /usr/bin/ping -c2 -W3 8.8.8.8 > /dev/null 2>&1 || /usr/bin/ping -c2 -W3 1.1.1.1 > /dev/null 2>&1
}

if ada_internet; then
    rm -f "$GAGAL"
    exit 0
fi

# Sambung ulang Wi-Fi USB dulu
sudo /sbin/ip link set wlan1 down
sleep 5
sudo /sbin/ip link set wlan1 up
sleep 30
if ada_internet; then
    echo "$(date): Internet putus, pulih setelah restart wlan1 (tanpa reboot)" >> "$LOG"
    rm -f "$GAGAL"
    exit 0
fi

n=$(( $(cat "$GAGAL" 2>/dev/null || echo 0) + 1 ))
if [ "$n" -ge 3 ]; then
    rm -f "$GAGAL"
    echo "$(date): Internet mati, melakukan reboot otomatis... (gagal $n kali berturut-turut)" >> "$LOG"
    sudo /sbin/reboot
else
    echo "$n" > "$GAGAL"
    echo "$(date): Internet putus, percobaan $n/3, belum reboot" >> "$LOG"
fi
