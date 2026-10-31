#!/usr/bin/env python3
"""
DOCK-012 per-monitor independent Dock profile tests.

SAFE: pure MonitorProfiles.js helpers executed under node (vm), hotplug
resolution over simulated screen lists, static wiring contracts for the QML
integration (ConfigService load/save/mutations, Dock per-screen resolution,
DockItem popup wiring, WindowService intellihide gate, Settings UI), qmllint
of the touched files, and an isolated headless runtime E2E (private XDG
dirs + private D-Bus session, offscreen quickshell) covering: seeded config
load with sanitization (invalid overrides/names dropped, numeric clamping),
the mutation API (set/clear key, clear profile, invalid rejections, the
intellihide window-tracking gate), reactive binding updates, persistence on
disk and a fresh-process reload. The live Plasma session is never touched.

Run with: python3 -m unittest tests.test_dock_monitor_profiles
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MONITOR_PROFILES_JS = os.path.join(REPO, "services/config/MonitorProfiles.js")
CONFIG_SERVICE = os.path.join(REPO, "services/config/ConfigService.qml")
DOCK_QML = os.path.join(REPO, "modules/dock/Dock.qml")
DOCK_ITEM_QML = os.path.join(REPO, "modules/dock/DockItem.qml")
WINDOW_SERVICE = os.path.join(REPO, "services/kwin/WindowService.qml")
SETTINGS_WINDOW = os.path.join(REPO, "modules/settings/SettingsWindow.qml")
DEFAULT_DOCK_CONFIG = os.path.join(REPO, "config/dock_config.json")


def read(path):
    with open(path) as f:
        return f.read()


DRIVER = (
    "const vm=require('vm'),fs=require('fs');\n"
    "const ctx={};vm.createContext(ctx);vm.runInContext("
    "fs.readFileSync(process.argv[1],'utf8').replace(/^\\.pragma.*$/m,''),ctx);\n"
    "const M=ctx;\n"
    "const input=JSON.parse(process.argv[2]);\n"
    "const out={};\n"
    "if(input.op==='values'){"
    "out.values=input.cases.map(c=>M.sanitizeValue(c.key,c.value));}\n"
    "else if(input.op==='sanitize'){"
    "out.profiles=M.sanitizeProfiles(input.raw);"
    "out.count=Object.keys(out.profiles).length;}\n"
    "else if(input.op==='get'){"
    "out.gets=input.names.map(n=>M.getProfile(input.profiles,n));}\n"
    "else if(input.op==='effective'){"
    "out.eff=M.effectiveProfile(input.profiles,input.screen,input.globals);"
    "out.effUnknown=M.effectiveProfile(input.profiles,'zz-no-such',input.globals);}\n"
    "else if(input.op==='resolve'){"
    "out.val=M.resolveKey(input.profiles,input.screen,input.key,input.global);}\n"
    "else if(input.op==='set'){"
    "const before=JSON.stringify(input.profiles);"
    "const next=M.setOverride(input.profiles,input.screen,input.key,input.value);"
    "out.next=next;"
    "out.inputUnchanged=JSON.stringify(input.profiles)===before;"
    "out.contentNoop=JSON.stringify(next)===before;}\n"
    "else if(input.op==='clearKey'){"
    "const before=JSON.stringify(input.profiles);"
    "const next=M.clearOverride(input.profiles,input.screen,input.key);"
    "out.next=next;out.inputUnchanged=JSON.stringify(input.profiles)===before;}\n"
    "else if(input.op==='clearProfile'){"
    "const next=M.clearProfile(input.profiles,input.screen);"
    "out.next=next;"
    "out.inputUnchanged=JSON.stringify(input.profiles)===JSON.stringify(input.rawBefore);}\n"
    "else if(input.op==='any'){"
    "out.hit=M.anyProfileKey(input.profiles,input.key,input.value);}\n"
    "else if(input.op==='hotplug'){"
    "const profiles={'DP-1':{edge:'left'},'HDMI-A-0':{autoHide:true}};"
    "const globals={edge:'bottom',floating:true,edgeOffset:8,iconSize:44,"
    "autoHide:false,intellihide:false};"
    "out.rounds=input.rounds.map(function(names){"
    "const m={screens:names};"
    "for(let i=0;i<names.length;i++){"
    "const eff=M.effectiveProfile(profiles,names[i],globals);"
    "m[names[i]]={edge:eff.edge,autoHide:eff.autoHide};}"
    "return m;});}\n"
    "console.log(JSON.stringify(out));\n"
)


def run_node(payload):
    p = subprocess.run(["node", "-e", DRIVER, MONITOR_PROFILES_JS,
                        json.dumps(payload)],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


SEED_PROFILES = {
    # Valid overrides; iconSize/edgeOffset outside the global clamp range.
    "DP-1": {"edge": "left", "iconSize": 999, "edgeOffset": -5, "junk": 1},
    # Valid override plus invalid ones (dropped key-by-key).
    "HDMI-A-0": {"autoHide": True, "floating": "bogus"},
    # Invalid screen name -> whole entry dropped.
    "BAD NAME!": {"edge": "top"},
    # All override values invalid -> profile dropped entirely.
    "DP-2": {"edge": "diagonal"},
    # Empty override set -> dropped.
    "eDP-1": {},
}

GLOBALS = {"edge": "bottom", "floating": True, "edgeOffset": 8,
           "iconSize": 44, "autoHide": False, "intellihide": False}


class TestMonitorProfilesPure(unittest.TestCase):
    """Pure MonitorProfiles.js helpers under node (no QML/KWin)."""

    def test_sanitize_value(self):
        r = run_node({"op": "values", "cases": [
            {"key": "edge", "value": "left"},
            {"key": "edge", "value": " Left "},
            {"key": "edge", "value": "diagonal"},
            {"key": "edge", "value": 5},
            {"key": "floating", "value": False},
            {"key": "floating", "value": "true"},
            {"key": "autoHide", "value": 1},
            {"key": "intellihide", "value": True},
            {"key": "edgeOffset", "value": 12},
            {"key": "edgeOffset", "value": -5},
            {"key": "edgeOffset", "value": 999},
            {"key": "edgeOffset", "value": 3.7},
            {"key": "iconSize", "value": 32},
            {"key": "iconSize", "value": 10},
            {"key": "iconSize", "value": 500},
            {"key": "junk", "value": 1},
            {"key": "pinned", "value": ["firefox"]},
            {"key": "monitors", "value": "all"},
        ]})
        self.assertEqual(r["values"], [
            "left", "left", None, None,
            False, None, None, True,
            12, 0, 64, 3,
            32, 20, 128,
            None, None, None,
        ])

    def test_sanitize_profiles(self):
        r = run_node({"op": "sanitize", "raw": SEED_PROFILES})
        self.assertEqual(r["count"], 2)
        self.assertEqual(r["profiles"], {
            "DP-1": {"edge": "left", "iconSize": 128, "edgeOffset": 0},
            "HDMI-A-0": {"autoHide": True},
        })

    def test_sanitize_profiles_rejects_non_objects(self):
        for raw in [None, 5, "x", [], [1, 2]]:
            r = run_node({"op": "sanitize", "raw": raw})
            self.assertEqual(r["profiles"], {})

    def test_sanitize_profiles_caps_count(self):
        raw = {("scr%02d" % i): {"iconSize": 32} for i in range(20)}
        r = run_node({"op": "sanitize", "raw": raw})
        self.assertEqual(r["count"], 16)

    def test_get_profile(self):
        r = run_node({"op": "get", "profiles": {"DP-1": {"edge": "left"}},
                      "names": ["DP-1", "HDMI-A-0", "", "BAD NAME!", 5]})
        self.assertEqual(r["gets"][0], {"edge": "left"})
        self.assertIsNone(r["gets"][1])
        self.assertIsNone(r["gets"][2])
        self.assertIsNone(r["gets"][3])
        self.assertIsNone(r["gets"][4])

    def test_effective_profile_merges_over_globals(self):
        r = run_node({"op": "effective",
                      "profiles": {"DP-1": {"edge": "left", "iconSize": 128,
                                            "edgeOffset": 0}},
                      "screen": "DP-1", "globals": GLOBALS})
        # Overridden keys win; the rest falls back to the globals.
        self.assertEqual(r["eff"], {"edge": "left", "floating": True,
                                    "edgeOffset": 0, "iconSize": 128,
                                    "autoHide": False, "intellihide": False})
        # Unknown screen: pure globals.
        self.assertEqual(r["effUnknown"], GLOBALS)

    def test_resolve_key_invalid_override_falls_back(self):
        # A defensively-unsanitized profile (as if mutated in place) still
        # resolves safely: invalid values fall back to the global.
        r = run_node({"op": "resolve",
                      "profiles": {"DP-1": {"edge": "diagonal", "iconSize": "big"}},
                      "screen": "DP-1", "key": "edge", "global": "bottom"})
        self.assertEqual(r["val"], "bottom")

    def test_set_override_pure_and_valid(self):
        profiles = {"DP-1": {"edge": "left"}}
        r = run_node({"op": "set", "profiles": profiles, "screen": "DP-1",
                      "key": "iconSize", "value": 999})
        self.assertTrue(r["inputUnchanged"])
        self.assertEqual(r["next"], {"DP-1": {"edge": "left", "iconSize": 128}})

    def test_set_override_new_screen_and_invalid(self):
        r = run_node({"op": "set", "profiles": {"DP-1": {"edge": "left"}},
                      "screen": "HDMI-A-0", "key": "autoHide", "value": True})
        self.assertEqual(r["next"], {"DP-1": {"edge": "left"},
                                     "HDMI-A-0": {"autoHide": True}})
        # Invalid value / key / screen name: content unchanged (a safe copy).
        for screen, key, value in [("DP-1", "edge", "diagonal"),
                                   ("DP-1", "junk", 5),
                                   ("BAD NAME!", "edge", "top")]:
            r = run_node({"op": "set", "profiles": {"DP-1": {"edge": "left"}},
                          "screen": screen, "key": key, "value": value})
            self.assertTrue(r["contentNoop"], (screen, key, value))
            self.assertTrue(r["inputUnchanged"])

    def test_set_override_respects_profile_cap(self):
        profiles = {("scr%02d" % i): {"iconSize": 32} for i in range(16)}
        r = run_node({"op": "set", "profiles": profiles, "screen": "scr-new",
                      "key": "iconSize", "value": 40})
        self.assertTrue(r["contentNoop"])
        # Extending an EXISTING profile at the cap is still allowed.
        r = run_node({"op": "set", "profiles": profiles, "screen": "scr00",
                      "key": "autoHide", "value": True})
        self.assertEqual(r["next"]["scr00"], {"iconSize": 32, "autoHide": True})

    def test_clear_override_drops_empty_profile(self):
        r = run_node({"op": "clearKey", "profiles": {"DP-1": {"edge": "left"}},
                      "screen": "DP-1", "key": "edge"})
        self.assertTrue(r["inputUnchanged"])
        self.assertEqual(r["next"], {})
        r = run_node({"op": "clearKey",
                      "profiles": {"DP-1": {"edge": "left", "iconSize": 64}},
                      "screen": "DP-1", "key": "edge"})
        self.assertEqual(r["next"], {"DP-1": {"iconSize": 64}})
        # Clearing a key the screen does not override: no-op copy.
        r = run_node({"op": "clearKey", "profiles": {"DP-1": {"edge": "left"}},
                      "screen": "HDMI-A-0", "key": "edge"})
        self.assertEqual(r["next"], {"DP-1": {"edge": "left"}})

    def test_clear_profile(self):
        r = run_node({"op": "clearProfile",
                      "rawBefore": {"DP-1": {"edge": "left"},
                                    "HDMI-A-0": {"autoHide": True}},
                      "profiles": {"DP-1": {"edge": "left"},
                                   "HDMI-A-0": {"autoHide": True}},
                      "screen": "DP-1"})
        self.assertTrue(r["inputUnchanged"])
        self.assertEqual(r["next"], {"HDMI-A-0": {"autoHide": True}})
        r = run_node({"op": "clearProfile",
                      "rawBefore": {"DP-1": {"edge": "left"}},
                      "profiles": {"DP-1": {"edge": "left"}},
                      "screen": "ghost"})
        self.assertEqual(r["next"], {"DP-1": {"edge": "left"}})

    def test_any_profile_key(self):
        profiles = {"DP-1": {"intellihide": True}, "HDMI-A-0": {"edge": "left"}}
        r = run_node({"op": "any", "profiles": profiles,
                      "key": "intellihide", "value": True})
        self.assertTrue(r["hit"])
        r = run_node({"op": "any", "profiles": profiles,
                      "key": "intellihide", "value": False})
        self.assertFalse(r["hit"])
        r = run_node({"op": "any", "profiles": {}, "key": "intellihide",
                      "value": True})
        self.assertFalse(r["hit"])

    def test_hotplug_resolution_over_simulated_screen_lists(self):
        """Profile resolution follows screen add/remove without restart.

        Pure resolution over simulated Quickshell.screens lists: removing an
        output simply stops resolving its profile; adding an output without
        a profile resolves pure globals; re-adding an output picks its
        stored override back up (profiles survive hotplug by design).
        """
        r = run_node({"op": "hotplug", "rounds": [
            ["DP-1", "HDMI-A-0"],
            ["DP-1"],
            ["DP-1", "DP-2"],
            ["DP-1", "HDMI-A-0"],
        ]})
        rounds = r["rounds"]
        self.assertEqual(rounds[0]["screens"], ["DP-1", "HDMI-A-0"])
        self.assertEqual(rounds[0]["DP-1"], {"edge": "left", "autoHide": False})
        self.assertEqual(rounds[0]["HDMI-A-0"], {"edge": "bottom", "autoHide": True})
        # HDMI-A-0 removed: no resolution for it; DP-1 unaffected.
        self.assertEqual(rounds[1]["screens"], ["DP-1"])
        self.assertEqual(rounds[1]["DP-1"], {"edge": "left", "autoHide": False})
        # DP-2 connected: no stored profile -> pure globals.
        self.assertEqual(rounds[2]["DP-2"], {"edge": "bottom", "autoHide": False})
        self.assertEqual(rounds[2]["DP-1"], {"edge": "left", "autoHide": False})
        # HDMI-A-0 re-connected: its stored override applies again.
        self.assertEqual(rounds[3]["HDMI-A-0"], {"edge": "bottom", "autoHide": True})


class TestStaticContracts(unittest.TestCase):
    """Source contracts for the QML integration (no runtime)."""

    def test_config_service_profile_api(self):
        src = read(CONFIG_SERVICE)
        self.assertIn('import "MonitorProfiles.js" as MonitorProfiles', src)
        self.assertIn("property var dockMonitorProfiles: ({})", src)
        for fn in ("function getDockMonitorProfile(",
                   "function hasDockMonitorProfile(",
                   "function effectiveDockProfile(",
                   "function setDockMonitorProfileKey(",
                   "function clearDockMonitorProfileKey(",
                   "function clearDockMonitorProfile("):
            self.assertIn(fn, src, fn)
        # Load: profiles are sanitized (invalid entries dropped) through the
        # modified-before-load protocol like every other dock key.
        self.assertIn('if (parsed.monitorProfiles !== undefined && !mod["monitorProfiles"]) {', src)
        self.assertIn("root.dockMonitorProfiles = MonitorProfiles.sanitizeProfiles(parsed.monitorProfiles);", src)
        # Save: profiles are persisted.
        self.assertIn('"monitorProfiles": root.dockMonitorProfiles || {}', src)
        # Mutations mark the key and reassign the whole object
        # (QVariant-signal gotcha) before saving.
        self.assertEqual(src.count('root._markDockModified("monitorProfiles");'), 3)
        self.assertEqual(src.count("root.dockMonitorProfiles = MonitorProfiles."), 4)
        # Window tracking gate for per-monitor intellihide.
        self.assertIn("readonly property bool anyDockIntellihide:", src)
        self.assertIn('MonitorProfiles.anyProfileKey(root.dockMonitorProfiles, "intellihide", true)', src)

    def test_dock_resolves_per_screen(self):
        src = read(DOCK_QML)
        # Each Variants delegate resolves the effective profile for ITS
        # screen; the Variants model re-evaluates on hotplug.
        self.assertIn("readonly property var monitorProfile: ConfigService.effectiveDockProfile(modelData ? modelData.name : \"\")", src)
        for prop in ("monitorProfile.edge", "monitorProfile.floating",
                     "monitorProfile.edgeOffset", "monitorProfile.iconSize",
                     "monitorProfile.autoHide", "monitorProfile.intellihide"):
            self.assertIn(prop, src, prop)
        # The per-monitor keys must no longer be read globally in Dock.qml.
        for banned in ("ConfigService.dockEdge", "ConfigService.dockFloating",
                       "ConfigService.dockEdgeOffset", "ConfigService.dockIconSize",
                       "ConfigService.dockAutoHide", "ConfigService.dockIntellihide"):
            self.assertNotIn(banned, src, banned)

    def test_dock_item_follows_owning_surface(self):
        src = read(DOCK_ITEM_QML)
        # Icon size and popup edges follow the owning dock surface's
        # per-monitor profile; bare items fall back to the global settings.
        self.assertIn("root.parentWindowRef.iconSize : ConfigService.dockIconSize", src)
        self.assertIn("readonly property string dockEdge:", src)
        self.assertEqual(src.count("edge: root.dockEdge"), 5)

    def test_window_service_intellihide_gate(self):
        src = read(WINDOW_SERVICE)
        self.assertIn("ConfigService.anyDockIntellihide", src)
        self.assertNotIn("ConfigService.dockIntellihide", src)

    def test_settings_ui_profile_management(self):
        src = read(SETTINGS_WINDOW)
        self.assertIn("Per-Monitor Dock Profiles", src)
        for frag in ("ConfigService.setDockMonitorProfileKey(",
                     "ConfigService.clearDockMonitorProfileKey(",
                     "ConfigService.clearDockMonitorProfile(",
                     "ConfigService.getDockMonitorProfile(",
                     "ConfigService.effectiveDockProfile("):
            self.assertIn(frag, src, frag)
        # The editor lists the live screen model (hotplug-aware).
        self.assertIn("model: Quickshell.screens", src)

    def test_pinned_stays_global(self):
        """Per-monitor profiles must not fork the pinned/stack model."""
        for path in (DOCK_QML, DOCK_ITEM_QML):
            src = read(path)
            self.assertNotIn("monitorProfile.pinned", src)
        # Meta shortcuts still address the single global pinned list.
        meta = read(os.path.join(REPO, "services/kwin/MetaShortcuts.js"))
        self.assertIn("dockPinned", meta)

    def test_first_launch_defaults_untouched(self):
        dock = json.loads(read(DEFAULT_DOCK_CONFIG))
        self.assertNotIn("monitorProfiles", dock)
        self.assertEqual(dock["pinned"],
                         ["org.kde.dolphin", "org.kde.konsole", "firefox",
                          "code", "systemsettings"])
        self.assertEqual(dock["iconSize"], 44)
        self.assertEqual(dock["edge"], "bottom")

    def test_qml_lint(self):
        res = subprocess.run(
            ["qmllint", "modules/dock/Dock.qml",
             "modules/dock/DockItem.qml",
             "services/config/ConfigService.qml",
             "services/kwin/WindowService.qml",
             "modules/settings/SettingsWindow.qml"],
            cwd=REPO, capture_output=True, text=True)
        warnings = [ln for ln in (res.stdout + res.stderr).splitlines()
                    if "arning" in ln or "rror" in ln]
        self.assertEqual(warnings, [], "qmllint reported issues: " + "\n".join(warnings))


# ---------------------------------------------------------------------------
# Isolated headless runtime E2E (offscreen quickshell + private XDG dirs +
# private D-Bus session). ConfigService-level only: no KWin rig, no app
# scanning, no live session access.
# ---------------------------------------------------------------------------

PROBE_QML = """import QtQuick
import Quickshell
import "./services"

Scope {
    id: root
    // Phases: "load" (seeded config must sanitize in), "mutate" (exercise
    // the profile mutation API + reactive binding), "verify" (fresh
    // process: reload persisted).
    property string phase: Quickshell.env("PROFILES_PHASE") || "load"
    property int tries: 0
    property bool done: false
    // Reactive consumer: proves effectiveDockProfile() bindings update
    // when dockMonitorProfiles is reassigned (real QML reactivity chain).
    property int reactiveIconSize: ConfigService.effectiveDockProfile("DP-1").iconSize

    function snap() {
        return {
            profiles: ConfigService.dockMonitorProfiles,
            effDp1: ConfigService.effectiveDockProfile("DP-1"),
            effUnknown: ConfigService.effectiveDockProfile("zz-no-such"),
            getHdmi: ConfigService.getDockMonitorProfile("HDMI-A-0"),
            hasDp1: ConfigService.hasDockMonitorProfile("DP-1"),
            pinned: ConfigService.dockPinned,
            globalIconSize: ConfigService.dockIconSize
        };
    }

    function log(marker, obj) {
        console.log(marker + ":" + JSON.stringify(obj));
    }

    Timer {
        interval: 200; running: true; repeat: true
        onTriggered: {
            if (root.done) return;
            if (root.phase === "load" || root.phase === "mutate") {
                // Wait until the seeded config has been loaded (seeded
                // profile for DP-1 must be present).
                if (!ConfigService.hasDockMonitorProfile("DP-1")) {
                    if (++root.tries < 60) return;
                    root.log("PROFILES-FAIL", {step: "seed-load-timeout", snap: root.snap()});
                    root.done = true; // terminal: never fall through
                    Qt.exit(1);
                    return;
                }
                if (root.phase === "load") {
                    root.log("PROFILES-LOAD", root.snap());
                    root.done = true;
                    exitTimer.start();
                    return;
                }
                // --- mutation phase ---
                const res = {};
                const screens = Quickshell.screens || [];
                res.screenCount = screens.length;
                // Live output name when the platform exposes one; the
                // offscreen platform reports an UNNAMED screen, which must
                // resolve to pure globals (empty name -> no profile).
                res.liveName = screens.length > 0 ? (screens[0].name || "") : "";
                res.effLive = screens.length > 0
                    ? ConfigService.effectiveDockProfile(screens[0].name)
                    : null;
                let target = "";
                for (let i = 0; i < screens.length; i++) {
                    if (screens[i].name && screens[i].name.length > 0) {
                        target = screens[i].name;
                        break;
                    }
                }
                if (!target) target = "OFFSCREEN-1";
                res.real = target;
                res.usedLiveScreenName = target !== "OFFSCREEN-1";
                res.reactiveInitial = root.reactiveIconSize;
                res.setEdge = ConfigService.setDockMonitorProfileKey(res.real, "edge", "left");
                res.effEdgeLeft = ConfigService.effectiveDockProfile(res.real).edge === "left";
                res.setBadEdge = ConfigService.setDockMonitorProfileKey(res.real, "edge", "diagonal");
                res.setJunkKey = ConfigService.setDockMonitorProfileKey(res.real, "junk", 5);
                res.setBadName = ConfigService.setDockMonitorProfileKey("BAD NAME!", "edge", "top");
                res.setBigIcon = ConfigService.setDockMonitorProfileKey(res.real, "iconSize", 999);
                res.setNegOffset = ConfigService.setDockMonitorProfileKey(res.real, "edgeOffset", -7);
                res.setIconDp1 = ConfigService.setDockMonitorProfileKey("DP-1", "iconSize", 64);
                res.reactiveAfter = root.reactiveIconSize;
                res.anyIhBefore = ConfigService.anyDockIntellihide;
                res.setIntellihide = ConfigService.setDockMonitorProfileKey(res.real, "intellihide", true);
                res.anyIhDuring = ConfigService.anyDockIntellihide;
                res.clearIntellihide = ConfigService.clearDockMonitorProfileKey(res.real, "intellihide");
                res.anyIhAfter = ConfigService.anyDockIntellihide;
                res.clearEdge = ConfigService.clearDockMonitorProfileKey(res.real, "edge");
                res.effEdgeGlobal = ConfigService.effectiveDockProfile(res.real).edge === ConfigService.dockEdge;
                res.setEdgeAgain = ConfigService.setDockMonitorProfileKey(res.real, "edge", "left");
                res.clearHdmi = ConfigService.clearDockMonitorProfile("HDMI-A-0");
                res.clearGhost = ConfigService.clearDockMonitorProfile("ghost");
                res.after = root.snap();
                res.effReal = ConfigService.effectiveDockProfile(res.real);
                root.log("PROFILES-MUTATE", res);
                root.done = true;
                exitTimer.start();
            } else {
                // verify: fresh process, persisted state must reload.
                if (!ConfigService.hasDockMonitorProfile("DP-1")
                    || ConfigService.getDockMonitorProfile("DP-1").iconSize !== 64) {
                    if (++root.tries < 60) return;
                    root.log("PROFILES-FAIL", {step: "verify-load-timeout", snap: root.snap()});
                    root.done = true;
                    Qt.exit(1);
                    return;
                }
                root.log("PROFILES-VERIFY", root.snap());
                root.done = true;
                Qt.exit(0);
            }
        }
    }

    Timer {
        id: exitTimer
        interval: 2500
        onTriggered: {
            root.log("PROFILES-FINAL", {phase: root.phase, snap: root.snap()});
            Qt.exit(0);
        }
    }

    Timer {
        interval: 30000; running: true; repeat: false
        onTriggered: { root.log("PROFILES-FAIL", {step: "global-timeout"}); Qt.exit(1); }
    }
}
"""

SEED_DOCK = {
    "enabled": True, "floating": False, "edge": "bottom", "edgeOffset": 12,
    "iconSize": 48, "monitors": "all", "windowFilter": "all",
    "pinned": ["org.kde.dolphin", "firefox"],
    "monitorProfiles": SEED_PROFILES,
}


class TestMonitorProfilesRuntimeE2E(unittest.TestCase):
    """Isolated quickshell runtime: load -> mutate -> persist -> reload."""

    @classmethod
    def setUpClass(cls):
        if shutil.which("quickshell") is None or shutil.which("dbus-run-session") is None:
            raise unittest.SkipTest("quickshell or dbus-run-session not available")
        cls.testroot = tempfile.mkdtemp(prefix="qs-profiles-e2e-")
        cls.probe = os.path.join(REPO, "_test_dock_monitor_profiles_probe.qml")
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
        runtime_dir = os.path.join(self.testroot, "runtime-" + phase)
        env.update({
            "QT_QPA_PLATFORM": "offscreen",
            "XDG_RUNTIME_DIR": runtime_dir,
            "XDG_CONFIG_HOME": config_home,
            "PROFILES_PHASE": phase,
        })
        os.makedirs(runtime_dir, mode=0o700, exist_ok=True)
        proc = subprocess.run(
            ["dbus-run-session", "--", "quickshell", "-p", self.probe, "--no-duplicate"],
            cwd=REPO, env=env, capture_output=True, text=True, timeout=90)
        combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
        return proc.returncode, combined

    def _seed(self, config_home):
        cfgdir = os.path.join(config_home, "quickshell-kde")
        os.makedirs(cfgdir, exist_ok=True)
        with open(os.path.join(cfgdir, "dock_config.json"), "w") as f:
            json.dump(SEED_DOCK, f)

    def _marker(self, combined, marker):
        lines = [ln for ln in combined.splitlines() if marker in ln]
        self.assertTrue(lines, f"missing {marker} in output:\n{combined}")
        raw = lines[-1].split(marker, 1)[1].strip().lstrip(":").strip()
        return json.loads(raw)

    def _persisted(self, config_home):
        with open(os.path.join(config_home, "quickshell-kde", "dock_config.json")) as f:
            return json.load(f)

    def _assert_loaded_state(self, snap):
        # Invalid seed entries dropped; valid overrides sanitized in.
        self.assertEqual(snap["profiles"], {
            "DP-1": {"edge": "left", "iconSize": 128, "edgeOffset": 0},
            "HDMI-A-0": {"autoHide": True},
        })
        self.assertEqual(snap["getHdmi"], {"autoHide": True})
        self.assertTrue(snap["hasDp1"])
        # Effective merge: overrides win, the rest falls back to the seeded
        # globals (edge bottom, floating false, edgeOffset 12, iconSize 48).
        self.assertEqual(snap["effDp1"], {"edge": "left", "floating": False,
                                          "edgeOffset": 0, "iconSize": 128,
                                          "autoHide": False, "intellihide": False})
        self.assertEqual(snap["effUnknown"], {"edge": "bottom", "floating": False,
                                              "edgeOffset": 12, "iconSize": 48,
                                              "autoHide": False, "intellihide": False})
        # Pinned row untouched by per-monitor profiles.
        self.assertEqual(snap["pinned"], ["org.kde.dolphin", "firefox"])
        self.assertEqual(snap["globalIconSize"], 48)

    def test_load_mutate_persist_reload(self):
        config_home = os.path.join(self.testroot, "config-main")
        os.makedirs(config_home, exist_ok=True)
        self._seed(config_home)

        # Phase 1: seeded config loads with sanitization.
        code, out = self._run_phase("load", config_home)
        self.assertEqual(code, 0, out)
        self._assert_loaded_state(self._marker(out, "PROFILES-LOAD"))

        # Phase 2: mutations on a fresh process over the same config.
        code, out = self._run_phase("mutate", config_home)
        self.assertEqual(code, 0, out)
        res = self._marker(out, "PROFILES-MUTATE")
        real = res["real"]
        self.assertTrue(real, res)
        # The offscreen platform exposes exactly one UNNAMED screen: it
        # must resolve to pure globals (no profile for an empty name).
        self.assertEqual(res["screenCount"], 1, res)
        self.assertEqual(res["liveName"], "", res)
        self.assertEqual(res["effLive"], {"edge": "bottom", "floating": False,
                                          "edgeOffset": 12, "iconSize": 48,
                                          "autoHide": False, "intellihide": False}, res)
        self.assertFalse(res["usedLiveScreenName"], res)
        self.assertTrue(res["setEdge"], res)
        self.assertTrue(res["effEdgeLeft"], res)
        self.assertFalse(res["setBadEdge"], res)   # invalid edge value
        self.assertFalse(res["setJunkKey"], res)   # non-overridable key
        self.assertFalse(res["setBadName"], res)   # invalid screen name
        self.assertTrue(res["setBigIcon"], res)    # clamped to 128
        self.assertTrue(res["setNegOffset"], res)  # clamped to 0
        self.assertTrue(res["setIconDp1"], res)
        # Reactive binding: effectiveDockProfile("DP-1").iconSize moved
        # from the seeded 128 to 64 through the property reassignment.
        self.assertEqual(res["reactiveInitial"], 128, res)
        self.assertEqual(res["reactiveAfter"], 64, res)
        # Per-monitor intellihide drives the window-tracking gate.
        self.assertFalse(res["anyIhBefore"], res)
        self.assertTrue(res["setIntellihide"], res)
        self.assertTrue(res["anyIhDuring"], res)
        self.assertTrue(res["clearIntellihide"], res)
        self.assertFalse(res["anyIhAfter"], res)
        # Per-key clear falls back to the global edge.
        self.assertTrue(res["clearEdge"], res)
        self.assertTrue(res["effEdgeGlobal"], res)
        self.assertTrue(res["setEdgeAgain"], res)
        self.assertTrue(res["clearHdmi"], res)
        self.assertFalse(res["clearGhost"], res)
        # Final in-memory state.
        after = res["after"]
        self.assertEqual(after["profiles"], {
            "DP-1": {"edge": "left", "iconSize": 64, "edgeOffset": 0},
            real: {"edge": "left", "iconSize": 128, "edgeOffset": 0},
        })
        self.assertEqual(after["effDp1"]["iconSize"], 64)
        self.assertIsNone(after["getHdmi"])
        self.assertEqual(res["effReal"], {"edge": "left", "floating": False,
                                          "edgeOffset": 0, "iconSize": 128,
                                          "autoHide": False, "intellihide": False})

        # Persisted file on disk matches the final in-memory state; user
        # preferences survive verbatim.
        final = self._marker(out, "PROFILES-FINAL")
        disk = self._persisted(config_home)
        self.assertEqual(disk["monitorProfiles"], final["snap"]["profiles"])
        self.assertEqual(disk["monitorProfiles"], after["profiles"])
        self.assertEqual(disk["iconSize"], 48)
        self.assertEqual(disk["pinned"], ["org.kde.dolphin", "firefox"])

        # Phase 3: fresh process — persisted profiles reload cleanly.
        code, out = self._run_phase("verify", config_home)
        self.assertEqual(code, 0, out)
        snap = self._marker(out, "PROFILES-VERIFY")
        self.assertEqual(snap["profiles"], after["profiles"])
        self.assertEqual(snap["effDp1"], {"edge": "left", "floating": False,
                                          "edgeOffset": 0, "iconSize": 64,
                                          "autoHide": False, "intellihide": False})

    def test_fresh_defaults_have_no_profiles(self):
        """No seeded config: first-launch defaults load with zero profiles."""
        config_home = os.path.join(self.testroot, "config-fresh")
        os.makedirs(config_home, exist_ok=True)
        code, out = self._run_phase("verify", config_home)
        # The verify phase waits for the seeded profile which never comes;
        # use the global snapshot from the failure marker instead.
        self.assertNotEqual(code, 0)
        fail = self._marker(out, "PROFILES-FAIL")
        self.assertEqual(fail["step"], "verify-load-timeout")
        snap = fail["snap"]
        self.assertEqual(snap["profiles"], {})
        self.assertFalse(snap["hasDp1"])
        # Defaults unchanged (backwards compatibility).
        self.assertEqual(snap["globalIconSize"], 44)
        self.assertEqual(snap["pinned"], ["org.kde.dolphin", "org.kde.konsole",
                                          "firefox", "code", "systemsettings"])
        self.assertEqual(snap["effUnknown"], {"edge": "bottom", "floating": True,
                                              "edgeOffset": 8, "iconSize": 44,
                                              "autoHide": False, "intellihide": False})


if __name__ == "__main__":
    unittest.main()
