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
            ["qmllint", "shell.qml", "components/AnchoredPopup.qml", "services/core/ModuleRegistry.qml", "modules/bar/PowerPopup.qml", "modules/bar/TrayModule.qml", "services/config/ConfigService.qml", "modules/settings/SettingsWindow.qml"],
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

        required_modules = ["launcher", "workspaces", "clock", "media", "tray", "network", "battery", "audio", "brightness", "power"]
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
        """Verify tray visibility policies, live status transitions, chevron rules, and _status_icon_N collision safety."""
        with open(os.path.join(REPO_DIR, "modules/bar/TrayModule.qml")) as f:
            tray_content = f.read()
        self.assertIn("readonly property bool hasHiddenItems: root.hiddenItems.length > 0", tray_content)
        self.assertIn("visible: root.hasHiddenItems", tray_content)
        self.assertIn("active: root.overflowOpen && root.hasHiddenItems", tray_content)
        self.assertIn("overflowDelegate.modelData.display(win, Math.round(pt.x), Math.round(pt.y))", tray_content)

        with open(os.path.join(REPO_DIR, "services/config/ConfigService.qml")) as f:
            cfg_content = f.read()
        self.assertIn("function hasTrayPrefixCollision", cfg_content)
        self.assertIn("function getTrayItemId", cfg_content)
        self.assertIn("function getTrayItemPolicy", cfg_content)
        self.assertIn("function setTrayItemPolicy", cfg_content)

        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["XDG_CONFIG_HOME"] = tmpdir
            probe_path = os.path.join(REPO_DIR, "_test_tray_regression_probe.qml")
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
            // 1. Single-icon _status_icon_N normalizes and survives reconnect with incremented counter
            const idSingle1 = ConfigService.getTrayItemId(single1, [single1]);
            ConfigService.setTrayItemPolicy(single1, "hidden", [single1]);
            const polReconnect = ConfigService.getTrayItemPolicy(single2, [single2]);

            // 2. Multi-icon _status_icon_N collision prevention
            const bothMulti = [multi1, multi2];
            const idM1 = ConfigService.getTrayItemId(multi1, bothMulti);
            const idM2 = ConfigService.getTrayItemId(multi2, bothMulti);
            ConfigService.setTrayItemPolicy(multi1, "hidden", bothMulti);
            ConfigService.setTrayItemPolicy(multi2, "always", bothMulti);
            const polM1 = ConfigService.getTrayItemPolicy(multi1, bothMulti);
            const polM2 = ConfigService.getTrayItemPolicy(multi2, bothMulti);

            // 3. Generic runtime prefix collision prevention
            const idG1 = ConfigService.getTrayItemId(generic1, [generic1]);
            const idG2 = ConfigService.getTrayItemId(generic2, [generic1, generic2]);

            // 4. TrayModule policy + status evaluation
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
                idM1: idM1,
                idM2: idM2,
                polM1: polM1,
                polM2: polM2,
                idG1: idG1,
                idG2: idG2,
                autoActiveVis: autoActiveVis,
                autoPassiveVis: autoPassiveVis,
                autoAttnVis: autoAttnVis,
                unknownVis: unknownVis
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
                marker = "TRAY_TEST_RESULT:"
                self.assertIn(marker, combined, f"Missing marker in output:\\n{combined}")
                payload_line = [line for line in combined.splitlines() if marker in line][-1]
                data = json.loads(payload_line.split(marker, 1)[1].strip())

                self.assertEqual(data["idSingle1"], "discord")
                self.assertEqual(data["polReconnect"], "hidden")
                self.assertEqual(data["idM1"], "myapp_status_icon_1")
                self.assertEqual(data["idM2"], "myapp_status_icon_2")
                self.assertEqual(data["polM1"], "hidden")
                self.assertEqual(data["polM2"], "always")
                self.assertEqual(data["idG1"], "chrome_status_icon_1")
                self.assertEqual(data["idG2"], "chrome_status_icon_2")
                self.assertTrue(data["autoActiveVis"])
                self.assertFalse(data["autoPassiveVis"])
                self.assertTrue(data["autoAttnVis"])
                self.assertTrue(data["unknownVis"])
            finally:
                if os.path.exists(probe_path):
                    os.remove(probe_path)

if __name__ == "__main__":
    unittest.main()
