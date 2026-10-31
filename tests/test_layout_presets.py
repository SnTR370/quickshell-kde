#!/usr/bin/env python3
"""
Layout preset verification suite for quickshell-kde (native layout presets).

Covers:
1. Preset catalog integrity (LayoutPresets.js executed under node)
2. Target layout validation: ranges, module ids, surface/Settings lockout
3. Diff / describe / match logic and preservation of non-layout keys
4. Static source contracts (ConfigService API, Settings UI, Control Center
   Settings entry, live bindings in Bar/Dock, untouched first-launch defaults)
5. QML lint of the touched files
6. Isolated runtime E2E: seeded user config -> apply preset -> live property
   update -> persistence on disk -> fresh process reload (restart survival)
   -> early-apply race (preset applied before the config store finishes
   loading). Runs quickshell offscreen with private XDG dirs and a private
   D-Bus session; the live Plasma session is never touched.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRESETS_JS = os.path.join(REPO, "services/config/LayoutPresets.js")

# The 11 modules registered in services/core/ModuleRegistry.qml.
VALID_MODULES = ["launcher", "workspaces", "clock", "media", "tray", "network",
                 "battery", "audio", "brightness", "controlcenter", "power"]

BAR_KEYS = ["enabled", "floating", "edge", "edgeOffset", "reserveSpace",
            "height", "left", "center", "right"]
DOCK_KEYS = ["enabled", "floating", "edge", "edgeOffset", "reserveSpace",
             "iconSize", "autoHide", "intellihide"]

# A user config that differs from every preset in both layout and preserved
# keys, used to seed the runtime E2E phases.
SEED_BAR = {
    "enabled": True, "floating": True, "edge": "left", "edgeOffset": 12,
    "reserveSpace": False, "height": 44,
    "left": ["workspaces"], "center": ["media"], "right": ["clock", "audio"],
    "opacity": 0.55, "monitors": ["DP-1"], "blur": False,
    "notificationsEnabled": True,
    "trayItemPolicies": {"org.example.App": "always"},
    "controlCenterMigrated": True,
}
SEED_DOCK = {
    "enabled": True, "floating": False, "edge": "right", "edgeOffset": 10,
    "reserveSpace": True, "iconSize": 52, "autoHide": True, "intellihide": True,
    "hideDelay": 500, "revealDelay": 80, "monitors": ["DP-1"],
    "windowFilter": "desktop", "pinned": ["org.kde.dolphin", "firefox"],
}

# Minimal-preset expectations for the seeded runtime phases.
MINIMAL_BAR = {"enabled": True, "floating": True, "edge": "top", "edgeOffset": 6,
               "reserveSpace": False, "height": 26,
               "left": ["launcher"], "center": ["clock"],
               "right": ["audio", "controlcenter", "power"]}
MINIMAL_DOCK = {"enabled": True, "floating": True, "edge": "bottom", "edgeOffset": 6,
                "reserveSpace": False, "iconSize": 36, "autoHide": True,
                "intellihide": False}


def read(rel):
    with open(os.path.join(REPO, rel)) as f:
        return f.read()


def node_eval(payload):
    driver = (
        "const vm=require('vm'),fs=require('fs');\n"
        "const ctxo={};vm.createContext(ctxo);\n"
        "vm.runInContext(fs.readFileSync(process.argv[1],'utf8')"
        ".replace(/^\\.pragma.*$/m,''),ctxo);\n"
        "const L=ctxo;\n"
        "const input=JSON.parse(process.argv[2]);\n"
        "const out={};\n"
        "if(input.op==='catalog'){out.ids=L.getPresetIds();"
        "out.unknown=L.getPreset('nope');"
        "out.presets=L.PRESETS.map(p=>({id:p.id,name:p.name,icon:p.icon,"
        "description:p.description,barKeys:Object.keys(p.bar).sort(),"
        "dockKeys:Object.keys(p.dock).sort()}));}\n"
        "else if(input.op==='target'){const t=L.buildTargetLayout("
        "L.getPreset(input.preset),input.valid);"
        "out.target=t;out.check=L.validateLayout(t,input.valid);}\n"
        "else if(input.op==='check'){"
        "out.check=L.validateLayout(input.layout,input.valid);}\n"
        "else if(input.op==='diff'){"
        "out.diff=L.diffLayouts(input.current,input.target);}\n"
        "else if(input.op==='describe'){"
        "out.described=L.describeChanges(input.current,input.target,"
        "input.names||null);}\n"
        "else if(input.op==='matches'){out.matches=L.matchesPreset("
        "input.current,L.getPreset(input.preset),input.valid);}\n"
        "else if(input.op==='sanitizeslots'){out.slots=L.sanitizeSlots("
        "input.slots,input.valid);}\n"
        "console.log(JSON.stringify(out));\n"
    )
    p = subprocess.run(["node", "-e", driver, PRESETS_JS, json.dumps(payload)],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


def run_node(payload):
    return node_eval(payload)


def target_of(preset_id):
    r = run_node({"op": "target", "preset": preset_id, "valid": VALID_MODULES})
    assert r["check"]["valid"], r["check"]
    return r["target"]


class TestPresetCatalog(unittest.TestCase):
    def test_catalog_integrity(self):
        r = run_node({"op": "catalog"})
        self.assertEqual(r["ids"], ["everyday", "classic", "minimal"])
        self.assertIsNone(r["unknown"])
        self.assertEqual(len(r["presets"]), 3)
        ids = [p["id"] for p in r["presets"]]
        self.assertEqual(len(set(ids)), 3, "preset ids must be unique")
        for p in r["presets"]:
            self.assertTrue(p["name"], p)
            self.assertTrue(p["icon"], p)
            self.assertTrue(p["description"], p)
            self.assertEqual(sorted(BAR_KEYS), p["barKeys"], p["id"] + " bar keys")
            self.assertEqual(sorted(DOCK_KEYS), p["dockKeys"], p["id"] + " dock keys")

    def test_preset_modules_are_registered(self):
        registry = read("services/core/ModuleRegistry.qml")
        registered = set(re.findall(r'id:\s*"([a-z]+)"', registry))
        for preset_id in ("everyday", "classic", "minimal"):
            t = target_of(preset_id)
            for slot in ("left", "center", "right"):
                for mod in t["bar"][slot]:
                    self.assertIn(mod, registered,
                                  f"{preset_id}.{slot} references unregistered module {mod}")

    def test_first_launch_defaults_untouched(self):
        """Requirement: existing installations and first-launch defaults must remain functional."""
        bar = json.loads(read("config/bar_config.json"))
        dock = json.loads(read("config/dock_config.json"))
        self.assertTrue(bar["enabled"])
        self.assertEqual(bar["edge"], "top")
        self.assertTrue(dock["enabled"])
        self.assertEqual(dock["edge"], "bottom")
        self.assertIn("pinned", dock)


class TestPresetValidation(unittest.TestCase):
    def test_all_preset_targets_valid(self):
        for preset_id in ("everyday", "classic", "minimal"):
            t = target_of(preset_id)
            r = run_node({"op": "check", "layout": t, "valid": VALID_MODULES})
            self.assertTrue(r["check"]["valid"], f"{preset_id}: {r['check']}")

    def _reject(self, layout, fragment):
        r = run_node({"op": "check", "layout": layout, "valid": VALID_MODULES})
        self.assertFalse(r["check"]["valid"], f"expected rejection, got {r['check']}")
        self.assertIn(fragment, r["check"]["reason"])

    def test_rejects_both_surfaces_disabled(self):
        t = target_of("everyday")
        t["bar"]["enabled"] = False
        t["dock"]["enabled"] = False
        self._reject(t, "both be disabled")

    def test_rejects_dock_disabled_without_launcher(self):
        t = target_of("classic")
        t["bar"]["left"] = ["workspaces", "media"]
        self._reject(t, "launcher module")

    def test_rejects_dock_disabled_without_controlcenter(self):
        t = target_of("classic")
        t["bar"]["right"] = ["clock", "tray", "network", "battery", "audio", "power"]
        self._reject(t, "control center module")

    def test_rejects_unknown_module(self):
        t = target_of("everyday")
        t["bar"]["left"] = ["launcher", "nonexistent"]
        self._reject(t, "Unknown module 'nonexistent'")

    def test_rejects_module_in_multiple_slots(self):
        t = target_of("everyday")
        t["bar"]["center"] = ["clock", "launcher"]
        self._reject(t, "multiple Bar slots")

    def test_rejects_invalid_edge(self):
        t = target_of("everyday")
        t["bar"]["edge"] = "diagonal"
        self._reject(t, "Invalid bar edge")

    def test_rejects_out_of_range_values(self):
        for key, value, section in (("height", 200, "bar"), ("edgeOffset", -4, "bar"),
                                    ("iconSize", 500, "dock"), ("edgeOffset", 999, "dock")):
            t = target_of("everyday")
            t[section][key] = value
            self._reject(t, "out of range")

    def test_rejects_missing_and_malformed_keys(self):
        t = target_of("everyday")
        del t["dock"]["iconSize"]
        self._reject(t, "missing")
        t2 = target_of("everyday")
        t2["bar"]["left"] = "launcher"
        self._reject(t2, "must be an array")

    def test_bar_disabled_dock_enabled_is_valid(self):
        t = target_of("everyday")
        t["bar"]["enabled"] = False
        r = run_node({"op": "check", "layout": t, "valid": VALID_MODULES})
        self.assertTrue(r["check"]["valid"], r["check"])

    def test_sanitize_slots(self):
        r = run_node({"op": "sanitizeslots",
                      "slots": ["clock", "bogus", "clock", 5, "power", None],
                      "valid": VALID_MODULES})
        self.assertEqual(r["slots"], ["clock", "power"])


class TestPresetDiffLogic(unittest.TestCase):
    def test_diff_empty_for_identical_layouts(self):
        t = target_of("everyday")
        self.assertEqual(run_node({"op": "diff", "current": t, "target": t})["diff"], [])

    def test_diff_reports_only_changed_keys(self):
        current = target_of("everyday")
        current["bar"]["height"] = 30
        current["bar"]["edge"] = "bottom"
        target = target_of("everyday")
        diff = run_node({"op": "diff", "current": current, "target": target})["diff"]
        keys = {(d["section"], d["key"]) for d in diff}
        self.assertEqual(keys, {("bar", "height"), ("bar", "edge")})
        by = {(d["section"], d["key"]): d for d in diff}
        self.assertEqual(by[("bar", "height")]["from"], 30)
        self.assertEqual(by[("bar", "height")]["to"], 32)

    def test_diff_detects_slot_array_changes(self):
        current = target_of("minimal")
        current["bar"]["right"] = ["power", "audio", "controlcenter"]  # order change
        target = target_of("minimal")
        diff = run_node({"op": "diff", "current": current, "target": target})["diff"]
        self.assertEqual(len(diff), 1)
        self.assertEqual(diff[0]["key"], "right")

    def test_diff_never_touches_preserved_keys(self):
        """Pinned apps, monitors, theme, opacity etc. are user preferences."""
        current = target_of("everyday")
        current["bar"]["opacity"] = 0.4
        current["bar"]["monitors"] = ["HDMI-A-1"]
        current["bar"]["blur"] = False
        current["dock"]["pinned"] = ["a", "b"]
        current["dock"]["windowFilter"] = "desktop"
        target = target_of("classic")
        diff = run_node({"op": "diff", "current": current, "target": target})["diff"]
        for d in diff:
            self.assertIn(d["key"], BAR_KEYS if d["section"] == "bar" else DOCK_KEYS,
                          f"non-layout key {d['section']}.{d['key']} leaked into preset diff")

    def test_describe_changes_formatting(self):
        current = target_of("classic")  # attached, bottom, reserved
        target = target_of("everyday")  # floating, top, zero strut
        r = run_node({"op": "describe", "current": current, "target": target,
                      "names": {"launcher": "Application Launcher", "workspaces": "Virtual Desktops"}})
        described = {(d["section"], d["key"]): d for d in r["described"]}
        self.assertIn(("bar", "floating"), described)
        self.assertEqual(described[("bar", "floating")]["fromText"], "Attached panel")
        self.assertEqual(described[("bar", "floating")]["toText"], "Floating island")
        self.assertEqual(described[("bar", "edge")]["fromText"], "Bottom")
        self.assertEqual(described[("bar", "height")]["toText"], "32 px")
        self.assertIn(("dock", "enabled"), described)
        self.assertEqual(described[("dock", "enabled")]["fromText"], "Off")
        left = described[("bar", "left")]
        self.assertIn("Application Launcher", left["toText"])
        self.assertIn("Virtual Desktops", left["toText"])

    def test_matches_preset(self):
        t = target_of("minimal")
        self.assertTrue(run_node({"op": "matches", "preset": "minimal",
                                  "current": t, "valid": VALID_MODULES})["matches"])
        t2 = target_of("minimal")
        t2["bar"]["height"] = 40
        self.assertFalse(run_node({"op": "matches", "preset": "minimal",
                                   "current": t2, "valid": VALID_MODULES})["matches"])


class TestStaticContracts(unittest.TestCase):
    def test_config_service_preset_api(self):
        src = read("services/config/ConfigService.qml")
        self.assertIn('import "LayoutPresets.js" as LayoutPresets', src)
        for fn in ("function applyLayoutPreset(",
                   "function getLayoutPresetDiff(",
                   "function layoutPresetMatches(",
                   "function getLayoutPreset("):
            self.assertIn(fn, src)
        # Apply must respect the modified-before-load protocol so a preset
        # applied during startup is not overwritten by the config load.
        self.assertIn("for (let i = 0; i < barKeys.length; i++) root._markBarModified(barKeys[i]);", src)
        self.assertIn("for (let j = 0; j < dockKeys.length; j++) root._markDockModified(dockKeys[j]);", src)
        # The legacy control-center migration must not mutate applied presets.
        self.assertIn("root.controlCenterMigrated = true;", src)

    def test_settings_ui_preset_section(self):
        src = read("modules/settings/SettingsWindow.qml")
        self.assertIn("Layout Presets", src)
        self.assertIn("ConfigService.applyLayoutPreset(settingsWin.pendingPresetId)", src)
        self.assertIn("ConfigService.getLayoutPresetDiff(settingsWin.pendingPresetId)", src)
        self.assertIn("Apply Preset", src)
        self.assertIn("What will change", src)
        self.assertIn("enabled: presetPreview.pendingChanges.length > 0", src)

    def test_control_center_has_settings_entry(self):
        """Without the Dock, the Control Center is the Settings entry point (lockout prevention)."""
        src = read("modules/controlcenter/ControlCenter.qml")
        self.assertIn("ConfigService.toggleSettings", src)

    def test_surfaces_bind_config_directly(self):
        """Live UI update: Bar/Dock must keep binding ConfigService properties directly."""
        bar = read("modules/bar/Bar.qml")
        dock = read("modules/dock/Dock.qml")
        for fragment in ("visible: ConfigService.barEnabled",
                         "model: ConfigService.barLeft",
                         "model: ConfigService.barCenter",
                         "model: ConfigService.barRight"):
            self.assertIn(fragment, bar)
        for fragment in ("visible: ConfigService.dockEnabled",
                         # DOCK-012: dock geometry flows through the reactive
                         # per-monitor profile (which itself binds the global
                         # ConfigService properties), so preset application
                         # still updates the Dock live.
                         "ConfigService.effectiveDockProfile(",
                         "monitorProfile.iconSize"):
            self.assertIn(fragment, dock)

    def test_qml_lint(self):
        res = subprocess.run(
            ["qmllint", "services/config/ConfigService.qml",
             "modules/settings/SettingsWindow.qml",
             "modules/controlcenter/ControlCenter.qml"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"qmllint failed: {res.stderr}")


PROBE_QML = """import QtQuick
import Quickshell
import "./services"

Scope {
    id: root
    // Phases: "apply" (wait for seeded config, apply preset), "race" (apply
    // before the config store finished loading), "verify" (fresh process:
    // reload the persisted preset layout).
    property string phase: Quickshell.env("LAYOUT_PRESET_PHASE") || "apply"
    property string presetId: Quickshell.env("LAYOUT_PRESET_ID") || "minimal"
    property int tries: 0
    property bool applied: false
    property bool verified: false

    function snapshot() {
        return {
            barEnabled: ConfigService.barEnabled, barFloating: ConfigService.barFloating,
            barEdge: ConfigService.barEdge, barEdgeOffset: ConfigService.barEdgeOffset,
            barReserveSpace: ConfigService.barReserveSpace, barHeight: ConfigService.barHeight,
            barLeft: ConfigService.barLeft, barCenter: ConfigService.barCenter,
            barRight: ConfigService.barRight, barOpacity: ConfigService.barOpacity,
            barMonitors: ConfigService.barMonitors, blurEnabled: ConfigService.blurEnabled,
            notificationsEnabled: ConfigService.notificationsEnabled,
            trayItemPolicies: ConfigService.trayItemPolicies,
            dockEnabled: ConfigService.dockEnabled, dockFloating: ConfigService.dockFloating,
            dockEdge: ConfigService.dockEdge, dockEdgeOffset: ConfigService.dockEdgeOffset,
            dockReserveSpace: ConfigService.dockReserveSpace, dockIconSize: ConfigService.dockIconSize,
            dockAutoHide: ConfigService.dockAutoHide, dockIntellihide: ConfigService.dockIntellihide,
            dockMonitors: ConfigService.dockMonitors, dockWindowFilter: ConfigService.dockWindowFilter,
            dockPinned: ConfigService.dockPinned, dockHideDelay: ConfigService.dockHideDelay,
            dockRevealDelay: ConfigService.dockRevealDelay,
            matchesApplied: ConfigService.layoutPresetMatches(root.presetId)
        };
    }

    function log(marker, obj) {
        console.log(marker + ":" + JSON.stringify(obj));
    }

    Timer {
        interval: 200; running: true; repeat: true
        onTriggered: {
            if (root.phase === "apply" || root.phase === "race") {
                if (root.applied) return;
                if (root.phase === "apply") {
                    // Wait until the seeded user config has been loaded
                    // (seeded bar edge "left" + dock edge "right").
                    if (ConfigService.barEdge !== "left" || ConfigService.dockEdge !== "right") {
                        if (++root.tries < 60) return;
                        root.log("PRESET-FAIL", {step: "seed-load-timeout", snap: root.snapshot()});
                        root.applied = true; // terminal: never fall through
                        Qt.exit(1);
                        return;
                    }
                }
                const res = ConfigService.applyLayoutPreset(root.presetId);
                root.applied = true;
                root.log("PRESET-APPLY", {
                    ok: res.ok, reason: res.reason, alreadyActive: res.alreadyActive,
                    changeCount: res.changes.length, phase: root.phase,
                    snap: root.snapshot()});
                // Give the async JSON writes time to flush before exiting.
                exitTimer.start();
            } else {
                if (root.verified) return;
                if (ConfigService.barEdge !== "top" || ConfigService.dockIconSize !== 36) {
                    if (++root.tries < 60) return;
                    root.log("PRESET-FAIL", {step: "verify-load-timeout", snap: root.snapshot()});
                    root.verified = true; // terminal: never fall through
                    Qt.exit(1);
                    return;
                }
                root.verified = true;
                root.log("PRESET-VERIFY", {snap: root.snapshot()});
                Qt.exit(0);
            }
        }
    }

    Timer {
        id: exitTimer
        interval: 2500
        onTriggered: {
            // Final in-memory state after the config load/save cycle has
            // settled (matters for the race phase, where the store load is
            // still in flight when the preset is applied).
            root.log("PRESET-FINAL", {phase: root.phase, snap: root.snapshot()});
            Qt.exit(0);
        }
    }

    Timer {
        interval: 20000; running: true; repeat: false
        onTriggered: { root.log("PRESET-FAIL", {step: "global-timeout"}); Qt.exit(1); }
    }
}
"""


class TestPresetRuntimeE2E(unittest.TestCase):
    """Isolated quickshell runtime: apply -> persist -> restart -> reload."""

    @classmethod
    def setUpClass(cls):
        if shutil.which("quickshell") is None or shutil.which("dbus-run-session") is None:
            raise unittest.SkipTest("quickshell or dbus-run-session not available")
        cls.testroot = tempfile.mkdtemp(prefix="qs-presets-e2e-")
        cls.probe = os.path.join(REPO, "_test_layout_presets_probe.qml")
        with open(cls.probe, "w") as f:
            f.write(PROBE_QML)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.probe):
            os.remove(cls.probe)
        if hasattr(cls, "testroot"):
            shutil.rmtree(cls.testroot, ignore_errors=True)

    def _run_phase(self, phase, config_home):
        env = dict(os.environ)
        env.pop("WAYLAND_DISPLAY", None)
        env.pop("DISPLAY", None)
        # Fresh runtime dir per phase: quickshell keeps per-instance IPC and
        # log state under XDG_RUNTIME_DIR, and the phases must not influence
        # each other through it.
        runtime_dir = os.path.join(self.testroot, "runtime-" + phase)
        env.update({
            "QT_QPA_PLATFORM": "offscreen",
            "XDG_RUNTIME_DIR": runtime_dir,
            "XDG_CONFIG_HOME": config_home,
            "LAYOUT_PRESET_PHASE": phase,
            "LAYOUT_PRESET_ID": "minimal",
        })
        os.makedirs(runtime_dir, mode=0o700, exist_ok=True)
        proc = subprocess.run(
            ["dbus-run-session", "--", "quickshell", "-p", self.probe, "--no-duplicate"],
            cwd=REPO, env=env, capture_output=True, text=True, timeout=90)
        combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
        return proc.returncode, combined

    def _dump_files(self, config_home):
        """Config file state for failure messages."""
        out = {}
        for name in ("bar_config.json", "dock_config.json"):
            path = os.path.join(config_home, "quickshell-kde", name)
            try:
                with open(path) as f:
                    out[name] = json.load(f)
            except Exception as e:  # noqa: BLE001 - diagnostics only
                out[name] = f"<unreadable: {e}>"
        return out

    def _seed(self, config_home):
        cfgdir = os.path.join(config_home, "quickshell-kde")
        os.makedirs(cfgdir, exist_ok=True)
        with open(os.path.join(cfgdir, "bar_config.json"), "w") as f:
            json.dump(SEED_BAR, f)
        with open(os.path.join(cfgdir, "dock_config.json"), "w") as f:
            json.dump(SEED_DOCK, f)

    def _marker(self, combined, marker):
        lines = [ln for ln in combined.splitlines() if marker in ln]
        self.assertTrue(lines, f"missing {marker} in output:\n{combined}")
        raw = lines[-1].split(marker, 1)[1].strip().lstrip(":").strip()
        return json.loads(raw)

    def _assert_preset_state(self, snap):
        for key, value in MINIMAL_BAR.items():
            if key in ("left", "center", "right"):
                self.assertEqual(snap["bar" + key.capitalize()], value, key)
            elif key == "enabled":
                self.assertTrue(snap["barEnabled"])
            elif key == "edge":
                self.assertEqual(snap["barEdge"], value)
            elif key == "floating":
                self.assertTrue(snap["barFloating"])
            elif key == "edgeOffset":
                self.assertEqual(snap["barEdgeOffset"], value)
            elif key == "reserveSpace":
                self.assertFalse(snap["barReserveSpace"])
            elif key == "height":
                self.assertEqual(snap["barHeight"], value)
        self.assertEqual(snap["dockEdge"], MINIMAL_DOCK["edge"])
        self.assertEqual(snap["dockEdgeOffset"], MINIMAL_DOCK["edgeOffset"])
        self.assertEqual(snap["dockIconSize"], MINIMAL_DOCK["iconSize"])
        self.assertTrue(snap["dockFloating"])
        self.assertFalse(snap["dockReserveSpace"])
        self.assertTrue(snap["dockAutoHide"])
        self.assertFalse(snap["dockIntellihide"])
        self.assertTrue(snap["matchesApplied"])

    def _assert_preserved_state(self, snap):
        self.assertEqual(snap["barOpacity"], 0.55)
        self.assertEqual(snap["barMonitors"], ["DP-1"])
        self.assertFalse(snap["blurEnabled"])
        self.assertTrue(snap["notificationsEnabled"])
        self.assertEqual(snap["trayItemPolicies"], {"org.example.App": "always"})
        self.assertEqual(snap["dockMonitors"], ["DP-1"])
        self.assertEqual(snap["dockWindowFilter"], "desktop")
        self.assertEqual(snap["dockPinned"], ["org.kde.dolphin", "firefox"])
        self.assertEqual(snap["dockHideDelay"], 500)
        self.assertEqual(snap["dockRevealDelay"], 80)

    def _assert_persisted_files(self, config_home):
        with open(os.path.join(config_home, "quickshell-kde", "bar_config.json")) as f:
            bar = json.load(f)
        with open(os.path.join(config_home, "quickshell-kde", "dock_config.json")) as f:
            dock = json.load(f)
        for key, value in MINIMAL_BAR.items():
            self.assertEqual(bar[key], value, f"bar_config.{key}")
        for key, value in MINIMAL_DOCK.items():
            self.assertEqual(dock[key], value, f"dock_config.{key}")
        # Preserved user preferences survive verbatim.
        self.assertEqual(bar["opacity"], 0.55)
        self.assertEqual(bar["monitors"], ["DP-1"])
        self.assertFalse(bar["blur"])
        self.assertTrue(bar["notificationsEnabled"])
        self.assertEqual(bar["trayItemPolicies"], {"org.example.App": "always"})
        self.assertEqual(dock["pinned"], ["org.kde.dolphin", "firefox"])
        self.assertEqual(dock["windowFilter"], "desktop")
        self.assertEqual(dock["monitors"], ["DP-1"])
        self.assertEqual(dock["hideDelay"], 500)
        self.assertEqual(dock["revealDelay"], 80)
        self.assertEqual(bar["controlCenterMigrated"], True)

    def test_apply_persist_restart_reload(self):
        config_home = os.path.join(self.testroot, "config-main")
        os.makedirs(config_home, exist_ok=True)
        self._seed(config_home)

        # Phase 1: apply after the seeded config has loaded.
        code, out = self._run_phase("apply", config_home)
        self.assertEqual(code, 0, out + "\nFILES:" + json.dumps(self._dump_files(config_home)))
        data = self._marker(out, "PRESET-APPLY")
        self.assertTrue(data["ok"], data)
        self.assertFalse(data["alreadyActive"])
        self.assertGreater(data["changeCount"], 0)
        self._assert_preset_state(data["snap"])
        self._assert_preserved_state(data["snap"])
        self._assert_persisted_files(config_home)

        # Phase 2: fresh process, same config home — the preset layout must
        # survive the restart, together with the preserved preferences.
        code, out = self._run_phase("verify", config_home)
        self.assertEqual(code, 0, out + "\nFILES:" + json.dumps(self._dump_files(config_home)))
        data = self._marker(out, "PRESET-VERIFY")
        self._assert_preset_state(data["snap"])
        self._assert_preserved_state(data["snap"])

    def test_apply_before_config_load_race(self):
        """Preset applied during startup must win over the on-disk config load."""
        config_home = os.path.join(self.testroot, "config-race")
        os.makedirs(config_home, exist_ok=True)
        self._seed(config_home)

        code, out = self._run_phase("race", config_home)
        self.assertEqual(code, 0, out + "\nFILES:" + json.dumps(self._dump_files(config_home)))
        data = self._marker(out, "PRESET-APPLY")
        self.assertTrue(data["ok"], data)
        self.assertFalse(data["alreadyActive"])
        self._assert_preset_state(data["snap"])
        # Preserved keys may still be defaults at apply time in this phase
        # (the store load is still in flight); assert them on the final
        # state, after load + deferred save have settled.
        final = self._marker(out, "PRESET-FINAL")
        self._assert_preset_state(final["snap"])
        self._assert_preserved_state(final["snap"])
        self._assert_persisted_files(config_home)

        # The restart must still land on the preset, not the seeded layout.
        code, out = self._run_phase("verify", config_home)
        self.assertEqual(code, 0, out + "\nFILES:" + json.dumps(self._dump_files(config_home)))
        data = self._marker(out, "PRESET-VERIFY")
        self._assert_preset_state(data["snap"])
        self._assert_preserved_state(data["snap"])


if __name__ == "__main__":
    unittest.main()
