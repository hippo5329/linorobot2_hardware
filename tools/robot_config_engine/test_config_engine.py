# Copyright (c) 2026 Thomas Chou, Paul Bouchier, Linorobot contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import unittest
import os
from validator import validate_robot_spec
from generator import generate_config_header
from parser import parse_header_to_spec, merge_configurations

class TestRobotConfigEngine(unittest.TestCase):
    def setUp(self):
        self.valid_pico_spec = {
            "robot_name": "scout_pico2",
            "kinematics": "DIFFERENTIAL_DRIVE",
            "mcu": "PICO2",
            "transport": "SERIAL",
            "geometry": {
                "wheel_diameter": 0.065,
                "track_width": 0.20,
                "weight": 3.5
            },
            "motors": {
                "driver_type": "GENERIC_2_IN",
                "max_rpm": 330,
                "cpr": 1320,
                "rated_torque": 1.5,
                "rated_voltage": 12.0
            },
            "sensors": {
                "imu": "MPU6050",
                "mag": "NONE",
                "battery_monitor": "ADC_DIVIDER",
                "battery_capacity": 2.2,
                "battery_nominal_voltage": 11.1,
                "battery_min_voltage": 9.0,
                "battery_max_voltage": 12.6,
                "sonar": True
            },
            "pins": {
                "led": 25,
                "motor1": { "pwm": 14, "in_a": 12, "in_b": 13 },
                "motor2": { "pwm": 15, "in_a": 10, "in_b": 11 },
                "encoders": { "m1_a": 2, "m1_b": 3, "m2_a": 4, "m2_b": 5 },
                "i2c": { "sda": 8, "scl": 9 },
                "battery_pin": 26,
                "sonar": { "trig": 16, "echo": 17 }
            }
        }

    def test_validation_success(self):
        valid, errors, stats = validate_robot_spec(self.valid_pico_spec)
        self.assertTrue(valid)
        self.assertEqual(len(errors), 0)
        self.assertAlmostEqual(stats["max_linear_speed_m_s"], 0.954, places=2)
        self.assertIn("max_accel_m_s2", stats)

    def test_pin_conflict_detection(self):
        bad_spec = dict(self.valid_pico_spec)
        bad_spec["pins"] = dict(self.valid_pico_spec["pins"])
        bad_spec["pins"]["motor1"] = { "pwm": 2, "in_a": 12, "in_b": 13 }
        valid, errors, stats = validate_robot_spec(bad_spec)
        self.assertFalse(valid)
        self.assertTrue(any("assigned to multiple functions" in str(e) for e in errors))

    def test_header_generation(self):
        header = generate_config_header(self.valid_pico_spec)
        self.assertIn("#define LINO_BASE DIFFERENTIAL_DRIVE", header)
        self.assertIn("#define USE_GENERIC_2_IN_MOTOR_DRIVER", header)
        self.assertIn("#define USE_MPU6050_IMU", header)
        self.assertIn("#define BATTERY_CAP 2.2", header)
        self.assertIn("#define BATTERY_MIN 9", header)
        self.assertIn("#define BATTERY_MAX 12.6", header)
        self.assertIn("#define ROBOT_WEIGHT 3.5", header)
        # Sonar enabled in the fixture (sensors.sonar=True, pins.sonar trig/echo)
        self.assertIn("#define USE_SONAR", header)
        self.assertIn("#define TRIG_PIN 16", header)
        self.assertIn("#define ECHO_PIN 17", header)

    def test_header_parsing_fake_sensors(self):
        # Sample C++ header with Fake IMU and Fake Mag
        raw_header = """
#ifndef TESTBOT_CONFIG_H
#define TESTBOT_CONFIG_H
#define LINO_BASE DIFFERENTIAL_DRIVE
#define WHEEL_DIAMETER 0.0650
#define LR_WHEELS_DISTANCE 0.2000
#define USE_BTS7960_MOTOR_DRIVER
#define MOTOR_MAX_RPM 300
#define COUNTS_PER_REV1 1320
#define USE_FAKE_IMU
#define USE_FAKE_MAG
#define BAUDRATE 921600
#endif
"""
        parsed = parse_header_to_spec(raw_header)
        self.assertEqual(parsed["robot_name"], "testbot")
        self.assertEqual(parsed["kinematics"], "DIFFERENTIAL_DRIVE")
        self.assertEqual(parsed["motors"]["driver_type"], "BTS7960")
        self.assertEqual(parsed["sensors"]["imu_type"], "USE_FAKE_IMU")
        self.assertEqual(parsed["sensors"]["mag_type"], "USE_FAKE_MAG")
        self.assertEqual(parsed["telemetry"]["baudrate"], 921600)

    def test_negative_led_pin_roundtrip(self):
        # LED_PIN -1 means "no addressable LED" (e.g. Waveshare GenDrv).
        # It must parse to int -1 and regenerate as "#define LED_PIN -1".
        parsed = parse_header_to_spec("#define LED_PIN -1\n")
        self.assertEqual(parsed["pins"]["led"], -1)
        header = generate_config_header(parsed)
        self.assertIn("#define LED_PIN -1", header)

    def test_bts7960_two_output_roundtrip(self):
        # BTS7960 drives exactly two pins: MOTORx_IN_A (RPWM) and MOTORx_IN_B
        # (LPWM). MOTORx_PWM is an unused placeholder and must be emitted as -1
        # with no BOARD_INIT enable-drive lines.
        spec = json.loads(json.dumps(self.valid_pico_spec))
        spec["motors"]["driver_type"] = "BTS7960"
        spec["pins"]["motor1"] = {"in_a": 12, "in_b": 13}
        spec["pins"]["motor2"] = {"in_a": 10, "in_b": 11}
        header = generate_config_header(spec)
        self.assertIn("#define MOTOR1_PWM -1", header)
        self.assertIn("#define MOTOR1_IN_A 12", header)
        self.assertIn("#define MOTOR1_IN_B 13", header)
        self.assertNotIn("pinMode(MOTOR1_PWM", header)

        parsed = parse_header_to_spec(header)
        self.assertEqual(parsed["motors"]["driver_type"], "BTS7960")
        self.assertEqual(parsed["pins"]["motor1"]["in_a"], 12)
        self.assertEqual(parsed["pins"]["motor1"]["in_b"], 13)

        ok, errors, _ = validate_robot_spec(spec)
        self.assertTrue(ok, errors)

        # A duplicate across the two real outputs is still a conflict.
        spec["pins"]["motor2"]["in_a"] = 12
        ok, errors, _ = validate_robot_spec(spec)
        self.assertFalse(ok)

    def test_negative_encoder_pins_valid(self):
        # Negative values stand for "no connection" and must not trigger
        # pin-conflict or out-of-range errors, even when repeated.
        neg = json.loads(json.dumps(self.valid_pico_spec))
        neg["pins"] = {
            "led": 25,
            "encoders": {
                "m1_a": -1, "m1_b": -1, "m2_a": -1, "m2_b": -1,
                "m3_a": -1, "m3_b": -1, "m4_a": -1, "m4_b": -1,
                "m1_inv": False, "m2_inv": False, "m3_inv": False, "m4_inv": False,
            },
            "motor1": {"pwm": 14, "in_a": 12, "in_b": 13},
            "motor2": {"pwm": 15, "in_a": 10, "in_b": 11},
            "motor3": {"pwm": -1, "in_a": -1, "in_b": -1},
            "motor4": {"pwm": -1, "in_a": -1, "in_b": -1},
            "i2c": {"sda": 4, "scl": 5},
        }
        ok, errors, _ = validate_robot_spec(neg)
        self.assertTrue(ok)
        self.assertEqual(errors, [])

        # But a genuine positive-pin duplicate must still be an error.
        neg["pins"]["motor2"]["in_a"] = 14  # duplicates motor1.in_a == 14
        ok, errors, _ = validate_robot_spec(neg)
        self.assertFalse(ok)
        self.assertTrue(any("assigned to multiple functions" in str(e) for e in errors))

    def test_bmp280_env_roundtrip(self):
        raw = """
#ifndef ENVBOT_CONFIG_H
#define ENVBOT_CONFIG_H
#define LINO_BASE DIFFERENTIAL_DRIVE
#define USE_BTS7960_MOTOR_DRIVER
#define USE_BMP280
#define BMP280_ADDR 0x76
#define ENV_COV { 1.0, 0.01, 0.0025 }
#define BAUDRATE 921600
#endif
"""
        spec = parse_header_to_spec(raw)
        self.assertTrue(spec["sensors"].get("use_bmp280"))
        self.assertEqual(spec["sensors"].get("env_type"), "BMP280")
        self.assertEqual(spec["sensors"].get("bmp280_addr"), "0x76")
        self.assertEqual(spec["imu_tuning"]["env_cov"], [1.0, 0.01, 0.0025])

        h = generate_config_header(spec)
        self.assertEqual(h.count("#define USE_BMP280"), 1)
        self.assertIn("#define BMP280_ADDR 0x76", h)
        self.assertIn("#define ENV_COV { 1, 0.01, 0.0025 }", h)  # _n() trims 1.0 -> 1
        self.assertEqual(h.count("#define ENV_COV"), 1)

        # From the front-end form shape (sensors.env = "BME280")
        fe = json.loads(json.dumps(self.valid_pico_spec))
        fe["sensors"]["env"] = "BME280"
        h2 = generate_config_header(fe)
        self.assertIn("#define USE_BMP280", h2)

    def test_modern_imu_roundtrip(self):
        for imu, macro in (("LSM6DSOX", "USE_LSM6DSOX_IMU"),
                           ("ICM20948", "USE_ICM20948_IMU")):
            fe = json.loads(json.dumps(self.valid_pico_spec))
            fe["sensors"]["imu"] = imu
            h = generate_config_header(fe)
            self.assertIn(f"#define {macro}", h)

        # Enabling a known IMU with no explicit covariance -> datasheet default
        fe = json.loads(json.dumps(self.valid_pico_spec))
        fe["sensors"]["imu"] = "LSM6DSOX"
        fe.pop("imu_tuning", None)
        h = generate_config_header(fe)
        self.assertIn("#define ACCEL_COV { 4.7e-05, 4.7e-05, 4.7e-05 }", h)
        self.assertIn("#define GYRO_COV { 4.4e-07, 4.4e-07, 4.4e-07 }", h)
        # An explicit value still wins over the default.
        fe["imu_tuning"] = {"accel_cov": 0.02}
        h = generate_config_header(fe)
        self.assertIn("#define ACCEL_COV { 0.02, 0.02, 0.02 }", h)
        self.assertEqual(h.count("#define ACCEL_COV"), 1)
        raw = ("#ifndef ICMBOT_CONFIG_H\n#define ICMBOT_CONFIG_H\n"
               "#define USE_ICM20948_IMU\n#define USE_ICM20948_MAG\n#endif\n")
        spec = parse_header_to_spec(raw)
        self.assertEqual(spec["sensors"]["imu_type"], "USE_ICM20948_IMU")
        self.assertEqual(spec["sensors"]["mag_type"], "USE_ICM20948_MAG")
        h = generate_config_header(spec)
        self.assertEqual(h.count("#define USE_ICM20948_IMU"), 1)
        self.assertIn("#define USE_ICM20948_MAG", h)

    def test_pid_magbias_covariance_topicprefix_roundtrip(self):
        raw = """
#ifndef TUNEBOT_CONFIG_H
#define TUNEBOT_CONFIG_H
#define LINO_BASE DIFFERENTIAL_DRIVE
#define USE_BTS7960_MOTOR_DRIVER
#define K_P 0.75
#define K_I 0.9
#define K_D 0.42
#define MAG_BIAS { 12.5, -3.0, 7.25 }
#define ACCEL_COV { 0.01, 0.01, 0.01 }
#define GYRO_COV { 0.002, 0.002, 0.002 }
#define ORI_COV { 0.03, 0.03, 0.03 }
#define TOPIC_PREFIX "robot1/"
#define BAUDRATE 921600
#endif
"""
        spec = parse_header_to_spec(raw)
        self.assertEqual(spec["pid"], {"kp": 0.75, "ki": 0.9, "kd": 0.42})
        self.assertEqual(spec["imu_tuning"]["mag_bias"], [12.5, -3.0, 7.25])
        self.assertEqual(spec["imu_tuning"]["accel_cov"], 0.01)
        self.assertEqual(spec["imu_tuning"]["gyro_cov"], 0.002)
        self.assertEqual(spec["advanced"]["topic_prefix"], "robot1/")

        h = generate_config_header(spec)
        self.assertIn("#define K_P 0.75", h)
        self.assertIn("#define K_I 0.9", h)
        self.assertIn("#define K_D 0.42", h)
        self.assertIn("#define MAG_BIAS { 12.5, -3, 7.25 }", h)
        self.assertIn("#define ACCEL_COV { 0.01, 0.01, 0.01 }", h)
        self.assertIn("#define GYRO_COV { 0.002, 0.002, 0.002 }", h)
        self.assertIn('#define TOPIC_PREFIX "robot1/"', h)
        # exactly one definition of each (no passthrough double-emit)
        self.assertEqual(h.count("#define ACCEL_COV"), 1)
        self.assertEqual(h.count("#define TOPIC_PREFIX"), 1)
        self.assertEqual(h.count("#define K_P"), 1)

    def test_dac_pin_roundtrip_and_mcu_gating(self):
        # ESP32 header with a non-default DAC pin -> parsed, then re-emitted.
        raw = """
#ifndef DACBOT_CONFIG_H
#define DACBOT_CONFIG_H
#define LINO_BASE DIFFERENTIAL_DRIVE
#define USE_BTS7960_MOTOR_DRIVER
#define BATTERY_PIN 33
#define DAC_PIN 26
#define BATTERY_ADJUST(v) ((v) * ((30 + 7.5) / 7.5) / 1000.0)
#define BAUDRATE 921600
#endif
"""
        spec = parse_header_to_spec(raw)
        self.assertEqual(spec["sensors"].get("dac_pin"), 26)
        self.assertEqual(spec["pins"].get("dac_pin"), 26)
        spec["mcu"] = "ESP32"
        h = generate_config_header(spec)
        self.assertIn("#define DAC_PIN 26", h)
        self.assertEqual(h.count("#define DAC_PIN"), 1)

        # Same spec on a DAC-less MCU (Pico) -> DAC_PIN must NOT be emitted.
        pico = json.loads(json.dumps(self.valid_pico_spec))
        pico["pins"]["dac_pin"] = 25
        hp = generate_config_header(pico)
        self.assertNotIn("#define DAC_PIN", hp)

        # ESP32 form-shape spec with a DAC pin -> emitted.
        esp = json.loads(json.dumps(self.valid_pico_spec))
        esp["mcu"] = "ESP32"
        esp["pins"]["dac_pin"] = 25
        he = generate_config_header(esp)
        self.assertIn("#define DAC_PIN 25", he)

    def test_adc_lut_roundtrip_and_merge_preserves_it(self):
        # A previously-calibrated header with a short LUT (real ones are
        # always 4096 entries; a short one exercises the same regex/format).
        raw = """
#ifndef LUTBOT_CONFIG_H
#define LUTBOT_CONFIG_H
#define LINO_BASE DIFFERENTIAL_DRIVE
#define BATTERY_PIN 33
#define DAC_PIN 25
#define USE_ADC_LUT
const int16_t ADC_LUT[4096] = {
    0, 50, 53, 57, 60, 64, 65, 66,
    3959, 3967
};
#define BAUDRATE 921600
#endif
"""
        spec = parse_header_to_spec(raw)
        self.assertEqual(spec["sensors"].get("adc_lut"),
                          [0, 50, 53, 57, 60, 64, 65, 66, 3959, 3967])

        spec["mcu"] = "ESP32"
        h = generate_config_header(spec)
        self.assertIn("#define USE_ADC_LUT", h)
        self.assertIn("const int16_t ADC_LUT[4096] = {", h)
        self.assertIn("ADC_LUT[v]", h)   # LUT-linearized BATTERY_ADJUST
        self.assertEqual(h.count("#define USE_ADC_LUT"), 1)

        # merge_configurations: an overlay that doesn't touch sensors.adc_lut
        # must NOT drop the calibrated LUT already on disk.
        overlay_no_lut = {"sensors": {"battery_min_voltage": 9.5}}
        merged, _ = merge_configurations(spec, overlay_no_lut)
        self.assertEqual(merged["sensors"]["adc_lut"], spec["sensors"]["adc_lut"])
        self.assertEqual(merged["sensors"]["battery_min_voltage"], 9.5)

        # An overlay that DOES set a new LUT (e.g. a fresh calibration run)
        # replaces the old one — overlay wins, per merge_configurations.
        overlay_new_lut = {"sensors": {"adc_lut": [1, 2, 3]}}
        merged3, changes = merge_configurations(spec, overlay_new_lut)
        self.assertEqual(merged3["sensors"]["adc_lut"], [1, 2, 3])
        self.assertTrue(any(c["field"] == "sensors.adc_lut" for c in changes))

    def test_merge_overlay_wins_over_parsed_battery_fields(self):
        # Regression: parser.py used to store BATTERY_MIN/MAX/CAP and the
        # divider resistors under different key names than the web-UI form
        # overlay uses (battery_min vs. battery_min_voltage, etc). Because
        # merge_configurations() does a deep key-merge, that mismatch meant
        # an overlay's new value landed under its own key while the OLD
        # value stayed live under the base's key — and generator.py's
        # fallback chain checked the stale key first, so the overlay's
        # change was silently dropped. This locks in that the same key is
        # used both ways, so a merge genuinely overwrites.
        raw = """
#ifndef VOLTBOT_CONFIG_H
#define VOLTBOT_CONFIG_H
#define LINO_BASE DIFFERENTIAL_DRIVE
#define BATTERY_PIN 33
#define BATTERY_MIN 9
#define BAUDRATE 921600
#endif
"""
        base = parse_header_to_spec(raw)
        self.assertEqual(base["sensors"]["battery_min_voltage"], 9.0)
        self.assertEqual(base["sensors"]["battery_r1"], 30000.0)
        self.assertEqual(base["sensors"]["battery_r2"], 7500.0)

        # Overlay changes the min-cutoff voltage (form field name) — must win.
        overlay = {"sensors": {"battery_min_voltage": 7.5}}
        merged, changes = merge_configurations(base, overlay)
        self.assertEqual(merged["sensors"]["battery_min_voltage"], 7.5)
        self.assertFalse("battery_min" in merged["sensors"])  # no stale duplicate key

        base["mcu"] = "ESP32"
        merged["mcu"] = "ESP32"
        h_before = generate_config_header(base)
        h_after = generate_config_header(merged)
        self.assertIn("#define BATTERY_MIN 9", h_before)
        self.assertIn("#define BATTERY_MIN 7.5", h_after)
        self.assertNotIn("#define BATTERY_MIN 9", h_after)

    def test_user_modify_and_merge_workflow(self):
        # 1. User starts with an existing header (Fake IMU/Mag)
        raw_header = """
#ifndef MYROBOT_CONFIG_H
#define MYROBOT_CONFIG_H
#define LINO_BASE DIFFERENTIAL_DRIVE
#define WHEEL_DIAMETER 0.0800
#define LR_WHEELS_DISTANCE 0.2200
#define USE_GENERIC_2_IN_MOTOR_DRIVER
#define MOTOR_MAX_RPM 330
#define COUNTS_PER_REV1 1440
#define USE_FAKE_IMU
#define USE_FAKE_MAG
#define BAUDRATE 921600
#endif
"""
        base_spec = parse_header_to_spec(raw_header)
        self.assertEqual(base_spec["sensors"]["imu_type"], "USE_FAKE_IMU")

        # 2. User modifies settings in Web UI: adds QMI8658 IMU, AK09918 Mag, Sonar, and Dual-Core
        modified_settings = {
            "sensors": {
                "imu_type": "USE_QMI8658_IMU",
                "mag_type": "USE_AK09918_MAG",
                "sonar_trig": 19,
                "sonar_echo": 18
            },
            "telemetry": {
                "use_dual_core": True,
                "baudrate": 921600
            }
        }

        merged_spec, changes = merge_configurations(base_spec, modified_settings)
        self.assertGreater(len(changes), 0)

        # 3. Generate merged C++ header
        updated_header = generate_config_header(merged_spec)
        self.assertIn("#define USE_QMI8658_IMU", updated_header)
        self.assertIn("#define USE_AK09918_MAG", updated_header)
        self.assertIn("#define TRIG_PIN 19", updated_header)
        self.assertIn("#define ECHO_PIN 18", updated_header)
        self.assertIn("#define USE_DUAL_CORE", updated_header)
        self.assertNotIn("#define USE_FAKE_IMU", updated_header)
        self.assertNotIn("#define USE_FAKE_MAG", updated_header)

if __name__ == "__main__":
    unittest.main()
