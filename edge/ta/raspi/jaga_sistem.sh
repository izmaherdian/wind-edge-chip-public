#!/bin/bash
# Penjaga Raspi turbin (cron tiap 5 menit), pengganti reboot terjadwal 00.00/12.00 (22 Okt 2026, disetujui Genis).
# Prinsip: perbaiki dengan cara paling ringan dulu, reboot hanya bila perlu, dan tidak pernah reboot
# bila Raspi baru menyala < 20 menit (cegah reboot berulang). Semua tindakan dicatat di log_reboot.txt.
#   1. Program akuisisi (nodered_duadata) tidak mencatat "Waktu" selama 3 menit -> restart service;
#      reboot bila 3 kali restart berturut-turut tidak menolong.
#   2. Konverter USB-serial sensor (/dev/ttyUSB0, ttyUSB1) hilang pada 2 cek berturut-turut -> reboot.
#   3. Memori tersedia < 300 MB -> reboot.
# Internet ditangani cek_internet.sh; kernel beku ditangani watchdog hardware (RuntimeWatchdogSec di systemd).

LOG=/home/citamonitoring2025/log_reboot.txt
STATUS=/home/citamonitoring2025/.jaga_sistem
SERVICE=nodered_duadata
MIN_UPTIME_S=1200
MEM_MIN_MB=300

catat() { echo "$(date): [jaga] $*" >> "$LOG"; }
nilai() { grep -s "^$1=" "$STATUS" | cut -d= -f2; }
simpan() { { grep -sv "^$1=" "$STATUS"; echo "$1=$2"; } > "$STATUS.tmp"; mv "$STATUS.tmp" "$STATUS"; }
uptime_s() { cut -d. -f1 /proc/uptime; }

reboot_bila_boleh() {
    if [ "$(uptime_s)" -lt "$MIN_UPTIME_S" ]; then
        catat "perlu reboot ($1), ditunda: Raspi baru menyala $(( $(uptime_s) / 60 )) menit"
        return
    fi
    rm -f "$STATUS"
    echo "$(date): Reboot oleh penjaga sistem: $1" >> "$LOG"
    sudo /sbin/reboot
    exit 0
}

# 1. program akuisisi masih bekerja?
if systemctl is-active --quiet "$SERVICE" && \
   [ "$(journalctl -u "$SERVICE" --since "-3 min" --no-pager -o cat 2>/dev/null | grep -c 'Waktu')" -gt 0 ]; then
    simpan restart 0
else
    n=$(( $(nilai restart || echo 0) + 1 ))
    simpan restart "$n"
    if [ "$n" -ge 3 ]; then
        reboot_bila_boleh "program akuisisi macet walau sudah $((n - 1))x restart"
    else
        catat "program akuisisi tidak mencatat data 3 menit, restart service (percobaan $n)"
        sudo /bin/systemctl restart "$SERVICE"
    fi
fi

# 2. konverter USB-serial sensor ada?
if [ -e /dev/ttyUSB0 ] && [ -e /dev/ttyUSB1 ]; then
    simpan usb 0
else
    n=$(( $(nilai usb || echo 0) + 1 ))
    simpan usb "$n"
    if [ "$n" -ge 2 ]; then
        reboot_bila_boleh "konverter USB-serial sensor hilang ($(ls /dev/ttyUSB* 2>/dev/null | tr '\n' ' '))"
    else
        catat "konverter USB-serial sensor hilang, cek ulang 5 menit lagi"
    fi
fi

# 3. memori cukup?
tersedia=$(( $(awk '/MemAvailable/ {print $2}' /proc/meminfo) / 1024 ))
if [ "$tersedia" -lt "$MEM_MIN_MB" ]; then
    reboot_bila_boleh "memori tersedia tinggal $tersedia MB"
fi
