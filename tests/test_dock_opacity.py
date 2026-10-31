#!/usr/bin/env python3
"""
P1-1 remediation: independent Bar and Dock surface opacity.

Focused tests for ConfigService.dockOpacity:
- static wiring: Dock.qml binds ConfigService.dockOpacity (not barOpacity),
  SettingsWindow exposes a Dock Opacity slider, ConfigService loads/saves
  the dock "opacity" key and clamps setDockOpacity()
- isolated headless E2E (offscreen quickshell, private D-Bus/runtime/config,
  same recipe as tests/test_layout_presets.py):
    * inherit:  a dock config without "opacity" inherits the persisted
                barOpacity once (visual state preserved across the split)
                and later setBarOpacity() no longer moves the dock
    * explicit: a dock config with "opacity" keeps it independent of the
                bar value; setDockOpacity() clamps to [0.1, 1.0] and the
                value persists to dock_config.json
    * reload:   a fresh process restores the persisted dock opacity
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(path):
    with open(os.path.join(REPO, path)) as f:
        return f.read()


PROBE_QML = """import QtQuick
import Quickshell
import "./services"

Scope {
    id: root
    property string phase: Quickshell.env("DOCK_OPACITY_PHASE") || "inherit"
    property int tries: 0
    property bool done: false

    function log(marker, obj) {
        console.log(marker + ":" + JSON.stringify(obj));
    }

    Timer {
        interval: 200; running: true; repeat: true
        onTriggered: {
            if (root.done) return;
            // Wait until the seeded user config has been loaded
            // (seeded bar edge "left" + dock edge "right").
            if (ConfigService.barEdge !== "left" || ConfigService.dockEdge !== "right") {
                if (++root.tries < 60) return;
                root.done = true;
                root.log("DOCK-OPACITY-FAIL", {step: "seed-load-timeout",
                    barOpacity: ConfigService.barOpacity, dockOpacity: ConfigService.dockOpacity});
                Qt.exit(1);
                return;
            }
            root.done = true;
            if (root.phase === "inherit") {
                // Legacy dock config (no "opacity" key): the dock must have
                // inherited the persisted bar opacity once.
                root._inherited = ConfigService.dockOpacity;
                // Runtime bar changes must not move the dock anymore.
                ConfigService.setBarOpacity(0.8);
                waitAndFinish.start();
            } else if (root.phase === "explicit") {
                ConfigService.setDockOpacity(1.7);
                root._hi = ConfigService.dockOpacity;
                ConfigService.setDockOpacity(0.05);
                root._lo = ConfigService.dockOpacity;
                ConfigService.setDockOpacity(0.42);
                waitAndFinish.start();
            } else { // reload
                root.log("DOCK-OPACITY-RESULT", {
                    phase: root.phase,
                    barOpacity: ConfigService.barOpacity,
                    dockOpacity: ConfigService.dockOpacity
                });
                Qt.exit(0);
            }
        }
    }

    property real _inherited: 0
    property real _hi: 0
    property real _lo: 0

    Timer {
        id: waitAndFinish
        interval: 700
        onTriggered: {
            root.log("DOCK-OPACITY-RESULT", {
                phase: root.phase,
                inherited: root._inherited,
                clampedHigh: root._hi,
                clampedLow: root._lo,
                barOpacityAfterBarChange: ConfigService.barOpacity,
                dockOpacity: ConfigService.dockOpacity
            });
            Qt.exit(0);
        }
    }

    Timer {
        interval: 20000; running: true; repeat: false
        onTriggered: { root.log("DOCK-OPACITY-FAIL", {step: "global-timeout"}); Qt.exit(1); }
    }
}
"""


class TestDockOpacityWiring(unittest.TestCase):
    def test_dock_binds_dock_opacity(self):
        dock = read("modules/dock/Dock.qml")
        self.assertIn("ConfigService.dockOpacity", dock)
        self.assertNotIn("ConfigService.barOpacity", dock)

    def test_settings_ui_has_dock_opacity_slider(self):
        settings = read("modules/settings/SettingsWindow.qml")
        self.assertIn("Dock Opacity", settings)
        self.assertIn("ConfigService.setDockOpacity(parseFloat(val.toFixed(2)))", settings)

    def test_config_service_wiring(self):
        cfg = read("services/config/ConfigService.qml")
        self.assertIn("property real dockOpacity: 0.92", cfg)
        self.assertIn("function setDockOpacity(op)", cfg)
        self.assertIn('"opacity": root.dockOpacity', cfg)
        # Load path clamps and marks the value explicit.
        self.assertIn('root.dockOpacity = Math.max(0.1, Math.min(1.0, parsed.opacity));', cfg)
        self.assertIn("root._dockOpacityExplicit = true;", cfg)
        # One-time inheritance from the persisted bar opacity.
        self.assertIn("if (!root._dockOpacityExplicit", cfg)

    def test_qml_lint(self):
        res = subprocess.run(
            ["qmllint", "services/config/ConfigService.qml",
             "modules/dock/Dock.qml",
             "modules/settings/SettingsWindow.qml"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"qmllint failed: {res.stderr}")


class TestDockOpacityRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which("quickshell") is None or shutil.which("dbus-run-session") is None:
            raise unittest.SkipTest("quickshell or dbus-run-session not available")
        cls.testroot = tempfile.mkdtemp(prefix="qs-dock-opacity-")
        cls.probe = os.path.join(REPO, "_test_dock_opacity_probe.qml")
        with open(cls.probe, "w") as f:
            f.write(PROBE_QML)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.probe):
            os.remove(cls.probe)
        if hasattr(cls, "testroot"):
            shutil.rmtree(cls.testroot, ignore_errors=True)

    def _run_phase(self, phase, bar, dock):
        config_home = os.path.join(self.testroot, "cfg-" + phase)
        cfgdir = os.path.join(config_home, "quickshell-kde")
        os.makedirs(cfgdir, exist_ok=True)
        with open(os.path.join(cfgdir, "bar_config.json"), "w") as f:
            json.dump(bar, f)
        with open(os.path.join(cfgdir, "dock_config.json"), "w") as f:
            json.dump(dock, f)
        env = dict(os.environ)
        env.pop("WAYLAND_DISPLAY", None)
        env.pop("DISPLAY", None)
        runtime_dir = os.path.join(self.testroot, "rt-" + phase)
        os.makedirs(runtime_dir, mode=0o700, exist_ok=True)
        env.update({
            "QT_QPA_PLATFORM": "offscreen",
            "XDG_RUNTIME_DIR": runtime_dir,
            "XDG_CONFIG_HOME": config_home,
            "DOCK_OPACITY_PHASE": phase,
        })
        proc = subprocess.run(
            ["dbus-run-session", "--", "quickshell", "-p", self.probe, "--no-duplicate"],
            cwd=REPO, env=env, capture_output=True, text=True, timeout=60)
        combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
        lines = [ln for ln in combined.splitlines() if "DOCK-OPACITY-" in ln]
        self.assertTrue(lines, f"missing result marker in output:\n{combined}")
        return json.loads(lines[-1].split("DOCK-OPACITY-RESULT:", 1)[-1]
                          if "DOCK-OPACITY-RESULT:" in lines[-1]
                          else lines[-1].split("DOCK-OPACITY-FAIL:", 1)[-1]), config_home

    def test_inherit_and_independence(self):
        bar = {"edge": "left", "opacity": 0.55}
        dock = {"edge": "right"}  # legacy config: no dock opacity key
        data, _ = self._run_phase("inherit", bar, dock)
        self.assertAlmostEqual(data["inherited"], 0.55, places=2,
                               msg="legacy dock config must inherit the persisted bar opacity")
        self.assertAlmostEqual(data["dockOpacity"], 0.55, places=2,
                               msg="setBarOpacity must not move the dock opacity")
        self.assertAlmostEqual(data["barOpacityAfterBarChange"], 0.8, places=2)

    def test_explicit_clamp_and_persist(self):
        bar = {"edge": "left", "opacity": 0.55}
        dock = {"edge": "right", "opacity": 0.7}
        data, config_home = self._run_phase("explicit", bar, dock)
        self.assertAlmostEqual(data["clampedHigh"], 1.0, places=2,
                               msg="setDockOpacity(1.7) must clamp to 1.0")
        self.assertAlmostEqual(data["clampedLow"], 0.1, places=2,
                               msg="setDockOpacity(0.05) must clamp to 0.1")
        self.assertAlmostEqual(data["dockOpacity"], 0.42, places=2,
                               msg="setDockOpacity(0.42) must win")
        with open(os.path.join(config_home, "quickshell-kde", "dock_config.json")) as f:
            saved = json.load(f)
        self.assertAlmostEqual(saved.get("opacity"), 0.42, places=2,
                               msg="dock opacity must persist to dock_config.json")

    def test_reload_restores_persisted_value(self):
        bar = {"edge": "left", "opacity": 0.55}
        dock = {"edge": "right", "opacity": 0.62}
        data, _ = self._run_phase("reload", bar, dock)
        self.assertAlmostEqual(data["dockOpacity"], 0.62, places=2)
        self.assertAlmostEqual(data["barOpacity"], 0.55, places=2)


if __name__ == "__main__":
    unittest.main()
