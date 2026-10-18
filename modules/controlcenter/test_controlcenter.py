#!/usr/bin/env python3
"""
Unit and Integration Tests for quickshell-kde Control Center Module.
"""

import os
import subprocess
import unittest

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))

class TestControlCenterModule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected_files = [
            "qmldir",
            "ControlCenter.qml",
            "ControlCenterPopup.qml",
            "QuickTile.qml",
            "VolumeControl.qml",
            "BrightnessControl.qml",
            "MediaControl.qml",
            "SessionRow.qml",
            "tst_controlcenter.qml"
        ]

    def test_01_all_files_exist(self):
        """Verify all planned controlcenter module files are present."""
        for filename in self.expected_files:
            filepath = os.path.join(MODULE_DIR, filename)
            self.assertTrue(os.path.isfile(filepath), f"Missing file: {filename}")

    def test_02_qmldir_validity(self):
        """Verify qmldir correctly registers module components."""
        qmldir_path = os.path.join(MODULE_DIR, "qmldir")
        with open(qmldir_path, "r", encoding="utf-8") as f:
            content = f.read()

        required_symbols = [
            "ControlCenter 1.0 ControlCenter.qml",
            "ControlCenterPopup 1.0 ControlCenterPopup.qml",
            "QuickTile 1.0 QuickTile.qml",
            "VolumeControl 1.0 VolumeControl.qml",
            "BrightnessControl 1.0 BrightnessControl.qml",
            "MediaControl 1.0 MediaControl.qml",
            "SessionRow 1.0 SessionRow.qml"
        ]
        for symbol in required_symbols:
            self.assertIn(symbol, content, f"qmldir missing registration: {symbol}")

    def test_03_qmllint_verification(self):
        """Verify that qmllint reports zero syntax or semantic errors on all QML files."""
        qml_files = [
            os.path.join(MODULE_DIR, f)
            for f in os.listdir(MODULE_DIR)
            if f.endswith(".qml")
        ]
        self.assertGreater(len(qml_files), 0, "No QML files found to lint")

        cmd = ["qmllint"] + qml_files
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(
            proc.returncode,
            0,
            f"qmllint failed (exit {proc.returncode}):\nStdout: {proc.stdout}\nStderr: {proc.stderr}"
        )

    def test_04_audio_service_integration(self):
        """Verify VolumeControl strictly reuses existing AudioService APIs."""
        filepath = os.path.join(MODULE_DIR, "VolumeControl.qml")
        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()

        # Audio sink controls
        self.assertIn("AudioService.volume", code)
        self.assertIn("AudioService.muted", code)
        self.assertIn("AudioService.setVolume", code)
        self.assertIn("AudioService.toggleMute", code)
        self.assertIn("AudioService.openVolumeControl", code)

        # Microphone controls
        self.assertIn("AudioService.inputVolume", code)
        self.assertIn("AudioService.inputMuted", code)
        self.assertIn("AudioService.setInputVolume", code)
        self.assertIn("AudioService.toggleInputMute", code)

    def test_05_brightness_service_integration(self):
        """Verify BrightnessControl strictly reuses existing BrightnessService APIs."""
        filepath = os.path.join(MODULE_DIR, "BrightnessControl.qml")
        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertIn("BrightnessService.brightness", code)
        self.assertIn("BrightnessService.supported", code)
        self.assertIn("BrightnessService.setBrightness", code)
        self.assertIn("BrightnessService.displays", code)
        self.assertIn("BrightnessService.setBrightnessForDisplay", code)
        self.assertIn("kcm_kscreen", code)

    def test_06_connectivity_and_power_integration(self):
        """Verify ControlCenter binds to NetworkService and PowerService."""
        filepath = os.path.join(MODULE_DIR, "ControlCenter.qml")
        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()

        # Network integration
        self.assertIn("NetworkService.connected", code)
        self.assertIn("NetworkService.connectionType", code)
        self.assertIn("NetworkService.openNetworkSettings", code)

        # Power & Battery integration
        self.assertIn("PowerService.isPresent", code)
        self.assertIn("PowerService.percentage", code)
        self.assertIn("PowerService.isCharging", code)
        self.assertIn("kcm_powerdevilprofilesconfig", code)

    def test_07_no_invented_dbus_or_pollers(self):
        """Ensure no invented DBus interfaces or duplicate system polling in controlcenter."""
        for filename in self.expected_files:
            if not filename.endswith(".qml"):
                continue
            filepath = os.path.join(MODULE_DIR, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                code = f.read()

            # Should not create ad-hoc background processes or listeners
            self.assertNotIn("org.freedesktop.Notifications", code)
            self.assertNotIn("dbus-monitor", code)


if __name__ == "__main__":
    unittest.main()
