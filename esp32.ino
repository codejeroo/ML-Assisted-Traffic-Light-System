#include <Arduino.h>

// --- 1. Pin Assignments ---
#define S1_GREEN 13
#define S1_RED   12

#define S2_GREEN 14
#define S2_RED   27

#define S3_GREEN 26
#define S3_RED   25

#define S4_GREEN 33
#define S4_RED   32

// --- 2. Traffic Light State Tracking (No timing, Python handles all durations) ---

// --- 3. Serial Configuration ---
const int BAUD_RATE = 115200;

// --- 4. Function to Control All Pins Off ---
void allLightsOff() {
  digitalWrite(S1_GREEN, LOW); digitalWrite(S1_RED, LOW);
  digitalWrite(S2_GREEN, LOW); digitalWrite(S2_RED, LOW);
  digitalWrite(S3_GREEN, LOW); digitalWrite(S3_RED, LOW);
  digitalWrite(S4_GREEN, LOW); digitalWrite(S4_RED, LOW);
}

// --- 5. Serial Command Handler ---
void handleSerialCommand(String command) {
  // Format: "S1:GREEN" or "S1:S4:GREEN" for paired commands
  // Parse the command
  
  int colonCount = 0;
  int colonPos[2] = {-1, -1};
  
  // Find colons to parse command
  for (int i = 0; i < command.length() && colonCount < 2; i++) {
    if (command[i] == ':') {
      colonPos[colonCount] = i;
      colonCount++;
    }
  }
  
  if (colonCount < 1) {
    Serial.println("ERROR: Invalid command format");
    return;
  }
  
  // Extract color (last part after last colon)
  String color = command.substring(colonPos[colonCount-1] + 1);
  color.trim();
  
  // Paired command: "S1:S4:GREEN"
  if (colonCount == 2) {
    String lane1 = command.substring(0, colonPos[0]);
    String lane2 = command.substring(colonPos[0] + 1, colonPos[1]);
    lane1.trim();
    lane2.trim();
    
    if (color == "GREEN") {
      // Set GREEN pins HIGH for the lanes
      int pin1 = (lane1 == "S1") ? S1_GREEN : (lane1 == "S2") ? S2_GREEN : (lane1 == "S3") ? S3_GREEN : S4_GREEN;
      int pin2 = (lane2 == "S1") ? S1_GREEN : (lane2 == "S2") ? S2_GREEN : (lane2 == "S3") ? S3_GREEN : S4_GREEN;
      digitalWrite(pin1, HIGH);
      digitalWrite(pin2, HIGH);
      
      // Turn off RED pins for these lanes
      if (lane1 == "S1" || lane2 == "S1") digitalWrite(S1_RED, LOW);
      if (lane1 == "S2" || lane2 == "S2") digitalWrite(S2_RED, LOW);
      if (lane1 == "S3" || lane2 == "S3") digitalWrite(S3_RED, LOW);
      if (lane1 == "S4" || lane2 == "S4") digitalWrite(S4_RED, LOW);
      
      // For opposite direction pair, turn on their RED and off GREEN
      if ((lane1 == "S1" && lane2 == "S4") || (lane1 == "S4" && lane2 == "S1")) {
        // S1/S4 are GREEN, so S2/S3 must be RED
        digitalWrite(S2_GREEN, LOW);
        digitalWrite(S3_GREEN, LOW);
        digitalWrite(S2_RED, HIGH);
        digitalWrite(S3_RED, HIGH);
      } else if ((lane1 == "S2" && lane2 == "S3") || (lane1 == "S3" && lane2 == "S2")) {
        // S2/S3 are GREEN, so S1/S4 must be RED
        digitalWrite(S1_GREEN, LOW);
        digitalWrite(S4_GREEN, LOW);
        digitalWrite(S1_RED, HIGH);
        digitalWrite(S4_RED, HIGH);
      }
      
      Serial.printf("OK: %s & %s GREEN\n", lane1.c_str(), lane2.c_str());
    } else if (color == "RED") {
      // Set RED pins HIGH for the lanes
      int pin1 = (lane1 == "S1") ? S1_RED : (lane1 == "S2") ? S2_RED : (lane1 == "S3") ? S3_RED : S4_RED;
      int pin2 = (lane2 == "S1") ? S1_RED : (lane2 == "S2") ? S2_RED : (lane2 == "S3") ? S3_RED : S4_RED;
      digitalWrite(pin1, HIGH);
      digitalWrite(pin2, HIGH);
      
      // Turn off GREEN pins for these lanes
      if (lane1 == "S1" || lane2 == "S1") digitalWrite(S1_GREEN, LOW);
      if (lane1 == "S2" || lane2 == "S2") digitalWrite(S2_GREEN, LOW);
      if (lane1 == "S3" || lane2 == "S3") digitalWrite(S3_GREEN, LOW);
      if (lane1 == "S4" || lane2 == "S4") digitalWrite(S4_GREEN, LOW);
      
      Serial.printf("OK: %s & %s RED\n", lane1.c_str(), lane2.c_str());
    }
  }
  // Single command: "S1:GREEN"
  else if (colonCount == 1) {
    String lane = command.substring(0, colonPos[0]);
    lane.trim();
    
    if (color == "GREEN") {
      if (lane == "S1") {
        digitalWrite(S1_GREEN, HIGH);
        digitalWrite(S1_RED, LOW);
      } else if (lane == "S2") {
        digitalWrite(S2_GREEN, HIGH);
        digitalWrite(S2_RED, LOW);
      } else if (lane == "S3") {
        digitalWrite(S3_GREEN, HIGH);
        digitalWrite(S3_RED, LOW);
      } else if (lane == "S4") {
        digitalWrite(S4_GREEN, HIGH);
        digitalWrite(S4_RED, LOW);
      }
      Serial.printf("OK: %s GREEN\n", lane.c_str());
    } else if (color == "RED") {
      if (lane == "S1") {
        digitalWrite(S1_RED, HIGH);
        digitalWrite(S1_GREEN, LOW);
      } else if (lane == "S2") {
        digitalWrite(S2_RED, HIGH);
        digitalWrite(S2_GREEN, LOW);
      } else if (lane == "S3") {
        digitalWrite(S3_RED, HIGH);
        digitalWrite(S3_GREEN, LOW);
      } else if (lane == "S4") {
        digitalWrite(S4_RED, HIGH);
        digitalWrite(S4_GREEN, LOW);
      }
      Serial.printf("OK: %s RED\n", lane.c_str());
    }
  }
}
  

// --- 6. Setup Function ---
void setup() {
  // Initialize serial communication at 115200 baud
  Serial.begin(115200);
  delay(1000); // Wait for serial to stabilize
  
  Serial.println("\n\n=== ESP32 Traffic Light Controller (Serial Mode) ===");
  Serial.println("Waiting for commands via serial at 115200 baud");
  Serial.println("Command format: \"S1:GREEN\" or \"S1:S4:GREEN\"");

  // Initialize all defined pins as OUTPUT
  pinMode(S1_GREEN, OUTPUT); pinMode(S1_RED, OUTPUT);
  pinMode(S2_GREEN, OUTPUT); pinMode(S2_RED, OUTPUT);
  pinMode(S3_GREEN, OUTPUT); pinMode(S3_RED, OUTPUT);
  pinMode(S4_GREEN, OUTPUT); pinMode(S4_RED, OUTPUT);

  // Start with all lights off
  allLightsOff();
  Serial.println("All pins initialized and set to OFF");
}

// --- 7. Loop Function ---
void loop() {
  // Read incoming serial data
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim(); // Remove any whitespace
    
    if (command.length() > 0) {
      Serial.printf("< Received: %s\n", command.c_str());
      handleSerialCommand(command);
    }
  }
  
  // Python script handles all timing logic - no auto-timeout needed
  delay(10); // Small delay to prevent CPU thrashing
}