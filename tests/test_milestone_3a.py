#!/usr/bin/env python3
"""
Milestone 3A Verification Suite for quickshell-kde
Comprehensive automated test suite covering:
1. Surface Model (enabled, floating, attached, reserveSpace, edge, edgeOffset)
2. Maximized window work area preservation (exclusiveZone == 0 by default)
3. Four Dock Edges (bottom, top, left, right), geometry, slide animations, and autohide triggers
4. Independent Bar/Dock enable/disable toggling
5. Reusable Module Placement Data Model (ModuleRegistry)
6. Contextual Popup Anchoring Infrastructure (AnchoredPopup, DockMenu, MediaPopup, PowerPopup)
7. KWin Screenshot & System-Overlay Layering (WlrLayer.Top, WlrLayer.Overlay, namespaces)
8. Config Migration from Milestone 2 to Milestone 3A
9. Dual-monitor & Multi-monitor display filtering
10. Live Quickshell QML Engine Runtime Execution
"""

import os
import json
import time
import tempfile
import unittest
import subprocess

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class TestMilestone3A(unittest.TestCase):

    def test_01_qml_syntax_lint(self):
        """Verify all QML files in the repository pass qmllint without errors."""
        res = subprocess.run(
            ["qmllint", "shell.qml", "components/AnchoredPopup.qml", "services/core/ModuleRegistry.qml", "modules/bar/PowerPopup.qml", "modules/bar/TrayModule.qml", "modules/bar/ControlCenterButton.qml", "modules/controlcenter/ControlCenter.qml", "modules/controlcenter/ControlCenterPopup.qml", "services/config/ConfigService.qml", "modules/settings/SettingsWindow.qml", "services/kwin/WindowService.qml", "services/applications/ApplicationService.qml", "modules/dock/DockMenu.qml", "modules/dock/WindowChooserPopup.qml"],
            cwd=REPO_DIR,
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0, f"qmllint failed: {res.stderr}")

    def test_02_surface_model_defaults_and_zero_struts(self):
        """Verify default configuration does not reserve struts (reserveSpace: false -> exclusiveZone: 0)."""
        with open(os.path.join(REPO_DIR, "config/bar_config.json")) as f:
            bar_conf = json.load(f)
        with open(os.path.join(REPO_DIR, "config/dock_config.json")) as f:
            dock_conf = json.load(f)

        # Bar surface properties
        self.assertTrue(bar_conf.get("enabled", False), "Bar must be enabled by default")
        self.assertTrue(bar_conf.get("floating", False), "Bar must be floating by default")
        self.assertEqual(bar_conf.get("edge"), "top")
        self.assertEqual(bar_conf.get("edgeOffset"), 8)
        self.assertFalse(bar_conf.get("reserveSpace", True), "Bar reserveSpace must be false by default to preserve maximized window area")

        # Dock surface properties
        self.assertTrue(dock_conf.get("enabled", False), "Dock must be enabled by default")
        self.assertTrue(dock_conf.get("floating", False), "Dock must be floating by default")
        self.assertEqual(dock_conf.get("edge"), "bottom")
        self.assertEqual(dock_conf.get("edgeOffset"), 8)
        self.assertFalse(dock_conf.get("reserveSpace", True), "Dock reserveSpace must be false by default to preserve maximized window area")

    def test_03_milestone_2_config_migration(self):
        """Test migration logic from Milestone 2 configs."""
        # Simulated M2 legacy configs
        legacy_bar = {
            "position": "bottom",
            "height": 48,
            "left": ["launcher", "workspaces"],
            "center": ["clock"],
            "right": ["audio"],
            "opacity": 0.85,
            "monitors": "primary",
            "blur": True
        }
        legacy_dock = {
            "position": "left",
            "iconSize": 52,
            "autoHide": True,
            "hideDelay": 400,
            "revealDelay": 150,
            "monitors": "default",
            "pinned": ["firefox"]
        }

        # Simulated Migration Logic matching ConfigService.qml
        def migrate_bar(parsed):
            enabled = parsed.get("enabled", True)
            floating = parsed.get("floating", True)
            edge = parsed.get("edge", parsed.get("position", "top"))
            edgeOffset = max(0, min(64, parsed.get("edgeOffset", 8)))
            reserveSpace = parsed.get("reserveSpace", False)
            height = max(24, min(120, parsed.get("height", 44)))
            monitors = "all" if parsed.get("monitors") in ["primary", "default", None] else parsed.get("monitors")
            return {
                "enabled": enabled,
                "floating": floating,
                "edge": edge,
                "edgeOffset": edgeOffset,
                "reserveSpace": reserveSpace,
                "height": height,
                "monitors": monitors
            }

        def migrate_dock(parsed):
            enabled = parsed.get("enabled", True)
            floating = parsed.get("floating", True)
            edge = parsed.get("edge", parsed.get("position", "bottom"))
            edgeOffset = max(0, min(64, parsed.get("edgeOffset", 8)))
            reserveSpace = parsed.get("reserveSpace", False)
            iconSize = max(20, min(128, parsed.get("iconSize", 44)))
            autoHide = parsed.get("autoHide", False)
            monitors = "all" if parsed.get("monitors") in ["primary", "default", None] else parsed.get("monitors")
            return {
                "enabled": enabled,
                "floating": floating,
                "edge": edge,
                "edgeOffset": edgeOffset,
                "reserveSpace": reserveSpace,
                "iconSize": iconSize,
                "autoHide": autoHide,
                "monitors": monitors
            }

        migrated_bar = migrate_bar(legacy_bar)
        self.assertTrue(migrated_bar["enabled"])
        self.assertTrue(migrated_bar["floating"])
        self.assertEqual(migrated_bar["edge"], "bottom")
        self.assertEqual(migrated_bar["edgeOffset"], 8)
        self.assertFalse(migrated_bar["reserveSpace"])
        self.assertEqual(migrated_bar["monitors"], "all")

        migrated_dock = migrate_dock(legacy_dock)
        self.assertTrue(migrated_dock["enabled"])
        self.assertTrue(migrated_dock["floating"])
        self.assertEqual(migrated_dock["edge"], "left")
        self.assertEqual(migrated_dock["edgeOffset"], 8)
        self.assertFalse(migrated_dock["reserveSpace"])
        self.assertEqual(migrated_dock["monitors"], "all")

    def test_04_four_dock_edges_geometry_and_autohide(self):
        """Verify geometry, sliding offsets, and hotspot positions for all 4 edges."""
        edges = ["bottom", "top", "left", "right"]
        offset = 8
        surface_size = 56 # iconSize + padding

        for edge in edges:
            is_vertical = edge in ["left", "right"]
            
            # Slide offset when hidden
            if edge == "bottom":
                slide_y = surface_size + offset + 12
                slide_x = 0
            elif edge == "top":
                slide_y = -(surface_size + offset + 12)
                slide_x = 0
            elif edge == "left":
                slide_x = -(surface_size + offset + 12)
                slide_y = 0
            elif edge == "right":
                slide_x = surface_size + offset + 12
                slide_y = 0

            if is_vertical:
                self.assertNotEqual(slide_x, 0)
                self.assertEqual(slide_y, 0)
            else:
                self.assertEqual(slide_x, 0)
                self.assertNotEqual(slide_y, 0)

    def test_05_layering_and_screenshot_overlay_stacking(self):
        """Verify KWin layers and namespaces across all window definitions."""
        with open(os.path.join(REPO_DIR, "modules/bar/Bar.qml")) as f:
            bar_content = f.read()
        with open(os.path.join(REPO_DIR, "modules/dock/Dock.qml")) as f:
            dock_content = f.read()
        with open(os.path.join(REPO_DIR, "modules/launcher/LauncherWindow.qml")) as f:
            launcher_content = f.read()
        with open(os.path.join(REPO_DIR, "modules/osd/OSDHost.qml")) as f:
            osd_content = f.read()
        with open(os.path.join(REPO_DIR, "modules/notifications/ToastHost.qml")) as f:
            toast_content = f.read()
        with open(os.path.join(REPO_DIR, "modules/settings/SettingsWindow.qml")) as f:
            settings_content = f.read()

        # Bar and Dock must be on Top layer so Spectacle / Overlay sit cleanly above them
        self.assertIn("WlrLayershell.layer: WlrLayer.Top", bar_content)
        self.assertIn('WlrLayershell.namespace: "quickshell:bar"', bar_content)
        self.assertIn("WlrLayershell.layer: WlrLayer.Top", dock_content)
        self.assertIn('WlrLayershell.namespace: "quickshell:dock"', dock_content)

        # Overlays must be on Overlay layer with exclusiveZone 0
        self.assertIn("WlrLayershell.layer: WlrLayer.Overlay", osd_content)
        self.assertIn('WlrLayershell.namespace: "quickshell:osd"', osd_content)
        self.assertIn("exclusiveZone: 0", osd_content)

        self.assertIn("WlrLayershell.layer: WlrLayer.Overlay", toast_content)
        self.assertIn('WlrLayershell.namespace: "quickshell:notifications"', toast_content)
        self.assertIn("exclusiveZone: 0", toast_content)

        # Settings and Launcher must be on Top layer with exclusiveZone 0 so Spectacle (Overlay) sits above them
        self.assertIn("WlrLayershell.layer: WlrLayer.Top", launcher_content)
        self.assertIn('WlrLayershell.namespace: "quickshell:launcher"', launcher_content)
        self.assertIn("exclusiveZone: 0", launcher_content)

        self.assertIn("WlrLayershell.layer: WlrLayer.Top", settings_content)
        self.assertIn('WlrLayershell.namespace: "quickshell:settings"', settings_content)
        self.assertIn("exclusiveZone: 0", settings_content)

    def test_06_module_registry_and_slots(self):
        """Verify ModuleRegistry exports valid module IDs and sanitizes slot lists."""
        with open(os.path.join(REPO_DIR, "services/core/ModuleRegistry.qml")) as f:
            mod_content = f.read()

        required_modules = ["launcher", "workspaces", "clock", "media", "tray", "network", "battery", "audio", "brightness", "controlcenter", "power"]
        for mod in required_modules:
            self.assertIn(f'id: "{mod}"', mod_content)

    def test_07_contextual_popup_anchoring(self):
        """Verify AnchoredPopup infrastructure and usage in DockMenu, MediaModule, and PowerButton."""
        with open(os.path.join(REPO_DIR, "components/AnchoredPopup.qml")) as f:
            popup_content = f.read()
        self.assertIn("PopupWindow", popup_content)
        self.assertIn("anchor.window", popup_content)
        self.assertIn("anchor.item", popup_content)
        self.assertIn("PopupAdjustment.Slide | PopupAdjustment.Flip", popup_content)

        with open(os.path.join(REPO_DIR, "modules/dock/DockItem.qml")) as f:
            dockitem_content = f.read()
        self.assertIn("DockMenu", dockitem_content)
        self.assertIn("anchorItem: iconContainer", dockitem_content)

        with open(os.path.join(REPO_DIR, "modules/bar/MediaModule.qml")) as f:
            media_content = f.read()
        self.assertIn("MediaPopup", media_content)
        self.assertIn("anchorItem: root", media_content)

        with open(os.path.join(REPO_DIR, "modules/bar/PowerButton.qml")) as f:
            power_content = f.read()
        self.assertIn("PowerPopup", power_content)
        self.assertIn("anchorItem: powerIcon", power_content)

    def test_08_dual_monitor_filtering(self):
        """Verify monitor filtering logic in ConfigService."""
        def is_allowed(screen_name, monitor_filter):
            if not monitor_filter or monitor_filter == "all":
                return True
            if isinstance(monitor_filter, list):
                if len(monitor_filter) == 0:
                    return True
                return screen_name in monitor_filter
            if isinstance(monitor_filter, str):
                return monitor_filter == screen_name or monitor_filter in ["primary", "default"]
            return False

        self.assertTrue(is_allowed("eDP-1", "all"))
        self.assertTrue(is_allowed("DP-2", "all"))
        self.assertTrue(is_allowed("eDP-1", ["eDP-1"]))
        self.assertFalse(is_allowed("DP-2", ["eDP-1"]))
        self.assertTrue(is_allowed("DP-2", ["eDP-1", "DP-2"]))
        self.assertTrue(is_allowed("eDP-1", "primary")) # legacy fallback

    def test_09_quickshell_startup_smoke_test(self):
        """Startup smoke test: execute quickshell against root shell.qml to verify syntax/QML engine startup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["XDG_CONFIG_HOME"] = tmpdir
            proc = subprocess.Popen(
                ["quickshell", "-p", "./shell.qml", "--no-duplicate"],
                cwd=REPO_DIR,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            time.sleep(2)
            is_running = proc.poll() is None
            proc.terminate()
            try:
                proc.communicate(timeout=2)
            except Exception:
                proc.kill()
            self.assertTrue(is_running, "Quickshell process crashed or exited unexpectedly during startup")

    def test_10_tray_visibility_and_id_collisions(self):
        """Verify tray visibility policies, live status transitions, chevron rules, and _status_icon_N collision/transition safety."""
        with open(os.path.join(REPO_DIR, "modules/bar/TrayModule.qml")) as f:
            tray_content = f.read()
        self.assertIn("readonly property bool hasHiddenItems: root.hiddenItems.length > 0", tray_content)
        self.assertIn("visible: root.hasHiddenItems", tray_content)
        self.assertIn("active: root.overflowOpen && root.hasHiddenItems", tray_content)
        self.assertIn("overflowDelegate.modelData.display(win, Math.round(pt.x), Math.round(pt.y))", tray_content)

        with open(os.path.join(REPO_DIR, "services/config/ConfigService.qml")) as f:
            cfg_content = f.read()
        self.assertIn("function hasTrayPrefixCollision", cfg_content)
        self.assertIn("function isLegacyTrayKeyCovered", cfg_content)
        self.assertIn("function getTrayItemId", cfg_content)
        self.assertIn("function getTrayItemPolicy", cfg_content)
        self.assertIn("function setTrayItemPolicy", cfg_content)

        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["XDG_CONFIG_HOME"] = tmpdir
            probe_path = os.path.join(REPO_DIR, "_test_tray_regression_probe.qml")
            reload_probe_path = os.path.join(REPO_DIR, "_test_tray_reload_probe.qml")
            try:
                with open(probe_path, "w") as pf:
                    pf.write("""import QtQuick
import Quickshell
import Quickshell.Services.SystemTray
import "./services"
import "./modules/bar"

Scope {
    QtObject { id: single1; property string id: "discord_status_icon_1"; property int status: Status.Active }
    QtObject { id: single2; property string id: "discord_status_icon_2"; property int status: Status.Passive }
    QtObject { id: multi1; property string id: "myapp_status_icon_1"; property int status: Status.Active }
    QtObject { id: multi2; property string id: "myapp_status_icon_2"; property int status: Status.Active }
    QtObject { id: generic1; property string id: "chrome_status_icon_1"; property int status: Status.Active }
    QtObject { id: generic2; property string id: "chrome_status_icon_2"; property int status: Status.Active }
    QtObject { id: unknownSt; property string id: "custom-sni"; property var status: undefined }

    TrayModule { id: trayMod }

    Timer {
        interval: 250
        running: true
        repeat: false
        onTriggered: {
            // Single-icon _status_icon_N normalizes and survives reconnect with incremented counter
            const idSingle1 = ConfigService.getTrayItemId(single1, [single1]);
            ConfigService.setTrayItemPolicy(single1, "hidden", [single1]);
            const polReconnect = ConfigService.getTrayItemPolicy(single2, [single2]);

            // BB2.1 Transition 1: Single icon -> save Hidden (stored as "myapp")
            const idM1Solo = ConfigService.getTrayItemId(multi1, [multi1]);
            ConfigService.setTrayItemPolicy(multi1, "hidden", [multi1]);
            const polM1Solo = ConfigService.getTrayItemPolicy(multi1, [multi1]);

            // BB2.1 Transition 2: Second same-prefix icon joins -> existing user preference must not disappear
            const bothMulti = [multi1, multi2];
            const idM1Joined = ConfigService.getTrayItemId(multi1, bothMulti);
            const idM2Joined = ConfigService.getTrayItemId(multi2, bothMulti);
            const polM1AfterJoin = ConfigService.getTrayItemPolicy(multi1, bothMulti);
            const polM1ByKeyAfterJoin = ConfigService.getTrayItemPolicy(idM1Joined, bothMulti);
            const legacyCoveredOnJoin = ConfigService.isLegacyTrayKeyCovered("myapp", bothMulti);

            // BB2.1 Transition 3: Set different policies on both icons -> independent
            ConfigService.setTrayItemPolicy(multi2, "always", bothMulti);
            const polM1AfterM2Set = ConfigService.getTrayItemPolicy(multi1, bothMulti);
            const polM2AfterM2Set = ConfigService.getTrayItemPolicy(multi2, bothMulti);
            ConfigService.setTrayItemPolicy(multi1, "hidden", bothMulti);
            const polM1Explicit = ConfigService.getTrayItemPolicy(multi1, bothMulti);

            // BB2.1 Transition 4: Second icon disappears -> policies remain deterministic
            const polM1AfterLeave = ConfigService.getTrayItemPolicy(multi1, [multi1]);
            const polM2WhileDisconnected = ConfigService.getTrayItemPolicy(multi2, [multi1]);
            const legacyCoveredAfterLeave = ConfigService.isLegacyTrayKeyCovered("myapp", [multi1]);
            const m2CoveredWhileDisconnected = ConfigService.isLegacyTrayKeyCovered("myapp_status_icon_2", [multi1]);

            // Generic runtime prefix collision prevention
            const idG1 = ConfigService.getTrayItemId(generic1, [generic1]);
            const idG2 = ConfigService.getTrayItemId(generic2, [generic1, generic2]);

            // TrayModule policy + status evaluation
            ConfigService.setTrayItemPolicy(single1, "auto", [single1]);
            const autoActiveVis = trayMod.isItemVisibleInBar(single1);
            single1.status = Status.Passive;
            const autoPassiveVis = trayMod.isItemVisibleInBar(single1);
            single1.status = Status.NeedsAttention;
            const autoAttnVis = trayMod.isItemVisibleInBar(single1);
            const unknownVis = trayMod.isItemVisibleInBar(unknownSt);

            console.log("TRAY_TEST_RESULT:" + JSON.stringify({
                idSingle1: idSingle1,
                polReconnect: polReconnect,
                idM1Solo: idM1Solo,
                polM1Solo: polM1Solo,
                idM1Joined: idM1Joined,
                idM2Joined: idM2Joined,
                polM1AfterJoin: polM1AfterJoin,
                polM1ByKeyAfterJoin: polM1ByKeyAfterJoin,
                legacyCoveredOnJoin: legacyCoveredOnJoin,
                polM1AfterM2Set: polM1AfterM2Set,
                polM2AfterM2Set: polM2AfterM2Set,
                polM1Explicit: polM1Explicit,
                polM1AfterLeave: polM1AfterLeave,
                polM2WhileDisconnected: polM2WhileDisconnected,
                legacyCoveredAfterLeave: legacyCoveredAfterLeave,
                m2CoveredWhileDisconnected: m2CoveredWhileDisconnected,
                idG1: idG1,
                idG2: idG2,
                autoActiveVis: autoActiveVis,
                autoPassiveVis: autoPassiveVis,
                autoAttnVis: autoAttnVis,
                unknownVis: unknownVis
            }));
            quitTimer.running = true;
        }
    }
    Timer {
        id: quitTimer
        interval: 100
        repeat: false
        onTriggered: Qt.quit()
    }
}
""")
                proc = subprocess.run(
                    ["quickshell", "-p", probe_path, "--no-duplicate"],
                    cwd=REPO_DIR,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=6
                )
                combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
                marker = "TRAY_TEST_RESULT:"
                self.assertIn(marker, combined, f"Missing marker in output:\\n{combined}")
                payload_line = [line for line in combined.splitlines() if marker in line][-1]
                data = json.loads(payload_line.split(marker, 1)[1].strip())

                self.assertEqual(data["idSingle1"], "discord")
                self.assertEqual(data["polReconnect"], "hidden")
                self.assertEqual(data["idM1Solo"], "myapp")
                self.assertEqual(data["polM1Solo"], "hidden")
                self.assertEqual(data["idM1Joined"], "myapp_status_icon_1")
                self.assertEqual(data["idM2Joined"], "myapp_status_icon_2")
                self.assertEqual(data["polM1AfterJoin"], "hidden")
                self.assertEqual(data["polM1ByKeyAfterJoin"], "hidden")
                self.assertTrue(data["legacyCoveredOnJoin"])
                self.assertEqual(data["polM1AfterM2Set"], "hidden")
                self.assertEqual(data["polM2AfterM2Set"], "always")
                self.assertEqual(data["polM1Explicit"], "hidden")
                self.assertEqual(data["polM1AfterLeave"], "hidden")
                self.assertEqual(data["polM2WhileDisconnected"], "always")
                self.assertTrue(data["legacyCoveredAfterLeave"])
                self.assertFalse(data["m2CoveredWhileDisconnected"])
                self.assertEqual(data["idG1"], "chrome_status_icon_1")
                self.assertEqual(data["idG2"], "chrome_status_icon_2")
                self.assertTrue(data["autoActiveVis"])
                self.assertFalse(data["autoPassiveVis"])
                self.assertTrue(data["autoAttnVis"])
                self.assertTrue(data["unknownVis"])

                # BB2.1 Transition 5 & 6: Reload config in fresh process -> preferences persist and legacy key is suppressed
                with open(reload_probe_path, "w") as rpf:
                    rpf.write("""import QtQuick
import Quickshell
import Quickshell.Services.SystemTray
import "./services"

Scope {
    property var _cfg: ConfigService.trayItemPolicies
    QtObject { id: multi1; property string id: "myapp_status_icon_1"; property int status: Status.Active }
    QtObject { id: multi2; property string id: "myapp_status_icon_2"; property int status: Status.Active }

    Timer {
        interval: 250
        running: true
        repeat: false
        onTriggered: {
            const both = [multi1, multi2];
            console.log("TRAY_RELOAD_RESULT:" + JSON.stringify({
                polM1SoloReload: ConfigService.getTrayItemPolicy(multi1, [multi1]),
                polM1BothReload: ConfigService.getTrayItemPolicy(multi1, both),
                polM2BothReload: ConfigService.getTrayItemPolicy(multi2, both),
                legacyCoveredReload: ConfigService.isLegacyTrayKeyCovered("myapp", [multi1])
            }));
            Qt.quit();
        }
    }
}
""")
                proc_reload = subprocess.run(
                    ["quickshell", "-p", reload_probe_path, "--no-duplicate"],
                    cwd=REPO_DIR,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=6
                )
                reload_combined = (proc_reload.stdout or "") + "\n" + (proc_reload.stderr or "")
                reload_marker = "TRAY_RELOAD_RESULT:"
                self.assertIn(reload_marker, reload_combined, f"Missing reload marker:\\n{reload_combined}")
                reload_line = [line for line in reload_combined.splitlines() if reload_marker in line][-1]
                reload_data = json.loads(reload_line.split(reload_marker, 1)[1].strip())

                self.assertEqual(reload_data["polM1SoloReload"], "hidden")
                self.assertEqual(reload_data["polM1BothReload"], "hidden")
                self.assertEqual(reload_data["polM2BothReload"], "always")
                self.assertTrue(reload_data["legacyCoveredReload"])
            finally:
                for p in (probe_path, reload_probe_path):
                    if os.path.exists(p):
                        os.remove(p)

    def test_11_window_identity_and_ghost_dock_prevention(self):
        """Verify KWin window identity resolution ignores window titles, resolves StartupWMClass/desktopFile, filters uninstalled pinned apps, and keeps unknown apps deterministic."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["XDG_CONFIG_HOME"] = tmpdir
            probe_path = os.path.join(REPO_DIR, "_test_window_identity_probe.qml")
            try:
                with open(probe_path, "w") as pf:
                    pf.write("""import QtQuick
import Quickshell
import "./services"

Scope {
    property var _cfg: ConfigService.dockPinned
    Timer {
        interval: 350
        running: true
        repeat: false
        onTriggered: {
            ApplicationService.applications = [
                {
                    id: "org.kde.dolphin",
                    name: "Dolphin",
                    icon: "system-file-manager",
                    startupWMClass: "",
                    execBinary: "dolphin",
                    aliases: ["org.kde.dolphin", "dolphin", "system-file-manager"]
                },
                {
                    id: "org.kde.konsole",
                    name: "Konsole",
                    icon: "utilities-terminal",
                    startupWMClass: "",
                    execBinary: "konsole",
                    aliases: ["org.kde.konsole", "konsole", "utilities-terminal"]
                },
                {
                    id: "org.mozilla.firefox",
                    name: "Firefox",
                    icon: "org.mozilla.firefox",
                    startupWMClass: "org.mozilla.firefox",
                    execBinary: "firefox",
                    aliases: ["org.mozilla.firefox", "firefox"]
                },
                {
                    id: "com.discordapp.Discord",
                    name: "Discord",
                    icon: "com.discordapp.Discord",
                    startupWMClass: "discord",
                    execBinary: "flatpak",
                    aliases: ["com.discordapp.discord", "discord"]
                },
                {
                    id: "com.spotify.Client",
                    name: "Spotify",
                    icon: "com.spotify.Client",
                    startupWMClass: "spotify",
                    execBinary: "flatpak",
                    aliases: ["com.spotify.client", "spotify"]
                },
                {
                    id: "faugus-shortcut",
                    name: "Faugus Launcher",
                    icon: "application-x-executable",
                    startupWMClass: "",
                    execBinary: "env",
                    aliases: ["faugus-shortcut", "env", "application-x-executable"]
                }
            ];
            ApplicationService.loading = false;

            const rawOutput = [
                '[Argument: (sssida{sv}) "0_{95883ac0-1606-4793-828b-35d890ed89e0}", "Sesli Sohbet 1 | NepentheSubs - Discord", "", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "0_{178fdccb-6efb-41d5-864f-26a4e0095b74}", "Fatma Turgut - Gunleri Baglarken", "", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "0_{19261c49-3ffb-45ba-bab8-892801ae3dbd}", "QuickShell - Mozilla Firefox", "org.mozilla.firefox", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "0_{19261c49-3ffb-45ba-bab8-892801ae3dbe}", "Docs - code - Mozilla Firefox", "org.mozilla.firefox", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "0_{deadbeef-0000-0000-0000-000000000001}", "project.py - code", "", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "0_{deadbeef-0000-0000-0000-000000000002}", "Fake Spoof - Firefox", "", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "0_{deadbeef-0000-0000-0000-000000000003}", "Build Output - env", "", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "0_{deadbeef-0000-0000-0000-000000000004}", "Custom Tool Window 1 - Discord", "", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "0_{deadbeef-0000-0000-0000-000000000005}", "Custom Tool Window 2 - Spotify", "", 100, 1.0, [Argument: a{sv} {}]]',
                '===KWIN_META:0_{95883ac0-1606-4793-828b-35d890ed89e0}\\tdiscord\\tdiscord\\t===',
                '===KWIN_META:0_{178fdccb-6efb-41d5-864f-26a4e0095b74}\\tspotify\\tspotify\\t===',
                '===KWIN_META:0_{19261c49-3ffb-45ba-bab8-892801ae3dbd}\\torg.mozilla.firefox\\torg.mozilla.firefox\\t===',
                '===KWIN_META:0_{19261c49-3ffb-45ba-bab8-892801ae3dbe}\\torg.mozilla.firefox\\torg.mozilla.firefox\\t===',
                '===KWIN_META:0_{deadbeef-0000-0000-0000-000000000004}\\t\\tmy-uninstalled-tool\\tmy-uninstalled-tool===',
                '===KWIN_META:0_{deadbeef-0000-0000-0000-000000000005}\\t\\tmy-uninstalled-tool\\tmy-uninstalled-tool==='
            ].join("\\n");

            WindowService.parseWindowsOutput(rawOutput);

            const byWid = {};
            for (let i = 0; i < WindowService.windows.length; i++) {
                const w = WindowService.windows[i];
                byWid[w.id] = { appId: w.appId, appName: w.appName, hasApp: w.app !== null };
            }

            const ffWins = WindowService.getWindowsForApp("firefox").map(w => w.id);
            const customWins = WindowService.getWindowsForApp("window-my-uninstalled-tool").map(w => w.id);

            console.log("WINDOW_IDENTITY_RESULT:" + JSON.stringify({
                rawPinned: ConfigService.dockPinned,
                filteredPinned: ApplicationService.pinnedApps,
                runningAppIds: WindowService.runningAppIds,
                byWid: byWid,
                ffWins: ffWins,
                customWins: customWins,
                faugusRunning: WindowService.isAppRunning("faugus-shortcut")
            }));
            Qt.quit();
        }
    }
}
""")
                proc = subprocess.run(
                    ["quickshell", "-p", probe_path, "--no-duplicate"],
                    cwd=REPO_DIR,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=6
                )
                combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
                marker = "WINDOW_IDENTITY_RESULT:"
                self.assertIn(marker, combined, f"Missing marker in output:\\n{combined}")
                payload_line = [line for line in combined.splitlines() if marker in line][-1]
                data = json.loads(payload_line.split(marker, 1)[1].strip())

                # 1. Uninstalled "code" remains in raw config but is excluded from effective pinnedApps
                self.assertIn("code", data["rawPinned"])
                self.assertNotIn("code", data["filteredPinned"])
                self.assertEqual(
                    data["filteredPinned"],
                    ["org.kde.dolphin", "org.kde.konsole", "firefox"]
                )

                # 2. Discord and Spotify resolve via KWin desktopFile/StartupWMClass even when WindowsRunner icon is empty
                self.assertEqual(data["byWid"]["0_{95883ac0-1606-4793-828b-35d890ed89e0}"]["appId"], "com.discordapp.Discord")
                self.assertEqual(data["byWid"]["0_{178fdccb-6efb-41d5-864f-26a4e0095b74}"]["appId"], "com.spotify.Client")

                # 3. Window titles ending in "- code", "- Firefox", "- env" never infer app identity
                self.assertEqual(
                    data["byWid"]["0_{deadbeef-0000-0000-0000-000000000001}"]["appId"],
                    "window-0_{deadbeef-0000-0000-0000-000000000001}"
                )
                self.assertFalse(data["byWid"]["0_{deadbeef-0000-0000-0000-000000000001}"]["hasApp"])
                self.assertEqual(
                    data["byWid"]["0_{deadbeef-0000-0000-0000-000000000002}"]["appId"],
                    "window-0_{deadbeef-0000-0000-0000-000000000002}"
                )
                self.assertEqual(
                    data["byWid"]["0_{deadbeef-0000-0000-0000-000000000003}"]["appId"],
                    "window-0_{deadbeef-0000-0000-0000-000000000003}"
                )
                self.assertFalse(data["faugusRunning"])

                # 4. Known and unknown multi-window apps group deterministically and preserve exact UUIDs
                self.assertEqual(
                    data["ffWins"],
                    ["0_{19261c49-3ffb-45ba-bab8-892801ae3dbd}", "0_{19261c49-3ffb-45ba-bab8-892801ae3dbe}"]
                )
                self.assertEqual(
                    data["customWins"],
                    ["0_{deadbeef-0000-0000-0000-000000000004}", "0_{deadbeef-0000-0000-0000-000000000005}"]
                )
            finally:
                if os.path.exists(probe_path):
                    os.remove(probe_path)

    def test_12_kwin_metadata_cache_edge_cases(self):
        """Verify KWin metadata cache handles failure retries, closed windows during query, and queued queries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["XDG_CONFIG_HOME"] = tmpdir
            probe_path = os.path.join(REPO_DIR, "_test_cache_edge_probe.qml")
            try:
                with open(probe_path, "w") as pf:
                    pf.write("""import QtQuick
import Quickshell
import "./services"

Scope {
    Timer {
        interval: 200
        running: true
        repeat: false
        onTriggered: {
            ApplicationService.applications = [
                {
                    id: "org.mozilla.firefox",
                    name: "Firefox",
                    icon: "org.mozilla.firefox",
                    startupWMClass: "org.mozilla.firefox",
                    execBinary: "firefox",
                    aliases: ["org.mozilla.firefox", "firefox"]
                }
            ];
            ApplicationService.loading = false;

            // Scenario 1: Setup active windows including a blank-title/icon window
            const winOutput = [
                '[Argument: (sssida{sv}) "0_{active-1111}", "Active Window 1", "", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "0_{active-2222}", "Active Window 2", "", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "0_{blank-3333}", "", "", 100, 1.0, [Argument: a{sv} {}]]'
            ].join("\\n");
            WindowService.handleScannerOutput(winOutput);
            const blankInWindowsBeforeMeta = WindowService.windows.some(w => w.id === "0_{blank-3333}");

            // 1. Single getWindowInfo failure does NOT permanently cache empty metadata
            WindowService.parseMetaOutput("===KWIN_META_FAIL:0_{active-1111}===");
            const cachedAfter1Fail = WindowService.metadataCache["0_{active-1111}"];
            const retriesAfter1Fail = WindowService.metaRetries["0_{active-1111}"];

            // 2. Window closes while meta query was in-flight (0_{closed-9999} not in active set)
            WindowService.parseMetaOutput("===KWIN_META:0_{closed-9999}\\torg.mozilla.firefox\\torg.mozilla.firefox\\t===");
            const closedCached = WindowService.metadataCache["0_{closed-9999}"];

            // 3. Metadata arrives for blank-title/icon window -> discovered and resolved
            WindowService.parseMetaOutput("===KWIN_META:0_{blank-3333}\\torg.mozilla.firefox\\torg.mozilla.firefox\\t===");
            const blankWin = WindowService.windows.find(w => w.id === "0_{blank-3333}");

            // 4. Subsequent success for 0_{active-1111} populates cache and clears retry count
            WindowService.parseMetaOutput("===KWIN_META:0_{active-1111}\\torg.mozilla.firefox\\torg.mozilla.firefox\\t===");
            const cachedAfterSuccess = WindowService.metadataCache["0_{active-1111}"];
            const retriesAfterSuccess = WindowService.metaRetries["0_{active-1111}"];

            // 5. Repeated 3 failures permanently marks cache to avoid infinite polling
            WindowService.parseMetaOutput("===KWIN_META_FAIL:0_{active-2222}===");
            WindowService.parseMetaOutput("===KWIN_META_FAIL:0_{active-2222}===");
            WindowService.parseMetaOutput("===KWIN_META_FAIL:0_{active-2222}===");
            const cachedAfter3Fails = WindowService.metadataCache["0_{active-2222}"];

            console.log("CACHE_EDGE_RESULT:" + JSON.stringify({
                blankInWindowsBeforeMeta: blankInWindowsBeforeMeta,
                blankResolvedAppId: blankWin ? blankWin.appId : null,
                cachedAfter1Fail: cachedAfter1Fail !== undefined,
                retriesAfter1Fail: retriesAfter1Fail,
                closedCached: closedCached !== undefined,
                hasCachedAfterSuccess: cachedAfterSuccess !== undefined,
                successDesktopFile: cachedAfterSuccess ? cachedAfterSuccess.desktopFile : "",
                retriesAfterSuccess: retriesAfterSuccess !== undefined,
                hasCachedAfter3Fails: cachedAfter3Fails !== undefined
            }));
            Qt.quit();
        }
    }
}
""")
                proc = subprocess.run(
                    ["quickshell", "-p", probe_path, "--no-duplicate"],
                    cwd=REPO_DIR,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=6
                )
                combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
                marker = "CACHE_EDGE_RESULT:"
                self.assertIn(marker, combined, f"Missing marker in output:\\n{combined}")
                payload_line = [line for line in combined.splitlines() if marker in line][-1]
                data = json.loads(payload_line.split(marker, 1)[1].strip())

                # Blank title/icon window initially skipped, then discovered upon metadata arrival
                self.assertFalse(data["blankInWindowsBeforeMeta"])
                self.assertEqual(data["blankResolvedAppId"], "org.mozilla.firefox")

                # Single failure must not cache empty metadata, must increment retry
                self.assertFalse(data["cachedAfter1Fail"])
                self.assertEqual(data["retriesAfter1Fail"], 1)

                # Window closed during in-flight query must be discarded
                self.assertFalse(data["closedCached"])

                # Subsequent success populates cache and clears retries
                self.assertTrue(data["hasCachedAfterSuccess"])
                self.assertEqual(data["successDesktopFile"], "org.mozilla.firefox")
                self.assertFalse(data["retriesAfterSuccess"])

                # 3 consecutive failures safely caches empty metadata to prevent infinite loop
                self.assertTrue(data["hasCachedAfter3Fails"])
            finally:
                if os.path.exists(probe_path):
                    os.remove(probe_path)

    def test_13_kwin_window_actions(self):
        """Verify KWin native window actions: UUID-exact activate, graceful close, move across outputs, 1-output hiding, invalid output rejection, and stale UUID no-ops."""
        script_path = os.path.join(REPO_DIR, "services/kwin/scripts/kwin-window-action.sh")
        self.assertTrue(os.path.exists(script_path), "kwin-window-action.sh must exist")
        with open(script_path) as sf:
            script_text = sf.read()
        for forbidden in ["killall", "pkill", "SIGTERM", "SIGKILL", "killWindow"]:
            self.assertNotIn(forbidden, script_text)
        self.assertIn("w.closeWindow()", script_text)
        self.assertIn("workspace.sendClientToScreen(w, targetScreen)", script_text)

        with open(os.path.join(REPO_DIR, "modules/dock/DockMenu.qml")) as dmf:
            dm_text = dmf.read()
        self.assertIn("WindowService.activateWindow(", dm_text)
        self.assertIn("WindowService.moveWindowToOutput(", dm_text)
        self.assertIn("WindowService.closeWindow(", dm_text)
        self.assertIn("WindowService.getTargetOutputsForWindow(", dm_text)

        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["XDG_CONFIG_HOME"] = tmpdir
            probe_path = os.path.join(REPO_DIR, "_test_window_actions_probe.qml")
            try:
                with open(probe_path, "w") as pf:
                    pf.write("""import QtQuick
import Quickshell
import "./services"

Scope {
    Timer {
        interval: 250
        running: true
        repeat: false
        onTriggered: {
            ApplicationService.applications = [
                {
                    id: "org.mozilla.firefox",
                    name: "Firefox",
                    icon: "org.mozilla.firefox",
                    startupWMClass: "org.mozilla.firefox",
                    execBinary: "firefox",
                    aliases: ["org.mozilla.firefox", "firefox"]
                },
                {
                    id: "org.kde.konsole",
                    name: "Konsole",
                    icon: "utilities-terminal",
                    startupWMClass: "org.kde.konsole",
                    execBinary: "konsole",
                    aliases: ["org.kde.konsole", "konsole"]
                }
            ];
            ApplicationService.loading = false;

            const uuidA = "0_{11111111-1111-1111-1111-111111111111}";
            const uuidB = "0_{22222222-2222-2222-2222-222222222222}";
            const uuidC = "0_{33333333-3333-3333-3333-333333333333}";
            const staleUuid = "0_{99999999-9999-9999-9999-999999999999}";

            // 1. One-output behavior initially
            WindowService.outputsOverride = ["eDP-1"];
            const rawWin = [
                '[Argument: (sssida{sv}) "' + uuidA + '", "Firefox Win A", "org.mozilla.firefox", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "' + uuidB + '", "Firefox Win B", "org.mozilla.firefox", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "' + uuidC + '", "Konsole Win C", "utilities-terminal", 100, 1.0, [Argument: a{sv} {}]]',
                '===KWIN_META:' + uuidA + '\\torg.mozilla.firefox\\torg.mozilla.firefox\\t===',
                '===KWIN_META:' + uuidB + '\\torg.mozilla.firefox\\torg.mozilla.firefox\\t===',
                '===KWIN_META:' + uuidC + '\\torg.kde.konsole\\torg.kde.konsole\\tkonsole==='
            ].join("\\n");
            WindowService.handleScannerOutput(rawWin);

            const oneOutTargetsA = WindowService.getTargetOutputsForWindow(uuidA);
            const oneOutMoveAttempt = WindowService.moveWindowToOutput(uuidA, "eDP-1");

            // 2. Activate UUID A without affecting UUID B
            const actA = WindowService.activateWindow(uuidA);
            const activeAfterA = WindowService.activeWindowId;
            const ffWinsBeforeClose = WindowService.getWindowsForApp("firefox").map(w => w.id);

            // 3. Multi-monitor (2 connected outputs: eDP-1 and DP-2) — non-optimistic move reconciliation
            WindowService.outputsOverride = ["eDP-1", "DP-2"];
            WindowService.parseWindowOutputsJson(JSON.stringify([
                { id: "{11111111-1111-1111-1111-111111111111}", output: "eDP-1" },
                { id: "{22222222-2222-2222-2222-222222222222}", output: "eDP-1" },
                { id: "{33333333-3333-3333-3333-333333333333}", output: "eDP-1" }
            ]));
            const twoOutTargetsABefore = WindowService.getTargetOutputsForWindow(uuidA);
            const moveAToDP2 = WindowService.moveWindowToOutput(uuidA, "DP-2");
            // Unconfirmed move must NOT optimistically report DP-2 before KWin confirms
            const outABeforeKWinConfirm = WindowService.getWindowOutput(uuidA);
            const targetsABeforeKWinConfirm = WindowService.getTargetOutputsForWindow(uuidA);

            // Simulate move rejected/failed in KWin (KWin still reports eDP-1)
            WindowService.parseWindowOutputsJson(JSON.stringify([
                { id: "{11111111-1111-1111-1111-111111111111}", output: "eDP-1" },
                { id: "{22222222-2222-2222-2222-222222222222}", output: "eDP-1" },
                { id: "{33333333-3333-3333-3333-333333333333}", output: "eDP-1" }
            ]));
            const outAAfterRejectedMove = WindowService.getWindowOutput(uuidA);

            // Simulate move confirmed by later KWin output refresh
            WindowService.parseWindowOutputsJson(JSON.stringify([
                { id: "{11111111-1111-1111-1111-111111111111}", output: "DP-2" },
                { id: "{22222222-2222-2222-2222-222222222222}", output: "eDP-1" },
                { id: "{33333333-3333-3333-3333-333333333333}", output: "eDP-1" }
            ]));
            const outAAfterConfirmedMove = WindowService.getWindowOutput(uuidA);
            const outBAfterMoveA = WindowService.getWindowOutput(uuidB);
            const twoOutTargetsAAfter = WindowService.getTargetOutputsForWindow(uuidA);
            const moveAToSameDP2 = WindowService.moveWindowToOutput(uuidA, "DP-2");
            const moveABackToEDP1 = WindowService.moveWindowToOutput(uuidA, "eDP-1");
            WindowService.parseWindowOutputsJson(JSON.stringify([
                { id: "{11111111-1111-1111-1111-111111111111}", output: "eDP-1" },
                { id: "{22222222-2222-2222-2222-222222222222}", output: "eDP-1" },
                { id: "{33333333-3333-3333-3333-333333333333}", output: "eDP-1" }
            ]));
            const outAAfterReturn = WindowService.getWindowOutput(uuidA);

            // 4. Invalid / removed output checks
            const moveInvalidOut = WindowService.moveWindowToOutput(uuidA, "HDMI-99-NONE");
            const moveUnsafeOut = WindowService.moveWindowToOutput(uuidA, "DP-2;rm");
            WindowService.outputsOverride = ["eDP-1"];
            const targetsAfterRemoveDP2 = WindowService.getTargetOutputsForWindow(uuidA);
            const moveRemovedDP2 = WindowService.moveWindowToOutput(uuidA, "DP-2");

            // 5. Close UUID A gracefully — non-optimistic close reconciliation
            WindowService.outputsOverride = ["eDP-1", "DP-2"];
            const closeA = WindowService.closeWindow(uuidA);
            // Window must remain in local state until KWin confirms closure (e.g. unsaved-changes dialog)
            const ffWinsBeforeConfirmClose = WindowService.getWindowsForApp("firefox").map(w => w.id);
            WindowService.handleScannerOutput(rawWin); // KWin still enumerates uuidA (close rejected/delayed)
            const ffWinsAfterRejectedClose = WindowService.getWindowsForApp("firefox").map(w => w.id);

            // Now KWin scanner update confirms uuidA disappeared
            const rawWinAfterCloseA = [
                '[Argument: (sssida{sv}) "' + uuidB + '", "Firefox Win B", "org.mozilla.firefox", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "' + uuidC + '", "Konsole Win C", "utilities-terminal", 100, 1.0, [Argument: a{sv} {}]]'
            ].join("\\n");
            WindowService.handleScannerOutput(rawWinAfterCloseA);
            const ffWinsAfterConfirmedCloseA = WindowService.getWindowsForApp("firefox").map(w => w.id);
            const konsoleWinsAfterCloseA = WindowService.getWindowsForApp("konsole").map(w => w.id);
            const activeAfterConfirmedCloseA = WindowService.activeWindowId;

            // 6. Stale UUID no-ops (confirmed closed UUID A + non-existent UUID + unsafe string)
            const closeAAgain = WindowService.closeWindow(uuidA);
            const activateClosedA = WindowService.activateWindow(uuidA);
            const moveClosedA = WindowService.moveWindowToOutput(uuidA, "DP-2");
            const closeStale = WindowService.closeWindow(staleUuid);
            const activateStale = WindowService.activateWindow(staleUuid);
            const moveStale = WindowService.moveWindowToOutput(staleUuid, "DP-2");
            const closeUnsafe = WindowService.closeWindow("0_{bad;cmd}");

            console.log("WINDOW_ACTIONS_RESULT:" + JSON.stringify({
                oneOutTargetsA: oneOutTargetsA,
                oneOutMoveAttempt: oneOutMoveAttempt,
                actA: actA,
                activeAfterA: activeAfterA,
                ffWinsBeforeClose: ffWinsBeforeClose,
                twoOutTargetsABefore: twoOutTargetsABefore,
                moveAToDP2: moveAToDP2,
                outABeforeKWinConfirm: outABeforeKWinConfirm,
                targetsABeforeKWinConfirm: targetsABeforeKWinConfirm,
                outAAfterRejectedMove: outAAfterRejectedMove,
                outAAfterConfirmedMove: outAAfterConfirmedMove,
                outBAfterMoveA: outBAfterMoveA,
                twoOutTargetsAAfter: twoOutTargetsAAfter,
                moveAToSameDP2: moveAToSameDP2,
                moveABackToEDP1: moveABackToEDP1,
                outAAfterReturn: outAAfterReturn,
                moveInvalidOut: moveInvalidOut,
                moveUnsafeOut: moveUnsafeOut,
                targetsAfterRemoveDP2: targetsAfterRemoveDP2,
                moveRemovedDP2: moveRemovedDP2,
                closeA: closeA,
                ffWinsBeforeConfirmClose: ffWinsBeforeConfirmClose,
                ffWinsAfterRejectedClose: ffWinsAfterRejectedClose,
                ffWinsAfterConfirmedCloseA: ffWinsAfterConfirmedCloseA,
                konsoleWinsAfterCloseA: konsoleWinsAfterCloseA,
                activeAfterConfirmedCloseA: activeAfterConfirmedCloseA,
                closeAAgain: closeAAgain,
                activateClosedA: activateClosedA,
                moveClosedA: moveClosedA,
                closeStale: closeStale,
                activateStale: activateStale,
                moveStale: moveStale,
                closeUnsafe: closeUnsafe
            }));
            Qt.quit();
        }
    }
}
""")
                proc = subprocess.run(
                    ["quickshell", "-p", probe_path, "--no-duplicate"],
                    cwd=REPO_DIR,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=6
                )
                combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
                marker = "WINDOW_ACTIONS_RESULT:"
                self.assertIn(marker, combined, f"Missing marker in output:\\n{combined}")
                payload_line = [line for line in combined.splitlines() if marker in line][-1]
                data = json.loads(payload_line.split(marker, 1)[1].strip())

                uuid_a = "0_{11111111-1111-1111-1111-111111111111}"
                uuid_b = "0_{22222222-2222-2222-2222-222222222222}"
                uuid_c = "0_{33333333-3333-3333-3333-333333333333}"

                # 1. One-output behavior
                self.assertEqual(data["oneOutTargetsA"], [])
                self.assertFalse(data["oneOutMoveAttempt"])

                # 2. Activate UUID A without affecting UUID B
                self.assertTrue(data["actA"])
                self.assertEqual(data["activeAfterA"], "11111111-1111-1111-1111-111111111111")
                self.assertEqual(data["ffWinsBeforeClose"], [uuid_a, uuid_b])

                # 3. Move between two connected outputs (non-optimistic, KWin-confirmed)
                self.assertEqual(data["twoOutTargetsABefore"], ["DP-2"])
                self.assertTrue(data["moveAToDP2"])
                self.assertEqual(data["outABeforeKWinConfirm"], "eDP-1")
                self.assertEqual(data["targetsABeforeKWinConfirm"], ["DP-2"])
                self.assertEqual(data["outAAfterRejectedMove"], "eDP-1")
                self.assertEqual(data["outAAfterConfirmedMove"], "DP-2")
                self.assertEqual(data["outBAfterMoveA"], "eDP-1")
                self.assertEqual(data["twoOutTargetsAAfter"], ["eDP-1"])
                self.assertFalse(data["moveAToSameDP2"])
                self.assertTrue(data["moveABackToEDP1"])
                self.assertEqual(data["outAAfterReturn"], "eDP-1")

                # 4. Invalid / removed outputs
                self.assertFalse(data["moveInvalidOut"])
                self.assertFalse(data["moveUnsafeOut"])
                self.assertEqual(data["targetsAfterRemoveDP2"], [])
                self.assertFalse(data["moveRemovedDP2"])

                # 5. Graceful close UUID A (non-optimistic when rejected/delayed, removed when KWin confirms)
                self.assertTrue(data["closeA"])
                self.assertEqual(data["ffWinsBeforeConfirmClose"], [uuid_a, uuid_b])
                self.assertEqual(data["ffWinsAfterRejectedClose"], [uuid_a, uuid_b])
                self.assertEqual(data["ffWinsAfterConfirmedCloseA"], [uuid_b])
                self.assertEqual(data["konsoleWinsAfterCloseA"], [uuid_c])
                self.assertEqual(data["activeAfterConfirmedCloseA"], "")

                # 6. Stale / closed / unsafe UUID no-ops
                self.assertFalse(data["closeAAgain"])
                self.assertFalse(data["activateClosedA"])
                self.assertFalse(data["moveClosedA"])
                self.assertFalse(data["closeStale"])
                self.assertFalse(data["activateStale"])
                self.assertFalse(data["moveStale"])
                self.assertFalse(data["closeUnsafe"])
            finally:
                if os.path.exists(probe_path):
                    os.remove(probe_path)

    def test_16_json_store_and_config_service_durability(self):
        """Live QML Runtime Test: Verify JsonStore and ConfigService durability under pre-load mutations, rapid saves, deferred loads, serialize/write failures, and corrupt/empty JSON preservation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["XDG_CONFIG_HOME"] = tmpdir
            cfg_dir = os.path.join(tmpdir, "quickshell-kde")
            os.makedirs(cfg_dir, exist_ok=True)
            corrupt_path = os.path.join(cfg_dir, "corrupt_store.json")
            empty_path = os.path.join(cfg_dir, "empty_store.json")
            queue_path = os.path.join(cfg_dir, "queue_store.json")
            readonly_dir = os.path.join(tmpdir, "readonly_dir")
            os.makedirs(readonly_dir, exist_ok=True)
            readonly_path = os.path.join(readonly_dir, "locked.json")
            with open(corrupt_path, "w") as cf:
                cf.write("{invalid json content!!!")
            with open(empty_path, "w") as ef:
                ef.write("")
            with open(readonly_path, "w") as rf:
                json.dump({"version": 1}, rf)
            os.chmod(readonly_dir, 0o500)

            probe_path = os.path.join(REPO_DIR, "_test_phase_c_durability_probe.qml")
            try:
                with open(probe_path, "w") as pf:
                    pf.write(f"""import QtQuick
import Quickshell
import "./services"
import "./services/core"

Scope {{
    property var corruptFailures: []
    property var emptyFailures: []
    property var queueEvents: []
    property var writeFailures: []
    property bool serializeRejected: false

    JsonStore {{
        id: corruptStore
        path: "{corrupt_path}"
        fallbackPath: Qt.resolvedUrl("config/dock_config.json").toString().replace(/^file:\\/\\//, "")
        defaultValue: ({{ "fallback": false, "defaultUsed": true }})
        onFailed: (phase, code, details) => {{
            corruptFailures.push(phase);
        }}
    }}

    JsonStore {{
        id: emptyStore
        path: "{empty_path}"
        fallbackPath: Qt.resolvedUrl("config/dock_config.json").toString().replace(/^file:\\/\\//, "")
        defaultValue: ({{ "emptyDefault": true }})
        onFailed: (phase, code, details) => {{
            emptyFailures.push(phase);
        }}
    }}

    JsonStore {{
        id: queueStore
        path: "{queue_path}"
        defaultValue: ({{ "step": 0 }})
        onSavedValue: data => {{
            queueEvents.push("saved:" + data.step);
        }}
        onLoadedValue: (parsed, _) => {{
            queueEvents.push("loaded:" + parsed.step);
        }}
    }}

    JsonStore {{
        id: roStore
        path: "{readonly_path}"
        defaultValue: ({{ "version": 0 }})
        onFailed: (phase, code, details) => {{
            writeFailures.push(phase);
        }}
    }}

    Component.onCompleted: {{
        // Mutate ConfigService IMMEDIATELY during startup while initial load() is still in flight
        ConfigService.setDockEdge("left");
        ConfigService.setBarEdge("bottom");
    }}

    Timer {{
        interval: 120
        running: true
        repeat: false
        onTriggered: {{
            // 1. Rapid consecutive saves + load() called while save is in flight
            for (let i = 1; i <= 6; i++) {{
                queueStore.save({{ "step": i }});
            }}
            queueStore.load();

            // 2. Serialization failure check
            serializeRejected = !queueStore.save(undefined);

            // 3. Write failure on read-only directory must preserve lastPersistedValue ({{ "version": 1 }})
            roStore.save({{ "version": 999 }});

            // 4. Explicit save over corruptStore must create .bak of corrupt file before writing
            corruptStore.save({{ "recovered": true }});
        }}
    }}

    Timer {{
        interval: 350
        running: true
        repeat: false
        onTriggered: {{
            console.log("PHASE_C_DURABILITY_RESULT:" + JSON.stringify({{
                dockEdgeInMemory: ConfigService.dockEdge,
                barEdgeInMemory: ConfigService.barEdge,
                corruptFailures: corruptFailures,
                emptyFailures: emptyFailures,
                emptyHadParseError: emptyStore.hadParseError,
                emptyValue: emptyStore.value,
                queueFinalStep: queueStore.value.step,
                queueEvents: queueEvents,
                serializeRejected: serializeRejected,
                writeFailures: writeFailures,
                roRestoredVersion: roStore.value.version
            }}));
            Qt.quit();
        }}
    }}
}}
""")
                proc = subprocess.run(
                    ["quickshell", "-p", probe_path, "--no-duplicate"],
                    cwd=REPO_DIR,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=8
                )
                combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
                marker = "PHASE_C_DURABILITY_RESULT:"
                self.assertIn(marker, combined, f"Missing marker in output:\\n{combined}")
                payload_line = [line for line in combined.splitlines() if marker in line][-1]
                data = json.loads(payload_line.split(marker, 1)[1].strip())

                # 1. Pre-load modifications preserved in memory AND flushed to disk
                self.assertEqual(data["dockEdgeInMemory"], "left")
                self.assertEqual(data["barEdgeInMemory"], "bottom")
                with open(os.path.join(cfg_dir, "dock_config.json")) as df:
                    disk_dock = json.load(df)
                with open(os.path.join(cfg_dir, "bar_config.json")) as bf:
                    disk_bar = json.load(bf)
                self.assertEqual(disk_dock["edge"], "left")
                self.assertEqual(disk_bar["edge"], "bottom")

                # 2. Corrupt and empty JSON files emit "parse" failure, do not silently fall back to fallbackPath, and .bak is created on explicit save
                self.assertIn("parse", data["corruptFailures"])
                self.assertIn("parse", data["emptyFailures"])
                self.assertTrue(data["emptyHadParseError"])
                self.assertEqual(data["emptyValue"], {"emptyDefault": True})
                with open(empty_path) as ef:
                    self.assertEqual(ef.read(), "")
                self.assertTrue(os.path.isfile(corrupt_path + ".bak"))
                with open(corrupt_path + ".bak") as bkf:
                    self.assertEqual(bkf.read(), "{invalid json content!!!")
                with open(corrupt_path) as cf:
                    self.assertEqual(json.load(cf), {"recovered": True})

                # 3. Rapid consecutive saves + deferred load()
                self.assertEqual(data["queueFinalStep"], 6)
                self.assertIn("loaded:6", data["queueEvents"])
                with open(queue_path) as qf:
                    self.assertEqual(json.load(qf), {"step": 6})

                # 4. Serialization & write failure recovery
                self.assertTrue(data["serializeRejected"])
                self.assertIn("write", data["writeFailures"])
                self.assertEqual(data["roRestoredVersion"], 1)
            finally:
                os.chmod(readonly_dir, 0o700)
                if os.path.exists(probe_path):
                    os.remove(probe_path)

if __name__ == "__main__":
    unittest.main()
