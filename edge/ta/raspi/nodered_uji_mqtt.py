import os
import paho.mqtt.client as mqtt
import time
import json
import random

# --- Konfigurasi MQTT ---
# Ganti dengan alamat IP atau hostname server eksternal Anda
MQTT_BROKER = "citaitb.com" 
MQTT_PORT = 1883           # Port default MQTT (biasanya 1883)
MQTT_TOPIC = "TurbinAngin" # Topik unik untuk data Anda
CLIENT_ID = "RaspberryPi4_Publisher"

MQTT_USER = "cita"
MQTT_PASS = os.environ.get("MQTT_PASS", "")



# --- Fungsi Callback ---
def on_connect(client, userdata, flags, reason_code, properties):
    # 'reason_code' menggantikan 'rc' yang lama
    if reason_code == 0:
        print("Terhubung ke broker MQTT!")
    else:
        print(f"Gagal terhubung, kode: {reason_code}")

# # Dipanggil saat koneksi berhasil dibuat
# def on_connect(client, userdata, flags, rc):
#     if rc == 0:
#         print("Terhubung ke broker MQTT!")
#     else:
#         print(f"Gagal terhubung, kode: {rc}")
# 
# # --- Inisialisasi Klien MQTT ---
# client = mqtt.Client(CLIENT_ID)

# Tetapkan API versi 2.0 saat membuat klien
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, CLIENT_ID)
client.on_connect = on_connect

client.username_pw_set(username=MQTT_USER, password=MQTT_PASS)

try:
    # Coba terhubung ke broker
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
except Exception as e:
    print(f"Error saat mencoba koneksi: {e}")
    exit()

# Mulai loop di thread terpisah untuk menangani koneksi dan callback
client.loop_start()

print(f"Mulai mengirim data ke topik: {MQTT_TOPIC} setiap 8 detik...")

# --- Loop Pengiriman Data ---
try:
    while True:
        # 1. Simulasikan pengambilan data sensor (ganti dengan data sensor asli Anda)
        suhu = round(random.uniform(20.0, 30.0), 2)
        kelembaban = round(random.uniform(50.0, 70.0), 2)
        
        # 2. Buat payload dalam format JSON
        payload_data = str(suhu)
#             "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
#             "suhu_c": suhu,
#             "kelembaban_persen": kelembaban,
#             "device": "Raspi4"
        
        # Konversi objek Python (dict) ke string JSON
#         payload_json = json.dumps(payload_data)
        
        # 3. Kirim data
        result = client.publish(MQTT_TOPIC, payload_data, qos=1)
        status = result[0]
        
        if status == mqtt.MQTT_ERR_SUCCESS:
            print(f"Data terkirim: {payload_data}")
        else:
            print(f"Gagal mengirim pesan: {status}")

        time.sleep(8) # Kirim setiap 8 detik

except KeyboardInterrupt:
    print("Pengiriman data dihentikan.")

finally:
    # 4. Bersihkan dan putuskan koneksi
    client.loop_stop()
    client.disconnect()
    print("Koneksi MQTT terputus.")