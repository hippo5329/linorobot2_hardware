// Copyright (c) 2026 Thomas Chou, Paul Bouchier, Linorobot contributors
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
#ifndef PICOW_CONFIG_H
#define PICOW_CONFIG_H

#define LINO_BASE DIFFERENTIAL_DRIVE
#define LED_PIN LED_BUILTIN //used for debugging status

// Physical Geometry
#define WHEEL_DIAMETER 0.0800 // meters
#define LR_WHEELS_DISTANCE 0.2200 // meters
#define ROBOT_WEIGHT 3.50 // kg

// Motor Driver & Characteristics
#define USE_GENERIC_2_IN_MOTOR_DRIVER
#define MOTOR_MAX_RPM 330
#define MAX_RPM_RATIO 0.85
#define MOTOR_OPERATING_VOLTAGE 12.0
#define MOTOR_POWER_MAX_VOLTAGE 12.0
#define MOTOR_POWER_MEASURED_VOLTAGE 12.0
#define MOTOR_RATED_TORQUE 1.50 // kg*cm
#define MOTOR_RATED_VOLTAGE 12.0 // V

#define PWM_BITS 10
#define PWM_FREQUENCY 20000
#define PWM_MAX (1 << PWM_BITS) - 1
#define PWM_MIN -PWM_MAX

#define COUNTS_PER_REV1 1320
#define COUNTS_PER_REV2 1320
#define COUNTS_PER_REV3 1320
#define COUNTS_PER_REV4 1320

#define MOTOR1_INV false
#define MOTOR2_INV true
#define MOTOR3_INV false
#define MOTOR4_INV true
#define MOTOR1_ENCODER_INV false
#define MOTOR2_ENCODER_INV false
#define MOTOR3_ENCODER_INV false
#define MOTOR4_ENCODER_INV false

// PID Constants
#define K_P 0.6
#define K_I 0.8
#define K_D 0.5

// Pin Assignments
#define MOTOR1_PWM 14
#define MOTOR1_IN_A 15
#define MOTOR1_IN_B 13
#define MOTOR2_PWM 16
#define MOTOR2_IN_A 17
#define MOTOR2_IN_B 12
#define MOTOR3_PWM -1
#define MOTOR3_IN_A -1
#define MOTOR3_IN_B -1
#define MOTOR4_PWM -1
#define MOTOR4_IN_A -1
#define MOTOR4_IN_B -1

#define MOTOR1_ENCODER_A 2
#define MOTOR1_ENCODER_B 3
#define MOTOR2_ENCODER_A 4
#define MOTOR2_ENCODER_B 5
#define MOTOR3_ENCODER_A -1
#define MOTOR3_ENCODER_B -1
#define MOTOR4_ENCODER_A -1
#define MOTOR4_ENCODER_B -1

// Sensors
#define USE_BNO085_IMU
#define USE_FAKE_MAG
#define USE_BATTERY_MONITOR
#define BATTERY_PIN 26
#define BATTERY_R1 30000.0
#define BATTERY_R2 7500.0
#define BATTERY_ADJUST(v) (v * (3.3 / 4095.0) * ((30000.0 + 7500.0) / 7500.0))
#define BATTERY_CAP 2.20
#define BATTERY_MIN 9.00
#define BATTERY_MAX 12.60
#define BATTERY_NOMINAL 11.10
#define BATTERY_DIP 0.98

#define USE_SONAR
#define TRIG_PIN 18
#define ECHO_PIN 19

// WiFi & Network Telemetry (OTA + Syslog over background WiFi while micro-ROS runs on USB Serial)
#define USE_WIFI
#define WIFI_AP_LIST { { "YOUR_WIFI_SSID", "YOUR_WIFI_PASSWORD" }, { NULL, NULL } }
#define USE_ARDUINO_OTA
#define USE_SYSLOG
#define SYSLOG_SERVER "192.168.1.100"
#define SYSLOG_PORT 514
#define DEVICE_HOSTNAME "picow"
#define APP_NAME "hardware"

#endif
