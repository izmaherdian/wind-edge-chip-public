// =======================================
// ANEMOMETER OPTIK CELAH - ARDUINO
// FINAL VERSION
// =======================================

#define windPin 2   // Pin interrupt Arduino

// ---------- KONSTANTA ----------
const float pi = 3.14159265;
const int jml_celah = 18;     //
const float radius = 0.08;

const unsigned long sampleInterval = 1000; // 1 detik

float calibrationFactor = 2.3;   // contoh: 1/10

// ---------- VARIABEL ----------
volatile unsigned long pulseCount = 0;
volatile unsigned long lastMicros = 0;

unsigned long lastSampleTime = 0;
float windSpeed = 0;

// ---------- INTERRUPT ----------
void addcount() {
  unsigned long now = micros();

  // debounce 2 ms (aman untuk sistem mekanik)
  if (now - lastMicros >= 2000) {
    pulseCount++;
    lastMicros = now;
  }
}

// ---------- SETUP ----------
void setup() {
  pinMode(windPin, INPUT_PULLUP);
  Serial.begin(115200);

  attachInterrupt(digitalPinToInterrupt(windPin), addcount, FALLING);

  Serial.println("ANEMOMETER ARDUINO - FINAL");
  Serial.println("Pulsa -> RPM -> Wind Speed");
  Serial.println("--------------------------------");
}

// ---------- LOOP ----------
void loop() {
  unsigned long now = millis();

  if (now - lastSampleTime >= sampleInterval) {
    lastSampleTime = now;

    unsigned long pulses;
    noInterrupts();
    pulses = pulseCount;
    pulseCount = 0;
    interrupts();

    calculateWindSpeed(pulses);

    Serial.print("Pulsa: ");
    Serial.print(pulses);
    Serial.print(" | Wind Speed: ");
    Serial.print(windSpeed, 2);
    Serial.println(" m/s");
  }
}

// ---------- PERHITUNGAN ----------
void calculateWindSpeed(unsigned long pulses) {

  if (pulses == 0) {
    windSpeed = 0;
    return;
  }

  // Pulsa -> RPM
  float revolutions = (float)pulses / jml_celah;
  float RPM = revolutions * (60.0 / (sampleInterval / 1000.0));

  // RPM -> kecepatan angin teoritis (m/s)
  float speed_raw = 2 * pi * radius * RPM / 60.0;

  // Kalibrasi
  windSpeed = speed_raw * calibrationFactor;
}
