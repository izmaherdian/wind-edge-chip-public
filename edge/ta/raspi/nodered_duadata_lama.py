import os
import paho.mqtt.client as mqtt
import time
import serial
import minimalmodbus

# =========================
# ⚙️ KONFIGURASI UTAMA
# =========================
INTERVAL_DETIK = 3  

# --- Konfigurasi Modbus PZEM ---
DEVICE_ADDRESS = 0x01
BAUD_RATE = 9600
TIMEOUT = 1
PORT_PZEM = '/dev/ttyUSB0' # Port untuk PZEM

# --- Konfigurasi Modbus PZEM ---
DEVICE_ADDRESS = 0x01
BAUD_RATE = 9600
TIMEOUT = 1
PORT_PZEM = '/dev/ttyUSB0' # Port untuk Weather Station

# --- Konfigurasi Serial Arduino (Anemometer) ---
PORT_ARDUINO = '/dev/ttyACM0' # Port untuk Arduino
BAUD_ARDUINO = 9600

# --- Konfigurasi MQTT ---
MQTT_BROKER = "citaitb.com" 
MQTT_PORT = 1883            
MQTT_TOPIC_BASE = "TurbinAngin"
CLIENT_ID = "RaspberryPi4_Publisher_All"
MQTT_USER = "cita"
MQTT_PASS = os.environ.get("MQTT_PASS", "")

# =========================
# 📶 INISIALISASI MQTT
# =========================
def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("✅ Terhubung ke broker MQTT!")
    else:
        print(f"❌ Gagal terhubung, kode: {reason_code}")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, CLIENT_ID)
client.on_connect = on_connect
client.username_pw_set(username=MQTT_USER, password=MQTT_PASS)

try:
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()
except Exception as e:
    print(f"❌ Error saat mencoba koneksi MQTT: {e}")
    exit()

# =========================
# 🔌 INISIALISASI SENSOR
# =========================
# 1. Modbus (PZEM)
try:
    instrument = minimalmodbus.Instrument(PORT_PZEM, DEVICE_ADDRESS)
    instrument.serial.baudrate = BAUD_RATE
    instrument.serial.bytesize = 8
    instrument.serial.parity = serial.PARITY_NONE
    instrument.serial.stopbits = 2 
    instrument.serial.timeout = TIMEOUT
    instrument.mode = minimalmodbus.MODE_RTU
    print(f"✅ Modbus PZEM siap di {PORT_PZEM}")
except Exception as e:
    print(f"❌ Gagal inisialisasi PZEM di {PORT_PZEM}: {e}")
    instrument = None

# 2. Serial (Arduino Windspeed)
try:
    arduino_serial = serial.Serial(PORT_ARDUINO, BAUD_ARDUINO, timeout=0.5)
    print(f"✅ Arduino Windspeed siap di {PORT_ARDUINO}")
except Exception as e:
    print(f"⚠️ Gagal inisialisasi Arduino di {PORT_ARDUINO}: {e}")
    arduino_serial = None

# =========================
# 📊 FUNGSI BACA DATA
# =========================
def read_pzem_data():
    if instrument is None:
        return None
    data = {}
    try:
        data['voltage'] = instrument.read_register(0x0000, number_of_decimals=2, functioncode=4)
        data['current'] = instrument.read_register(0x0001, number_of_decimals=2, functioncode=4)
        power_low  = instrument.read_register(0x0002, functioncode=4)
        power_high = instrument.read_register(0x0003, functioncode=4)
        raw_power = (power_high << 16) | power_low
        data['power'] = round(raw_power * 0.1, 1)
        energy_low  = instrument.read_register(0x0004, functioncode=4)
        energy_high = instrument.read_register(0x0005, functioncode=4)
        data['energy'] = (energy_high << 16) | energy_low 
        return data
    except Exception:
        return None

def read_wind_speed():
    if arduino_serial and arduino_serial.in_waiting > 0:
        try:
            lines = arduino_serial.readlines()
            if lines:
                last_line = lines[-1].decode('utf-8').strip()
                return float(last_line)
        except Exception:
            pass
    return None

# =========================
# 📤 MAIN LOOP
# =========================
print(f"\n🚀 Mulai mengirim data PZEM & Windspeed setiap {INTERVAL_DETIK} detik...")
print("Tekan Ctrl+C untuk berhenti\n")

try:
    while True:
        print(f"\n--- Waktu: {time.strftime('%H:%M:%S')} ---")
        
        # Baca sensor
        pzem_data = read_pzem_data()
        wind_speed = read_wind_speed()

        # Kirim PZEM
        if pzem_data:
            for key, value in pzem_data.items():
                topic = f"{MQTT_TOPIC_BASE}/{key}"
                client.publish(topic, str(value), qos=1)
                print(f"-> PZEM  : {topic} = {value}")
        else:
            print("⚠️ PZEM tidak merespons.")
                
        # Kirim Arduino
        if wind_speed is not None:
            topic_wind = f"{MQTT_TOPIC_BASE}/Windspeed"
            client.publish(topic_wind, str(wind_speed), qos=1)
            print(f"-> Angin : {topic_wind} = {wind_speed}")
        else:
            print("⚠️ Data angin belum masuk/terbaca.")
        
        time.sleep(INTERVAL_DETIK)

except KeyboardInterrupt:
    print("\n✅ Program dihentikan user.")
finally:
    client.loop_stop()
    client.disconnect()
    if 'instrument' in locals() and instrument:
        instrument.serial.close()
    if 'arduino_serial' in locals() and arduino_serial:
        arduino_serial.close()
    print("Cleanup selesai.")
