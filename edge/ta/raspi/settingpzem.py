import minimalmodbus
import serial
import time

# =========================
# DEVICE CONFIGURATION
# =========================
SLAVE_ADDRESS = 0x01
DEVICE_PORT = '/dev/ttyUSB0'   # GANTI JIKA BERBEDA
DEVICE_BAUDRATE = 9600
DEVICE_PARITY = serial.PARITY_NONE
DEVICE_STOPBITS = 1

# =========================
# MODBUS CONNECTION
# =========================
def connect_modbus_device():
    instrument = minimalmodbus.Instrument(DEVICE_PORT, SLAVE_ADDRESS)
    instrument.serial.baudrate = DEVICE_BAUDRATE
    instrument.serial.bytesize = 8
    instrument.serial.parity = DEVICE_PARITY
    instrument.serial.stopbits = DEVICE_STOPBITS
    instrument.serial.timeout = 1
    instrument.mode = minimalmodbus.MODE_RTU
    return instrument

# =========================
# READ CURRENT SETTINGS
# =========================
def read_current_values(instrument):
    high_voltage_alarm = instrument.read_register(0x0000, functioncode=3) / 100.0
    low_voltage_alarm  = instrument.read_register(0x0001, functioncode=3) / 100.0
    slave_address      = instrument.read_register(0x0002, functioncode=3)
    current_range      = instrument.read_register(0x0003, functioncode=3)
    return high_voltage_alarm, low_voltage_alarm, slave_address, current_range

# =========================
# CURRENT RANGE MAPPING
# =========================
CURRENT_RANGE_MAPPING = {
    0: "100 A",   # ✅ SHUNT KAMU
    1: "50 A",
    2: "200 A",
    3: "300 A",
}

# =========================
# DISPLAY MENU
# =========================
def display_menu(current_values):
    range_text = CURRENT_RANGE_MAPPING.get(current_values[3], "UNKNOWN")

    print("\n=========== MODBUS CONFIG MENU ===========")
    print(f"1. Set High Voltage Alarm  (Current: {current_values[0]} V)")
    print(f"2. Set Low Voltage Alarm   (Current: {current_values[1]} V)")
    print(f"3. Set Slave Address      (Current: {current_values[2]})")
    print(f"4. Lock Current Range     (Current: {range_text}) [SHUNT 100A]")
    print("5. Reset Energy")
    print("6. Exit")
    print("==========================================")

# =========================
# SAFE INPUT FUNCTIONS
# =========================
def set_high_voltage_alarm_threshold(instrument):
    try:
        value = int(input("Enter High Voltage Alarm (5–350 V): "))
        if 5 <= value <= 350:
            instrument.write_register(0x0000, value * 100, functioncode=6)
            print("✅ High Voltage Alarm Updated")
        else:
            print("❌ Value out of range!")
    except ValueError:
        print("❌ Invalid input!")

def set_low_voltage_alarm_threshold(instrument):
    try:
        value = int(input("Enter Low Voltage Alarm (1–350 V): "))
        if 1 <= value <= 350:
            instrument.write_register(0x0001, value * 100, functioncode=6)
            print("✅ Low Voltage Alarm Updated")
        else:
            print("❌ Value out of range!")
    except ValueError:
        print("❌ Invalid input!")

def set_slave_address(instrument):
    try:
        value = int(input("Enter New Slave Address (1–247): "))
        if 1 <= value <= 247:
            instrument.write_register(0x0002, value, functioncode=6)
            instrument.serial.close()
            instrument.address = value
            instrument.serial.open()
            print("✅ Slave Address Updated")
        else:
            print("❌ Address out of range!")
    except ValueError:
        print("❌ Invalid input!")

# =========================
# LOCK CURRENT RANGE TO 100A
# =========================
def lock_current_range_100A(instrument):
    instrument.write_register(0x0003, 0, functioncode=6)
    print("✅ Current Range LOCKED to 100 A (Safe)")

# =========================
# RESET ENERGY (SAFE)
# =========================
def reset_energy(instrument):
    try:
        instrument.write_register(0x0004, 1, functioncode=6)  # SESUAI UMUM DATA LOGGER
        time.sleep(0.3)
        print("✅ Energy Reset Success")
    except:
        print("❌ Reset failed - check datasheet")

# =========================
# MAIN PROGRAM
# =========================
def main():
    instrument = connect_modbus_device()
    no_response_retries = 5

    while True:
        try:
            current_values = read_current_values(instrument)
            display_menu(current_values)

            choice = input("Enter your choice: ")

            if choice == "1":
                set_high_voltage_alarm_threshold(instrument)
            elif choice == "2":
                set_low_voltage_alarm_threshold(instrument)
            elif choice == "3":
                set_slave_address(instrument)
            elif choice == "4":
                lock_current_range_100A(instrument)
            elif choice == "5":
                reset_energy(instrument)
            elif choice == "6":
                print("Exiting program...")
                break
            else:
                print("❌ Invalid choice")

        except minimalmodbus.NoResponseError:
            no_response_retries -= 1
            print("⚠️ No response from device!")
            if no_response_retries == 0:
                print("❌ Device not responding. Exiting...")
                break

        except minimalmodbus.InvalidResponseError as e:
            print("❌ Invalid response:", e)

        except Exception as e:
            print("❌ Unexpected error:", e)

# =========================
# RUN PROGRAM
# =========================
if __name__ == "__main__":
    main()