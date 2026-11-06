import os
import paho.mqtt.client as mqtt
import time
import serial
import minimalmodbus
import RPi.GPIO as GPIO
import math

# =========================
# ⚙️ KONFIGURASI UTAMA
# =========================
INTERVAL_DETIK = 1

# --- Modbus PZEM ---
DEVICE_ADDRESS = 0x01
BAUD_RATE = 9600
TIMEOUT = 1
PORT = '/dev/ttyUSB0'

# --- MQTT ---
MQTT_BROKER = "citaitb.com"
MQTT_PORT = 1883
MQTT_TOPIC_BASE = "TurbinAngin"
CLIENT_ID = "RaspberryPi4_PZEM_Anemometer"
MQTT_USER = "cita"
MQTT_PASS = os.environ.get("MQTT_PASS", "")

# --- Anemometer GPIO ---
WIND_PIN = 17

# ---------- KONSTANTA ANEMOMETER ----------
pi = math.pi
jml_celah = 18
radius = 0.08            # meter
calibrationFactor = 2.3

# =========================
# 📶 MQTT CALLBACK
# =========================
def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("✅ MQTT terhubung")
    else:
        print(f"❌ MQTT gagal, kode {reason_code}")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, CLIENT_ID)
client.on_connect = on_connect
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

# =========================
# 🔌 MODBUS INIT
# =========================
instrument = minimalmodbus.Instrument(PORT, DEVICE_ADDRESS)
instrument.serial.baudrate = BAUD_RATE
instrument.serial.bytesize = 8
instrument.serial.parity = serial.PARITY_NONE
instrument.serial.stopbits = 2
instrument.serial.timeout = TIMEOUT
instrument.mode = minimalmodbus.MODE_RTU

print("✅ Modbus PZEM siap")

# =========================
# 🌬️ ANEMOMETER INIT
# =========================
pulseCount = 0
lastMicros = 0

def addcount(channel):
    global pulseCount, lastMicros
    now = time.time_ns() // 1000
    if now - lastMicros >= 2000:
        pulseCount += 1
        lastMicros = now

GPIO.setmode(GPIO.BCM)
GPIO.setup(WIND_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(WIND_PIN, GPIO.FALLING, callback=addcount, bouncetime=1)

print("✅ Anemometer siap")

# =========================
# 📊 BACA PZEM
# =========================
def read_pzem_data():
    try:
        data = {}
        data['voltage'] = instrument.read_register(0x0000, 2, 4)
        data['current'] = instrument.read_register(0x0001, 2, 4)

        p_low = instrument.read_register(0x0002, 0, 4)
        p_high = instrument.read_register(0x0003, 0, 4)
        data['power'] = round(((p_high << 16) | p_low) * 0.1, 1)

        e_low = instrument.read_register(0x0004, 0, 4)
        e_high = instrument.read_register(0x0005, 0, 4)
        data['energy'] = (e_high << 16) | e_low

        return data
    except Exception as e:
        print("❌ Error PZEM:", e)
        return None

# =========================
# 🚀 MAIN LOOP
# =========================
print("\n🚀 Sistem berjalan (PZEM + Anemometer)\n")

try:
    while True:
        start = time.time()

        # --- Ambil pulsa anemometer ---
        pulses = pulseCount
        pulseCount = 0

        if pulses > 0:
            revolutions = pulses / jml_celah
            RPM = revolutions * 60
            speed_raw = 2 * pi * radius * RPM / 60
            windSpeed = speed_raw * calibrationFactor
        else:
            windSpeed = 0.0

        # --- Baca PZEM ---
        pzem_data = read_pzem_data()

        if pzem_data:
            pzem_data['windspeed'] = round(windSpeed, 2)

            print(f"\n[{time.strftime('%H:%M:%S')}]")
            for k, v in pzem_data.items():
                topic = f"{MQTT_TOPIC_BASE}/{k}"
                client.publish(topic, v, qos=1)
                print(f"{k}: {v}")

        time.sleep(max(0, INTERVAL_DETIK - (time.time() - start)))

except KeyboardInterrupt:
    print("\n⛔ Program dihentikan")

finally:
    GPIO.cleanup()
    client.loop_stop()
    client.disconnect()
    instrument.serial.close()
    print("✅ Cleanup selesai")
