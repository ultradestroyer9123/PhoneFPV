// ===================== RC RECEIVER PINS =====================
const int THROTTLE_PIN = 4; // Forward / Backward
const int STEER_PIN    = 2; // Left / Right Turning

// ===================== BTS7960 #1 (LEFT DRIVER) =====================
// Ordered exactly by your physical sequence:
// VCC, GND, R_IS, R_EN, RPWM, L_IS, L_EN, LPWM
const int L_R_IS = A0;
const int L_REN  = 7;
const int L_RPWM = 5;
const int L_L_IS = A1;
const int L_LEN  = 8;
const int L_LPWM = 6;

// ===================== BTS7960 #2 (RIGHT DRIVER) =====================
// Ordered exactly by your physical sequence:
// VCC, GND, R_IS, R_EN, RPWM, L_IS, L_EN, LPWM
const int R_R_IS = A2;
const int R_REN  = 10;
const int R_RPWM = 3;
const int R_L_IS = A3;
const int R_LEN  = 12;
const int R_LPWM = 11;

// ===================== KEEP BATTERY AWAKE (VEX V5 "SMART" BATTERIES) =====================

const int WAKE_PIN = A4;
const unsigned long WAKE_PULSE_PERIOD = 2000; // ms
const unsigned long WAKE_PULSE_LENGTH = 100;  // ms

unsigned long lastWakePulse = 0;

// ===================== CALIBRATION & VALUES =====================
int LOWEST_VALUE  = 1000;
int HIGHEST_VALUE = 2000;
int CENTER_VALUE  = 1500;

// Reads raw microsecond pulses from RC receiver
int readChannel(int pin) {

  int value = pulseIn(pin, HIGH, 25000);

  // If signal disappears, return center value
  if (value == 0) return CENTER_VALUE;

  return value;
}

// Maps raw RC values to a clean -100 to 100 range
int mapRC(int value) {

  int output;

  if (value >= CENTER_VALUE) {
    output = map(value, CENTER_VALUE, HIGHEST_VALUE, 0, 100);
  } else {
    output = map(value, LOWEST_VALUE, CENTER_VALUE, -100, 0);
  }

  // Clamp protection
  if (output > 100) output = 100;
  if (output < -100) output = -100;

  // Deadband to stop twitching
  if (abs(output) < 15) output = 0;

  return output;
}

void setup() {

  // Battery Wake Logic
  pinMode(WAKE_PIN, INPUT);

  // Receiver Inputs
  pinMode(THROTTLE_PIN, INPUT);
  pinMode(STEER_PIN, INPUT);

  // Left Driver Pins
  pinMode(L_RPWM, OUTPUT);
  pinMode(L_LPWM, OUTPUT);
  pinMode(L_REN, OUTPUT);
  pinMode(L_LEN, OUTPUT);

  pinMode(L_R_IS, INPUT);
  pinMode(L_L_IS, INPUT);

  // Right Driver Pins
  pinMode(R_RPWM, OUTPUT);
  pinMode(R_LPWM, OUTPUT);
  pinMode(R_REN, OUTPUT);
  pinMode(R_LEN, OUTPUT);

  pinMode(R_R_IS, INPUT);
  pinMode(R_L_IS, INPUT);

  // Start disabled
  digitalWrite(L_REN, LOW);
  digitalWrite(L_LEN, LOW);

  digitalWrite(R_REN, LOW);
  digitalWrite(R_LEN, LOW);

  Serial.begin(9600);
}

void loop() {
  // ===================== KEEP BATTERY AWAKE =====================
  if (millis() - lastWakePulse >= WAKE_PULSE_PERIOD) {

    // Pull WAKE toward ground through the 10k resistor
    pinMode(WAKE_PIN, OUTPUT);
    digitalWrite(WAKE_PIN, LOW);

    delay(WAKE_PULSE_LENGTH);

    // Release WAKE
    pinMode(WAKE_PIN, INPUT);

    lastWakePulse = millis();
  }

  // ===================== READ CONTROLLER =====================
  int throttleRaw = readChannel(THROTTLE_PIN);
  int steerRaw    = readChannel(STEER_PIN);

  // Convert to -100 to 100
  int throttle = mapRC(throttleRaw);
  int steer    = mapRC(steerRaw);

  // ===================== TRUE TANK MIXING =====================
  int leftSpeed  = throttle + steer;
  int rightSpeed = throttle - steer;

  // ===================== MOTOR OUTPUT =====================
  setTrackSpeed(leftSpeed, rightSpeed);

  // ===================== SERIAL DEBUG =====================
  Serial.print("THR: ");
  Serial.print(throttle);

  Serial.print(" | STR: ");
  Serial.print(steer);

  Serial.print(" -> LEFT: ");
  Serial.print(leftSpeed);

  Serial.print(" | RIGHT: ");
  Serial.println(rightSpeed);
}

void setTrackSpeed(int leftSpeed, int rightSpeed) {

  // Clamp values
  leftSpeed  = constrain(leftSpeed, -100, 100);
  rightSpeed = constrain(rightSpeed, -100, 100);

  // Convert to PWM
  int leftPWM  = map(leftSpeed,  -100, 100, -255, 255);
  int rightPWM = map(rightSpeed, -100, 100, -255, 255);

  // =========================================================
  // LEFT TRACK
  // =========================================================

  if (leftPWM > 0) {

    // Enable driver
    digitalWrite(L_REN, HIGH);
    digitalWrite(L_LEN, HIGH);

    // Forward
    analogWrite(L_RPWM, leftPWM);
    analogWrite(L_LPWM, 0);

  }
  else if (leftPWM < 0) {

    // Enable driver
    digitalWrite(L_REN, HIGH);
    digitalWrite(L_LEN, HIGH);

    // Reverse
    analogWrite(L_RPWM, 0);
    analogWrite(L_LPWM, -leftPWM);

  }
  else {

    // Stop PWM
    analogWrite(L_RPWM, 0);
    analogWrite(L_LPWM, 0);

    // Disable driver in deadband
    digitalWrite(L_REN, LOW);
    digitalWrite(L_LEN, LOW);
  }

  // =========================================================
  // RIGHT TRACK
  // =========================================================

  if (rightPWM > 0) {

    // Enable driver
    digitalWrite(R_REN, HIGH);
    digitalWrite(R_LEN, HIGH);

    // Forward
    analogWrite(R_RPWM, rightPWM);
    analogWrite(R_LPWM, 0);

  }
  else if (rightPWM < 0) {

    // Enable driver
    digitalWrite(R_REN, HIGH);
    digitalWrite(R_LEN, HIGH);

    // Reverse
    analogWrite(R_RPWM, 0);
    analogWrite(R_LPWM, -rightPWM);

  }
  else {

    // Stop PWM
    analogWrite(R_RPWM, 0);
    analogWrite(R_LPWM, 0);

    // Disable driver in deadband
    digitalWrite(R_REN, LOW);
    digitalWrite(R_LEN, LOW);
  }
}