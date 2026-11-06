#!/bin/bash

# IP Address Google DNS untuk mengetes koneksi internet
SERVER=8.8.8.8

# Mengirim 2 paket ping ke server
ping -c2 ${SERVER} > /dev/null

# Jika ping gagal (exit status tidak sama dengan 0)
if [ $? != 0 ]
then
    echo "Koneksi terputus! Merestart wlan1..."

    # Matikan interface Wi-Fi USB
    sudo ip link set wlan1 down
    sleep 5

    # Nyalakan kembali interface Wi-Fi USB
    sudo ip link set wlan1 up
else
    echo "Koneksi aman."
fi
