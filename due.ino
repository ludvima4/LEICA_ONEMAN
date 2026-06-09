#include <Adafruit_BME280.h>
#include <Adafruit_Sensor.h>
#include <Wire.h>

// ==========================================
// --- KONFIGURACE ---
// ==========================================
#define SET_PIN 6
#define TARGET_BAUD 9600

Adafruit_BME280 bme;

String cmdBuf = "";

// HC_12 config
void configureHC12() {

  digitalWrite(SET_PIN, LOW);
  delay(200);

  Serial1.begin(9600);
  Serial1.setTimeout(200);
  while (Serial1.available())
    Serial1.read(); // clear buffer

  Serial.println("AT commands init");

  Serial1.print("AT+C001");
  delay(150);
  while (Serial1.available())
    Serial1.read();
  Serial1.print("AT+P8");
  delay(150);
  while (Serial1.available())
    Serial1.read();
  Serial1.print("AT+FU3");
  delay(150);
  while (Serial1.available())
    Serial1.read();
  Serial1.print("AT+B9600");
  delay(150);
  while (Serial1.available())
    Serial1.read();

  digitalWrite(SET_PIN, HIGH); // back to normal
  delay(300);

  Serial.println("config ok\n");

  Serial1.begin(TARGET_BAUD);
}

// setup
void setup() {
  Serial.begin(115200); // debug
  Serial2.begin(9600);  // RS232 -> ts

  pinMode(SET_PIN, OUTPUT);
  digitalWrite(SET_PIN, HIGH);

  cmdBuf.reserve(128);

  delay(1000);

  configureHC12();

  if (!bme.begin(0x76)) {
    Serial.println("BME280 error");
  } else {
    Serial.println("BME280 ok");
  }

  Serial.println("bridge ok\n");
}

// line handling
void handleLine(String line) {
  String key = line;
  key.trim();

  if (key == "PING") {
    // ping and pong
    Serial1.print("PONG\n");
    Serial.println("Odchyceno: odeslán PONG");

  } else if (key == "TEMP") {
    // atmos meassure
    float temperature = bme.readTemperature();
    float pressure = bme.readPressure(); // Pa

    Serial1.print("TEMP:");
    Serial1.print(temperature, 2);
    Serial1.print(",");
    Serial1.println(pressure, 2);

    Serial.print("Odchyceno: TEMP:");
    Serial.print(temperature, 2);
    Serial.print(",");
    Serial.println(pressure, 2);

  } else if (key.length() > 0) {
    Serial2.print(line);
    Serial2.print("\r\n");
    Serial.println("Přeposláno do RS232: '" + line + "'");
  }
}

// MAIN LOOP
void loop() {

  // DUE - PI
  while (Serial2.available() > 0) {
    Serial1.write(Serial2.read());
  }

  // PI - DUE
  while (Serial1.available() > 0) {
    char c = Serial1.read();

    if (c == '\n') {
      handleLine(cmdBuf);
      cmdBuf = "";
    } else if (c != '\r') {
      cmdBuf += c;
      if (cmdBuf.length() > 120)
        cmdBuf = ""; // overflow
    }

    while (Serial2.available() > 0) {
      Serial1.write(Serial2.read());
    }
  }
}
