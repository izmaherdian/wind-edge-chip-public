import os
import time
import serial
import minimalmodbus
import paho.mqtt.client as mqtt
import joblib
import numpy as np

# =========================
# ⚙️ KONFIGURASI UTAMA
# =========================
INTERVAL_DETIK = 3

# --- Konfigurasi Modbus PZEM ---
DEVICE_ADDRESS = 0x01
BAUD_RATE = 9600
TIMEOUT = 1
PORT_PZEM = '/dev/ttyUSB0'  # Port untuk PZEM

# --- Konfigurasi Modbus Weather Station ---
DEVICE_ADDRESS_STATION = 0x02
BAUD_RATE_STATION = 4800
TIMEOUT_STATION = 2
PORT_STATION = '/dev/ttyUSB1'  # Port untuk Weather Station

# --- Konfigurasi Serial Arduino (Anemometer) ---
PORT_ARDUINO = '/dev/ttyACM0'  # Port untuk Arduino
BAUD_ARDUINO = 9600

# --- Konfigurasi MQTT ---
MQTT_BROKER = "citaitb.com"
MQTT_PORT = 1883
MQTT_TOPIC_BASE = "TurbinAngin"
CLIENT_ID = "RaspberryPi4_Publisher_ML"
MQTT_USER = "cita"
MQTT_PASS = os.environ.get("MQTT_PASS", "")

# =========================
# 🤖 LOAD MACHINE LEARNING
# =========================
try:
    # Usulan 21 Okt 2026: SVM gaya TA dengan angin STASIUN (anemometer Arduino macet di 1,25 m/s).
    # Dilatih oleh ml/status/svm_angin_stasiun.py (scikit-learn 1.8.0). Model lama tetap ada sebagai cadangan.
    model = joblib.load("svm_angin_stasiun.pkl")
    print("✅ Model Machine Learning berhasil dimuat")

except Exception as e:
    print(f"❌ Gagal load model ML: {e}")
    model = None

# =========================
# 📶 INISIALISASI MQTT
# =========================
def on_connect(client, userdata, flags, reason_code, properties):

    if reason_code == 0:
        print("✅ Terhubung ke broker MQTT!")

    else:
        print(f"❌ Gagal terhubung, kode: {reason_code}")


client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    CLIENT_ID
)

client.on_connect = on_connect

client.username_pw_set(
    username=MQTT_USER,
    password=MQTT_PASS
)

try:
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()

except Exception as e:
    print(f"❌ Error saat mencoba koneksi MQTT: {e}")

# =========================
# 🔌 INISIALISASI SENSOR
# =========================

# 1. Modbus (PZEM)
try:

    instrument = minimalmodbus.Instrument(
        PORT_PZEM,
        DEVICE_ADDRESS
    )

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

    arduino_serial = serial.Serial(
        PORT_ARDUINO,
        BAUD_ARDUINO,
        timeout=0.5
    )

    print(f"✅ Arduino Windspeed siap di {PORT_ARDUINO}")

except Exception as e:

    print(f"⚠️ Gagal inisialisasi Arduino di {PORT_ARDUINO}: {e}")

    arduino_serial = None

# 3. Modbus (Weather Station)
try:

    instrument2 = minimalmodbus.Instrument(
        PORT_STATION,
        DEVICE_ADDRESS_STATION
    )

    instrument2.serial.baudrate = BAUD_RATE_STATION
    instrument2.serial.bytesize = 8
    instrument2.serial.parity = serial.PARITY_NONE
    instrument2.serial.stopbits = 1
    instrument2.serial.timeout = TIMEOUT_STATION
    instrument2.mode = minimalmodbus.MODE_RTU

    print(f"✅ Modbus Weather Station siap di {PORT_STATION}")

except Exception as e:

    print(f"❌ Gagal inisialisasi Weather Station di {PORT_STATION}: {e}")

    instrument2 = None

# =========================
# 📊 FUNGSI BACA DATA
# =========================

def read_pzem_data():

    if instrument is None:
        return None

    data = {}

    try:

        data['voltage'] = instrument.read_register(
            0x0000,
            number_of_decimals=2,
            functioncode=4
        )

        data['current'] = instrument.read_register(
            0x0001,
            number_of_decimals=2,
            functioncode=4
        )

        power_low = instrument.read_register(
            0x0002,
            functioncode=4
        )

        power_high = instrument.read_register(
            0x0003,
            functioncode=4
        )

        raw_power = (power_high << 16) | power_low

        data['power'] = round(raw_power * 0.1, 1)

        energy_low = instrument.read_register(
            0x0004,
            functioncode=4
        )

        energy_high = instrument.read_register(
            0x0005,
            functioncode=4
        )

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


def read_station_data():

    if instrument2 is None:
        return None

    data_station = {}

    try:

        raw_windspeed = instrument2.read_register(
            0x01F4,
            functioncode=3
        )

        raw_winddir = instrument2.read_register(
            0x01F7,
            functioncode=3
        )

        raw_humidity = instrument2.read_register(
            0x01F8,
            functioncode=3
        )

        raw_temp = instrument2.read_register(
            0x01F9,
            functioncode=3
        )

        raw_noise = instrument2.read_register(
            0x01FA,
            functioncode=3
        )

        raw_rainfall = instrument2.read_register(
            0x0201,
            functioncode=3
        )

        data_station['windspeedstation'] = round(
            raw_windspeed * 0.01,
            2
        )

        data_station['winddirdeg'] = round(
            raw_winddir - 115,
            2
        )

        data_station['humidity'] = round(
            (raw_humidity * 0.1 - 3.265) / 1.073,
            2
        )

        data_station['temperature'] = round(
            raw_temp * 0.1,
            2
        )

        data_station['noise'] = round(
            raw_noise * 0.1,
            2
        )

        data_station['rainfall'] = round(
            raw_rainfall * 0.1,
            2
        )

        return data_station

    except Exception:
        return None

# =========================
# 🤖 FUNGSI MACHINE LEARNING
# =========================

def predict_condition(voltage, current, windspeed):

    if model is None:
        return None

    try:

        # Feature HARUS sama dengan training
        features = np.array([
            [voltage, current, windspeed]
        ])

        prediction = model.predict(features)[0]

        return str(prediction)

    except Exception as e:

        print(f"❌ Error Machine Learning: {e}")

        return None

# =========================
# 📤 MAIN LOOP
# =========================

print(
    f"\n🚀 Mulai mengirim data PZEM & Windspeed setiap {INTERVAL_DETIK} detik"
)

print("Tekan Ctrl+C untuk berhenti\n")

try:

    while True:

        print(f"\n--- Waktu: {time.strftime('%H:%M:%S')} ---")

        # =========================
        # 📥 BACA SENSOR
        # =========================
        pzem_data = read_pzem_data()

        wind_speed = read_wind_speed()

        station_data = read_station_data()

        # =========================
        # 🤖 PREDIKSI MACHINE LEARNING
        # =========================
        ml_result = None

        # pakai angin stasiun (Modbus), bukan angin Arduino
        if pzem_data and station_data and station_data.get('windspeedstation') is not None:

            voltage = pzem_data['voltage']

            current = pzem_data['current']

            ml_result = predict_condition(
                voltage,
                current,
                station_data['windspeedstation']
            )

        # =========================
        # 📤 KIRIM DATA PZEM
        # =========================
        if pzem_data:

            for key, value in pzem_data.items():

                topic = f"{MQTT_TOPIC_BASE}/{key}"

                client.publish(
                    topic,
                    str(value),
                    qos=1
                )

                print(f"-> PZEM    : {topic} = {value}")

        else:
            print("⚠️ PZEM tidak merespons.")

        # =========================
        # 📤 KIRIM DATA ANGIN
        # =========================
        if wind_speed is not None:

            topic_wind = f"{MQTT_TOPIC_BASE}/Windspeed"

            client.publish(
                topic_wind,
                str(wind_speed),
                qos=1
            )

            print(f"-> Angin   : {topic_wind} = {wind_speed}")

        else:
            print("⚠️ Data angin belum masuk/terbaca.")

        # =========================
        # 📤 KIRIM WEATHER STATION
        # =========================
        if station_data:

            for key, value in station_data.items():

                topic = f"{MQTT_TOPIC_BASE}/{key}"

                client.publish(
                    topic,
                    str(value),
                    qos=1
                )

                print(f"-> Station : {topic} = {value}")

        else:
            print("⚠️ Weather Station tidak merespons.")

        # =========================
        # 📤 KIRIM HASIL ML
        # =========================
        if ml_result is not None:

            topic_ml = f"{MQTT_TOPIC_BASE}/ML_Status"

            client.publish(
                topic_ml,
                str(ml_result),
                qos=1
            )

            print(f"-> ML      : {topic_ml} = {ml_result}")

        else:
            print("⚠️ Prediksi ML gagal.")

        # Delay loop
        time.sleep(INTERVAL_DETIK)

except KeyboardInterrupt:

    print("\n✅ Program dihentikan user.")

finally:

    client.loop_stop()

    client.disconnect()

    if 'instrument' in locals() and instrument:
        instrument.serial.close()

    if 'instrument2' in locals() and instrument2:
        instrument2.serial.close()

    if 'arduino_serial' in locals() and arduino_serial:
        arduino_serial.close()

    print("Cleanup selesai.")
