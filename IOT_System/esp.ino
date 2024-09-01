#include <Wire.h>
#include <LiquidCrystal_PCF8574.h>
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <PubSubClient.h>

// Setting up the LCD address
LiquidCrystal_PCF8574 lcd(0x27);

// AP credentials
const char* ap_ssid = "NodeMCU_Config";
const char* ap_password = "password123";
bool apDisabled = false; // Used in order to disable the Access point when the IoT system is connected to the Wi-Fi 

// Default Wi-Fi credentials (can be modified during initial installation or left empty)
String wifi_ssid = "";
String wifi_password = "";

// We initilaize the the web server for the Access Point
ESP8266WebServer server(80);

// Pins for sensors
const int pirPin = 16; // PIR sensor
const int trigPin = 12; // Ultrasonic sensor TRIG
const int echoPin = 14; // Ultrasonic sensor ECHO

// Sensor readings variables
long motionDetected;
long duration;
float distance;

// MQTT setup
const char* mqtt_server = "broker.mqttdashboard.com";
const int mqtt_port = 1883;
const char* mqtt_user = "";
const char* mqtt_password = "";
const char * r_topic = "room1"; // the room id should be changed to match the specific room when configuring the system
const char * p_topic_0 = "room1/exhibit"; // the room id and the exhibit ids in the topic should be changed to match the room when configuring the system

WiFiClient espClient;
PubSubClient client(espClient);

void setup() {
  lcd.begin(16, 2);
  lcd.setBacklight(255);
  
  Serial.begin(115200);

  // We setup the AP
  WiFi.softAP(ap_ssid, ap_password);
  IPAddress IP = WiFi.softAPIP();

  // Initial attempt to connect to the network
  WiFi.begin(wifi_ssid.c_str(), wifi_password.c_str());

  // Display the waiting to connect message and IP address when the system is not connected to the Wi-Fi connection
  lcd.setCursor(0, 0);
  lcd.print("Waiting to connect");

  lcd.setCursor(0, 1);
  lcd.print(IP);

  Serial.print("AP IP address: ");
  Serial.println(IP);

  // We setup the Wi-Fi connection
  server.on("/", HTTP_GET, handleRoot);
  server.on("/set", HTTP_POST, handleSet);
  server.begin();

  // The sensors' pins are setup
  pinMode(trigPin, OUTPUT); // Sets the trigPin as an Output
  pinMode(echoPin, INPUT); // Sets the echoPin as an Input

  // We initialize the MQTT client
  client.setServer(mqtt_server, mqtt_port);
}

void loop() {
  server.handleClient();

  // Check Wi-Fi connection and reconnect if necessary
  if (WiFi.status() != WL_CONNECTED && apDisabled) {
    reconnectWiFi();
  }

  if (!client.connected()) {
    reconnectMQTT();
  }
  client.loop();
  
  // Check if connected to a Wi-Fi network
  if (WiFi.status() == WL_CONNECTED && !apDisabled) {
    // Clear the LCD
    lcd.clear();
    
    // Display the connected message
    lcd.setCursor(0, 0);
    lcd.print("Connected to WiFi");
    
    lcd.setCursor(0, 1);
    lcd.print("IP: ");
    lcd.print(WiFi.localIP());

    // Disable the AP after the system connects to the Wi-Fi network
    WiFi.softAPdisconnect(true);
    apDisabled = true;
  }

  if (WiFi.status() == WL_CONNECTED) {
    // Read PIR sensor
    motionDetected = digitalRead(pirPin);
    
    // Read Ultrasonic sensor for exhibit piece 0
    distance = getDistance();

    // Handle PIR sensor
    if (motionDetected == HIGH) {
      Serial.println("Motion detected!");
      client.publish(p_topic_0, "{\"id\": 1, \"detected\": 1}");
    }

    // Handle Ultrasonic sensor for exhibit piece 0
    if (distance < 250) { // Assuming threshold is 10 cm
      Serial.println("Someone in front of painting.");
      if (!client.publish(r_topic, "{\"r_id\": 1, \"id\": 0, \"detected\": 1}")) Serial.println("failed to publish !");
    } else if (distance < 1 and distance > 1000) {
      Serial.println("No one in front of painting.");
    }
    Serial.println(distance);

    // Add additional logic or delays here if needed
    delay(500); // Delay for stability
  }
}

// Function used to provide the user with the initial page to input a Wi-Fi network's credentials
void handleRoot() {
  String html = "<form action=\"/set\" method=\"post\">"
                "WiFi SSID: <input type=\"text\" name=\"ssid\"><br>"
                "WiFi Password: <input type=\"text\" name=\"password\"><br>"
                "<input type=\"submit\" value=\"Set\">"
                "</form>";
  server.send(200, "text/html", html);
}

// Function used to provide the user the page to handle the user's request to connect to a Wi-Fi network
void handleSet() {
  if (server.hasArg("ssid") && server.hasArg("password")) {
    wifi_ssid = server.arg("ssid");
    wifi_password = server.arg("password");

    Serial.println("Received credentials:");
    Serial.println("SSID: " + wifi_ssid);
    Serial.println("Password: " + wifi_password);

    WiFi.begin(wifi_ssid.c_str(), wifi_password.c_str());

    server.send(200, "text/html", "Connecting to WiFi... Please wait.");

  } else {
    server.send(400, "text/html", "Invalid Request");
  }
}

// Function to measure distance using Ultrasonic sensor
long getDistance() {
  // Clear the TRIG pin
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  
  // Set TRIG pin high for 10 microseconds
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  
  // Read the ECHO pin
  duration = pulseIn(echoPin, HIGH);
  
  // Calculate distance in cm
  return duration * 0.0344 / 2;
}


// Function used to reconnect to MQTT
void reconnectMQTT() {
  int attempts = 0;
  while (!client.connected() && attempts < 10) {
    Serial.print("Attempting MQTT connection...");

    if (client.connect()) {
      Serial.println("connected");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" try again in 5 seconds");
      
      attempts++;
      delay(5000);
    }
  }
}


// Function used to reconnect to the Wi-Fi
void reconnectWiFi() {
  Serial.print("Attempting to reconnect to WiFi...");
  WiFi.begin(wifi_ssid.c_str(), wifi_password.c_str());

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 10) {
    delay(5000);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("Reconnected to WiFi");
  } else {
    Serial.println("Failed to reconnect to WiFi");
  }
}
