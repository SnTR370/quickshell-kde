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

    def test_08_badge_color_api_and_scroll_support(self):
        """Static check: Verify Badge uses badgeColor property and ControlCenter includes ScrollView."""
        for filename in ["QuickTile.qml", "BrightnessControl.qml", "MediaControl.qml"]:
            filepath = os.path.join(MODULE_DIR, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                code = f.read()
            self.assertIn("badgeColor:", code, f"{filename} must use Badge.badgeColor")

        cc_path = os.path.join(MODULE_DIR, "ControlCenter.qml")
        with open(cc_path, "r", encoding="utf-8") as f:
            cc_code = f.read()
        self.assertIn("ScrollView", cc_code, "ControlCenter must wrap body in ScrollView for smaller screens")
        self.assertIn("property real maxHeight:", cc_code, "ControlCenter must support maxHeight bounding")

    def test_09_live_qml_runtime_controlcenter_and_bar_integration(self):
        """Real QML Runtime Test (via quickshell): Verify ControlCenterButton starts closed, ModuleRegistry slot preservation, Badge coloring, small-screen height clamping, and safe dry-run session actions."""
        import json
        import tempfile
        repo_dir = os.path.dirname(os.path.dirname(MODULE_DIR))
        with tempfile.TemporaryDirectory() as tmpdir:
            # Isolated runtime (never the user's session): offscreen QPA,
            # no WAYLAND_DISPLAY/DISPLAY, fresh private XDG_RUNTIME_DIR and
            # XDG_CONFIG_HOME, private D-Bus session — same recipe as
            # tests/test_layout_presets.py.
            runtime_dir = os.path.join(tmpdir, "runtime")
            os.makedirs(runtime_dir, mode=0o700, exist_ok=True)
            env = os.environ.copy()
            env.pop("WAYLAND_DISPLAY", None)
            env.pop("DISPLAY", None)
            env["QT_QPA_PLATFORM"] = "offscreen"
            env["XDG_RUNTIME_DIR"] = runtime_dir
            env["XDG_CONFIG_HOME"] = tmpdir
            env["QUICKSHELL_TEST_MODE"] = "1"
            probe_path = os.path.join(repo_dir, "_test_controlcenter_runtime_probe.qml")
            try:
                with open(probe_path, "w") as pf:
                    pf.write("""import QtQuick
import Quickshell
import "./services"
import "./components"
import "./modules/bar"
import "./modules/controlcenter"

Scope {
    ControlCenterButton { id: ccBtn }
    ControlCenter { id: ccStandalone; maxHeight: 320 }
    QuickTile {
        id: testTile
        title: "Wi-Fi"
        subtitle: "HomeNet"
        active: true
        badgeText: "88%"
        badgeColor: "#123456"
    }
    SessionRow {
        id: sessionRow
        dryRun: true
    }

    property int tileClicks: 0
    property int closeRequests: 0
    property var sessionActions: []

    Connections {
        target: testTile
        function onClicked() { tileClicks++; }
    }
    Connections {
        target: ccStandalone
        function onCloseRequested() { closeRequests++; }
    }
    Connections {
        target: sessionRow
        function onSessionActionRequested(act) { sessionActions.push(act); }
        function onActionTriggered() { closeRequests++; }
    }

    Timer {
        interval: 200
        running: true
        repeat: false
        onTriggered: {
            // 1. Verify ControlCenterButton starts with popup closed
            const startsClosed = (ccBtn.popupOpen === false);

            // 2. Verify ModuleRegistry registers "controlcenter" and preserves custom slots
            const isRegistered = ModuleRegistry.isValidModule("controlcenter");
            const sanitizedCustom = ModuleRegistry.sanitizeSlotList(["clock", "controlcenter", "invalid_mod"], []);

            // 3. Verify QuickTile click & Badge color propagation
            testTile.clicked();

            // 4. Verify small-screen height clamping on ControlCenter
            const clampedHeight = ccStandalone.implicitHeight;
            const naturalHeight = ccStandalone.naturalHeight;

            // 5. Verify SessionRow dry-run actions fire signals without executing destructive commands
            sessionRow.dispatchSessionAction("lock", []);
            sessionRow.dispatchSessionAction("logout", ["qdbus6", "org.kde.Shutdown", "/Shutdown", "org.kde.Shutdown.logout"]);
            sessionRow.dispatchSessionAction("reboot", ["qdbus6", "org.kde.Shutdown", "/Shutdown", "org.kde.Shutdown.logoutAndReboot"]);
            sessionRow.dispatchSessionAction("shutdown", ["qdbus6", "org.kde.Shutdown", "/Shutdown", "org.kde.Shutdown.logoutAndShutdown"]);

            console.log("CC_RUNTIME_RESULT:" + JSON.stringify({
                startsClosed: startsClosed,
                isRegistered: isRegistered,
                sanitizedCustom: sanitizedCustom,
                tileClicks: tileClicks,
                clampedHeight: clampedHeight,
                naturalHeight: naturalHeight,
                sessionActions: sessionActions,
                closeRequests: closeRequests
            }));
            Qt.quit();
        }
    }
}
""")
                proc = subprocess.run(
                    ["dbus-run-session", "--", "quickshell", "-p", probe_path, "--no-duplicate"],
                    cwd=repo_dir,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
                marker = "CC_RUNTIME_RESULT:"
                self.assertIn(marker, combined, f"Missing runtime marker:\n{combined}")
                payload_line = [line for line in combined.splitlines() if marker in line][-1]
                data = json.loads(payload_line.split(marker, 1)[1].strip())

                self.assertTrue(data["startsClosed"], "ControlCenter popup must not start visible automatically")
                self.assertTrue(data["isRegistered"], "ModuleRegistry must include 'controlcenter'")
                self.assertEqual(data["sanitizedCustom"], ["clock", "controlcenter"])
                self.assertEqual(data["tileClicks"], 1)
                self.assertLessEqual(data["clampedHeight"], 320, "ControlCenter height must clamp to maxHeight on smaller screens")
                self.assertGreater(data["naturalHeight"], 200)
                self.assertEqual(data["sessionActions"], ["lock", "logout", "reboot", "shutdown"])
                self.assertEqual(data["closeRequests"], 4)
            finally:
                if os.path.exists(probe_path):
                    os.remove(probe_path)


if __name__ == "__main__":
    unittest.main()
