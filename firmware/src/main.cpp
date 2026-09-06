#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

#include "secrets.h"

void connectWifi() {
  Serial.print("Connecting to WiFi");

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;

  while (WiFi.status() != WL_CONNECTED && attempts < 40) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("WiFi connected");
    Serial.print("ESP32 IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("WiFi connection failed");
  }
}

void fetchBoard() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi not connected");
    return;
  }

  HTTPClient http;

  Serial.print("Fetching: ");
  Serial.println(BOARD_URL);

  http.begin(BOARD_URL);
  int httpCode = http.GET();

  Serial.print("HTTP code: ");
  Serial.println(httpCode);

  if (httpCode != 200) {
    Serial.println("HTTP request failed");
    http.end();
    return;
  }

  String payload = http.getString();

  Serial.print("Payload size: ");
  Serial.println(payload.length());

  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, payload);

  if (error) {
    Serial.print("JSON parse failed: ");
    Serial.println(error.c_str());
    http.end();
    return;
  }

  const char* station = doc["station"] | "";
  const char* updated = doc["updated"] | "";

  Serial.println();
  Serial.println("==============================");
  Serial.print("Station: ");
  Serial.println(station);
  Serial.print("Updated: ");
  Serial.println(updated);

  Serial.println();
  Serial.println("To Barcelona:");
  JsonArray toBcn = doc["to_bcn"];

  for (JsonArray row : toBcn) {
    const char* time = row[0] | "";
    const char* dest = row[1] | "";
    const char* platform = row[2] | "";
    const char* leave = row[3] | "";
    const char* pos = row[4] | "";

    Serial.print("  ");
    Serial.print(time);
    Serial.print(" | ");
    Serial.print(dest);
    Serial.print(" | ");
    Serial.print(platform);
    Serial.print(" | ");
    Serial.print(leave);
    Serial.print(" | ");
    Serial.println(pos);
  }

  Serial.println();
  Serial.println("To South:");
  JsonArray toSouth = doc["to_south"];

  for (JsonArray row : toSouth) {
    const char* time = row[0] | "";
    const char* dest = row[1] | "";
    const char* platform = row[2] | "";
    const char* leave = row[3] | "";
    const char* pos = row[4] | "";

    Serial.print("  ");
    Serial.print(time);
    Serial.print(" | ");
    Serial.print(dest);
    Serial.print(" | ");
    Serial.print(platform);
    Serial.print(" | ");
    Serial.print(leave);
    Serial.print(" | ");
    Serial.println(pos);
  }

  Serial.println();
  Serial.println("Trains on line:");
  JsonArray trains = doc["trains"];

  for (JsonArray train : trains) {
    float lineIndex = train[0] | -1.0;
    const char* direction = train[1] | "?";

    Serial.print("  ");
    Serial.print(direction);
    Serial.print(" at ");
    Serial.println(lineIndex);
  }

  Serial.println("==============================");
  Serial.println();

  http.end();
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("Sitges Rodalies ESP32 test");

  connectWifi();
  fetchBoard();
}

void loop() {
  delay(60000);
  fetchBoard();
}