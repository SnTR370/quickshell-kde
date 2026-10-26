#!/usr/bin/env python3
"""
Dock 2.0 Feature Blitz Automated Verification Suite
Validates:
1. Auto-hide reveal (180ms Easing.OutCubic) and hide (220ms Easing.InOutQuad) transitions.
2. Edge trigger hotspot thickness (8px) and interactive area margins (+24px).
3. DockItem popup stabilization (isPopupOpen scale/highlight preservation).
4. Tooltip dwell timer (320ms debounce) eliminating Wayland surface thrashing.
5. Active focused window indicator dot expansion.
6. Tactile click bounce animation.
7. Smooth hover transitions in WindowChooserPopup and DockMenu.
8. Preservation of all 4 dock edges and layer-shell contracts.
"""

import os
import unittest
import subprocess

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class TestDockBlitz(unittest.TestCase):

    def setUp(self):
        with open(os.path.join(REPO_DIR, "modules/dock/Dock.qml")) as f:
            self.dock_qml = f.read()
        with open(os.path.join(REPO_DIR, "modules/dock/DockItem.qml")) as f:
            self.dock_item_qml = f.read()
        with open(os.path.join(REPO_DIR, "modules/dock/WindowChooserPopup.qml")) as f:
            self.chooser_qml = f.read()
        with open(os.path.join(REPO_DIR, "modules/dock/DockMenu.qml")) as f:
            self.menu_qml = f.read()

    def test_01_qmllint_dock_modules(self):
        """Verify all dock QML files pass qmllint cleanly."""
        res = subprocess.run(
            ["qmllint", "modules/dock/Dock.qml", "modules/dock/DockItem.qml",
             "modules/dock/WindowChooserPopup.qml", "modules/dock/DockMenu.qml",
             "modules/dock/DockSeparator.qml"],
            cwd=REPO_DIR,
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0, f"qmllint failed: {res.stderr}")

    def test_02_autohide_transitions(self):
        """Verify snappy reveal (180ms) and smooth hide (220ms) transitions."""
        self.assertIn("duration: dockWindow.isRevealed ? 180 : 220", self.dock_qml)
        self.assertIn("easing.type: dockWindow.isRevealed ? Easing.OutCubic : Easing.InOutQuad", self.dock_qml)
        self.assertIn("duration: dockWindow.isRevealed ? 160 : 200", self.dock_qml)

    def test_03_hotspot_and_interactive_bounds(self):
        """Verify edge trigger thickness (8px) and interactive area bleed cushion (+24px)."""
        self.assertIn("height: dockWindow.isVertical ? Math.max(180, dockSurface.implicitHeight) : 8", self.dock_qml)
        self.assertIn("width: dockWindow.isVertical ? 8 : Math.max(180, dockSurface.implicitWidth)", self.dock_qml)
        self.assertIn("Math.max(dockSurface.implicitWidth + 24, 180)", self.dock_qml)
        self.assertIn("Math.max(dockSurface.implicitHeight + 24, 180)", self.dock_qml)

    def test_04_popup_stabilization_and_anti_flicker(self):
        """Verify popup ownership stabilization prevents icon shrink/jitter and suppresses tooltips."""
        self.assertIn("readonly property bool isPopupOpen: menuOpen || chooserOpen", self.dock_item_qml)
        self.assertIn("root.isPopupOpen ? Theme.alpha(Theme.primary, 0.22)", self.dock_item_qml)
        self.assertIn("((dockItemMouse.containsMouse || root.isPopupOpen) ? 1.15 : 1.0)", self.dock_item_qml)
        self.assertIn("!(root.parentWindowRef && root.parentWindowRef.hasActivePopup)", self.dock_item_qml)

    def test_05_tooltip_dwell_debounce(self):
        """Verify tooltip dwell timer debounces rapid pointer moves across dock items."""
        self.assertIn("Timer {\n        id: tooltipDwellTimer\n        interval: 320", self.dock_item_qml)
        self.assertIn("tooltipDwellTimer.restart()", self.dock_item_qml)
        self.assertIn("tooltipDwellTimer.stop()", self.dock_item_qml)
        self.assertIn("root.tooltipActive && dockItemMouse.containsMouse", self.dock_item_qml)

    def test_06_active_focused_window_indicator(self):
        """Verify active focused window indicator expands width and shifts color."""
        self.assertIn("readonly property bool isCurrentAppActive:", self.dock_item_qml)
        self.assertIn("root.isCurrentAppActive ? 10 :", self.dock_item_qml)
        self.assertIn("root.isCurrentAppActive ? Theme.accent : Theme.primary", self.dock_item_qml)

    def test_07_tactile_click_bounce(self):
        """Verify tactile click bounce animation is triggered on mouse click without breaking scale binding."""
        self.assertIn("SequentialAnimation {\n        id: clickBounceAnim", self.dock_item_qml)
        self.assertIn('property: "bounceScale"', self.dock_item_qml)
        self.assertIn("* root.bounceScale", self.dock_item_qml)
        self.assertIn("clickBounceAnim.restart()", self.dock_item_qml)

    def test_08_popup_smooth_hover_animations(self):
        """Verify WindowChooserPopup and DockMenu have smooth color transitions."""
        self.assertIn("Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }", self.chooser_qml)
        self.assertIn("Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }", self.menu_qml)

    def test_09_runtime_click_bounce_magnification_preservation(self):
        """Live QML Runtime Test: Verify clicking a DockItem animates bounceScale and preserves reactive hover/popup magnification without breaking iconContainer.scale binding."""
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["XDG_CONFIG_HOME"] = tmpdir
            probe_path = os.path.join(REPO_DIR, "_test_dock_bounce_probe.qml")
            try:
                with open(probe_path, "w") as pf:
                    pf.write("""import QtQuick
import Quickshell
import "./services"
import "./modules/dock"

Scope {
    DockItem {
        id: item
        appId: "org.kde.konsole"
    }

    Timer {
        interval: 150
        running: true
        repeat: false
        onTriggered: {
            const initialScale = item.targetScale;
            // Open popup -> scale must reactively become 1.15
            item.menuOpen = true;
            const scalePopupOpen = item.targetScale;
            // Trigger bounce animation via bounceScale
            item.bounceScale = 0.86;
            const scaleDuringBounce = item.targetScale;
            item.bounceScale = 1.0;
            const scaleAfterBouncePopupStillOpen = item.targetScale;
            // Close popup -> scale must reactively return to 1.0 (proving binding is intact!)
            item.menuOpen = false;
            const scaleAfterPopupClosed = item.targetScale;
            // Re-open popup -> scale must reactively become 1.15 again
            item.chooserOpen = true;
            const scaleReopened = item.targetScale;

            console.log("DOCK_BOUNCE_RUNTIME:" + JSON.stringify({
                initialScale: initialScale,
                scalePopupOpen: scalePopupOpen,
                scaleDuringBounce: Number(scaleDuringBounce.toFixed(3)),
                scaleAfterBouncePopupStillOpen: scaleAfterBouncePopupStillOpen,
                scaleAfterPopupClosed: scaleAfterPopupClosed,
                scaleReopened: scaleReopened
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
                marker = "DOCK_BOUNCE_RUNTIME:"
                self.assertIn(marker, combined, f"Missing marker in output:\n{combined}")
                payload_line = [line for line in combined.splitlines() if marker in line][-1]
                data = json.loads(payload_line.split(marker, 1)[1].strip())

                self.assertAlmostEqual(data["initialScale"], 1.0, places=2)
                self.assertAlmostEqual(data["scalePopupOpen"], 1.15, places=2)
                self.assertAlmostEqual(data["scaleDuringBounce"], round(1.15 * 0.86, 3), places=2)
                self.assertAlmostEqual(data["scaleAfterBouncePopupStillOpen"], 1.15, places=2)
                self.assertAlmostEqual(data["scaleAfterPopupClosed"], 1.0, places=2)
                self.assertAlmostEqual(data["scaleReopened"], 1.15, places=2)
            finally:
                if os.path.exists(probe_path):
                    os.remove(probe_path)

    def test_10_static_window_cycling_and_pinned_reordering_contracts(self):
        """Static verification of WindowService cycling, ConfigService reorder API, and DockItem/DockMenu bindings."""
        with open(os.path.join(REPO_DIR, "services/kwin/WindowService.qml")) as f:
            win_service_qml = f.read()
        with open(os.path.join(REPO_DIR, "services/config/ConfigService.qml")) as f:
            cfg_service_qml = f.read()
        with open(os.path.join(REPO_DIR, "services/applications/ApplicationService.qml")) as f:
            app_service_qml = f.read()

        # Feature 1: Window cycling contracts
        self.assertIn("function cycleAppWindows(appId, reverse)", win_service_qml)
        self.assertIn("onWheel: wheel =>", self.dock_item_qml)
        self.assertIn("function handleWheel(delta)", self.dock_item_qml)
        self.assertIn("WindowService.cycleAppWindows(root.appId, delta < 0)", self.dock_item_qml)

        # Feature 2: Pinned app ordering contracts
        self.assertIn("function reorderDockPinned(fromIndex, toIndex)", cfg_service_qml)
        self.assertIn("function reorderDockPinnedByAppId(fromAppId, toAppId)", cfg_service_qml)
        self.assertIn("function moveDockPinned(appId, direction)", cfg_service_qml)
        self.assertIn("function sanitizeDockPinned(list)", cfg_service_qml)
        self.assertIn("function movePinnedApp(appId, direction)", app_service_qml)
        self.assertIn("function reorderPinnedApps(fromIndexOrAppId, toIndexOrAppId)", app_service_qml)
        self.assertIn('root.isVerticalDock ? "Move Up" : "Move Left"', self.menu_qml)
        self.assertIn('root.isVerticalDock ? "Move Down" : "Move Right"', self.menu_qml)

    def test_11_runtime_window_cycling_forward_reverse_and_edge_cases(self):
        """Live QML Runtime Test: Verify forward/reverse wheel window cycling, 0/1/multi windows, window close/open during cycle, and stale indices."""
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["XDG_CONFIG_HOME"] = tmpdir
            probe_path = os.path.join(REPO_DIR, "_test_dock_cycling_probe.qml")
            try:
                with open(probe_path, "w") as pf:
                    pf.write("""import QtQuick
import Quickshell
import "./services"
import "./modules/dock"

Scope {
    DockItem {
        id: ffItem
        appId: "firefox"
    }
    DockItem {
        id: konsoleItem
        appId: "org.kde.konsole"
    }
    DockItem {
        id: dolphinItem
        appId: "org.kde.dolphin"
    }

    Timer {
        interval: 250
        running: true
        repeat: false
        onTriggered: {
            WindowService.outputsOverride = ["eDP-1"];
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
                },
                {
                    id: "org.kde.dolphin",
                    name: "Dolphin",
                    icon: "system-file-manager",
                    startupWMClass: "org.kde.dolphin",
                    execBinary: "dolphin",
                    aliases: ["org.kde.dolphin", "dolphin"]
                }
            ];
            ApplicationService.loading = false;

            const wFF1 = "0_{11111111-1111-1111-1111-111111111111}";
            const wFF2 = "0_{22222222-2222-2222-2222-222222222222}";
            const wFF3 = "0_{33333333-3333-3333-3333-333333333333}";
            const wFF4 = "0_{44444444-4444-4444-4444-444444444444}";
            const wKon = "0_{55555555-5555-5555-5555-555555555555}";

            const rawInitial = [
                '[Argument: (sssida{sv}) "' + wFF1 + '", "FF 1", "org.mozilla.firefox", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "' + wFF2 + '", "FF 2", "org.mozilla.firefox", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "' + wFF3 + '", "FF 3", "org.mozilla.firefox", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "' + wKon + '", "Konsole 1", "utilities-terminal", 100, 1.0, [Argument: a{sv} {}]]',
                '===KWIN_META:' + wFF1 + '\\torg.mozilla.firefox\\torg.mozilla.firefox\\t===',
                '===KWIN_META:' + wFF2 + '\\torg.mozilla.firefox\\torg.mozilla.firefox\\t===',
                '===KWIN_META:' + wFF3 + '\\torg.mozilla.firefox\\torg.mozilla.firefox\\t===',
                '===KWIN_META:' + wKon + '\\torg.kde.konsole\\torg.kde.konsole\\t==='
            ].join("\\n");
            WindowService.handleScannerOutput(rawInitial);
            WindowService.activeWindowId = "";
            WindowService.lastExecutedAction = null;

            // 1. Zero windows: Dolphin has 0 windows -> wheel up/down must return false and NOT launch or activate anything
            const zeroUp = dolphinItem.handleWheel(120);
            const zeroDown = dolphinItem.handleWheel(-120);
            const zeroDirect = WindowService.cycleAppWindows("org.kde.dolphin", false);
            const actionAfterZero = WindowService.lastExecutedAction;

            // 2. Single window: Konsole has 1 window -> both wheel up and wheel down activate wKon
            const singleUp = konsoleItem.handleWheel(120);
            const activeAfterSingleUp = WindowService.activeWindowId;
            WindowService.activeWindowId = "";
            const singleDown = konsoleItem.handleWheel(-120);
            const activeAfterSingleDown = WindowService.activeWindowId;

            // 3. Multi-window forward cycling via wheel up (delta > 0)
            WindowService.activeWindowId = "";
            WindowService.appCycleIndices = ({});
            WindowService.appCycleWindowIds = ({});
            const fwd1 = ffItem.handleWheel(120);
            const actFwd1 = WindowService.activeWindowId;
            const fwd2 = ffItem.handleWheel(120);
            const actFwd2 = WindowService.activeWindowId;
            const fwd3 = ffItem.handleWheel(120);
            const actFwd3 = WindowService.activeWindowId;
            const fwd4Wrap = ffItem.handleWheel(120);
            const actFwd4Wrap = WindowService.activeWindowId;

            // 4. Multi-window reverse cycling via wheel down (delta < 0) from currently active wFF1
            const rev1 = ffItem.handleWheel(-120);
            const actRev1 = WindowService.activeWindowId;
            const rev2 = ffItem.handleWheel(-120);
            const actRev2 = WindowService.activeWindowId;
            const rev3 = ffItem.handleWheel(-120);
            const actRev3 = WindowService.activeWindowId;

            // 5. Stale cycling index recovery
            WindowService.activeWindowId = "";
            WindowService.appCycleWindowIds = ({});
            WindowService.appCycleIndices["org.mozilla.firefox"] = 99; // 99 % 3 === 0 -> wFF1
            const stalePos = ffItem.handleWheel(120);
            const actStalePos = WindowService.activeWindowId;

            WindowService.activeWindowId = "";
            WindowService.appCycleWindowIds = ({});
            WindowService.appCycleIndices["org.mozilla.firefox"] = -4; // ((-4 % 3) + 3) % 3 === 2 -> wFF3
            const staleNeg = ffItem.handleWheel(120);
            const actStaleNeg = WindowService.activeWindowId;

            // 6. Window closes during cycling: focus wFF2 (idx 1), then wFF2 closes -> next forward cycle selects wFF3
            WindowService.activateWindow(wFF2);
            const rawAfterCloseFF2 = [
                '[Argument: (sssida{sv}) "' + wFF1 + '", "FF 1", "org.mozilla.firefox", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "' + wFF3 + '", "FF 3", "org.mozilla.firefox", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "' + wKon + '", "Konsole 1", "utilities-terminal", 100, 1.0, [Argument: a{sv} {}]]'
            ].join("\\n");
            WindowService.handleScannerOutput(rawAfterCloseFF2);
            const activeAfterFF2Closed = WindowService.activeWindowId;
            const cycleAfterClose = ffItem.handleWheel(120);
            const actAfterCloseCycle = WindowService.activeWindowId;

            // 7. Window opens during cycling: wFF4 opens while wFF3 is active -> next forward cycle selects wFF4
            const rawAfterOpenFF4 = [
                '[Argument: (sssida{sv}) "' + wFF1 + '", "FF 1", "org.mozilla.firefox", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "' + wFF3 + '", "FF 3", "org.mozilla.firefox", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "' + wFF4 + '", "FF 4", "org.mozilla.firefox", 100, 1.0, [Argument: a{sv} {}]]',
                '===KWIN_META:' + wFF4 + '\\torg.mozilla.firefox\\torg.mozilla.firefox\\t==='
            ].join("\\n");
            WindowService.handleScannerOutput(rawAfterOpenFF4);
            const cycleAfterOpen = ffItem.handleWheel(120);
            const actAfterOpenCycle = WindowService.activeWindowId;

            console.log("DOCK_CYCLING_RUNTIME:" + JSON.stringify({
                zeroUp: zeroUp,
                zeroDown: zeroDown,
                zeroDirect: zeroDirect,
                actionAfterZero: actionAfterZero,
                singleUp: singleUp,
                activeAfterSingleUp: activeAfterSingleUp,
                singleDown: singleDown,
                activeAfterSingleDown: activeAfterSingleDown,
                actFwd1: actFwd1,
                actFwd2: actFwd2,
                actFwd3: actFwd3,
                actFwd4Wrap: actFwd4Wrap,
                actRev1: actRev1,
                actRev2: actRev2,
                actRev3: actRev3,
                actStalePos: actStalePos,
                actStaleNeg: actStaleNeg,
                activeAfterFF2Closed: activeAfterFF2Closed,
                actAfterCloseCycle: actAfterCloseCycle,
                actAfterOpenCycle: actAfterOpenCycle,
                ffIsCurrentActive: ffItem.isCurrentAppActive
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
                marker = "DOCK_CYCLING_RUNTIME:"
                self.assertIn(marker, combined, f"Missing marker in output:\n{combined}")
                payload_line = [line for line in combined.splitlines() if marker in line][-1]
                data = json.loads(payload_line.split(marker, 1)[1].strip())

                c_ff1 = "11111111-1111-1111-1111-111111111111"
                c_ff2 = "22222222-2222-2222-2222-222222222222"
                c_ff3 = "33333333-3333-3333-3333-333333333333"
                c_ff4 = "44444444-4444-4444-4444-444444444444"
                c_kon = "55555555-5555-5555-5555-555555555555"

                # Zero windows
                self.assertFalse(data["zeroUp"])
                self.assertFalse(data["zeroDown"])
                self.assertFalse(data["zeroDirect"])
                self.assertIsNone(data["actionAfterZero"])

                # Single window
                self.assertTrue(data["singleUp"])
                self.assertEqual(data["activeAfterSingleUp"], c_kon)
                self.assertTrue(data["singleDown"])
                self.assertEqual(data["activeAfterSingleDown"], c_kon)

                # Forward cycling + wraparound
                self.assertEqual(data["actFwd1"], c_ff1)
                self.assertEqual(data["actFwd2"], c_ff2)
                self.assertEqual(data["actFwd3"], c_ff3)
                self.assertEqual(data["actFwd4Wrap"], c_ff1)

                # Reverse cycling
                self.assertEqual(data["actRev1"], c_ff3)
                self.assertEqual(data["actRev2"], c_ff2)
                self.assertEqual(data["actRev3"], c_ff1)

                # Stale indices
                self.assertEqual(data["actStalePos"], c_ff1)
                self.assertEqual(data["actStaleNeg"], c_ff3)

                # Window closes during cycling
                self.assertEqual(data["activeAfterFF2Closed"], "")
                self.assertEqual(data["actAfterCloseCycle"], c_ff3)

                # Window opens during cycling
                self.assertEqual(data["actAfterOpenCycle"], c_ff4)
                self.assertTrue(data["ffIsCurrentActive"])
            finally:
                if os.path.exists(probe_path):
                    os.remove(probe_path)

    def test_12_runtime_pinned_ordering_persistence_and_edge_cases(self):
        """Live QML Runtime Test: Verify pinned app reordering, DockMenu Move Left/Right, boundary/invalid no-ops, duplicate prevention, uninstalled preservation, repeated pin/unpin, and reload persistence."""
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["XDG_CONFIG_HOME"] = tmpdir
            probe_path = os.path.join(REPO_DIR, "_test_dock_reorder_probe.qml")
            reload_probe_path = os.path.join(REPO_DIR, "_test_dock_reorder_reload_probe.qml")
            try:
                with open(probe_path, "w") as pf:
                    pf.write("""import QtQuick
import Quickshell
import "./services"
import "./modules/dock"

Scope {
    property var _pinned: ConfigService.dockPinned

    DockMenu {
        id: horizMenu
        edge: "bottom"
        appId: "org.kde.dolphin"
        isPinned: true
    }

    DockMenu {
        id: vertMenu
        edge: "left"
        appId: "firefox"
        isPinned: true
    }

    Timer {
        interval: 250
        running: true
        repeat: false
        onTriggered: {
            // Mock installed applications where "code" is uninstalled, while dolphin, konsole, firefox, systemsettings are installed
            ApplicationService.applications = [
                { id: "org.kde.dolphin", name: "Dolphin", icon: "system-file-manager", aliases: ["org.kde.dolphin", "dolphin"] },
                { id: "org.kde.konsole", name: "Konsole", icon: "utilities-terminal", aliases: ["org.kde.konsole", "konsole"] },
                { id: "org.mozilla.firefox", name: "Firefox", icon: "org.mozilla.firefox", aliases: ["org.mozilla.firefox", "firefox"] },
                { id: "systemsettings", name: "System Settings", icon: "preferences-system", aliases: ["systemsettings"] }
            ];
            ApplicationService.loading = false;

            const initialRaw = ConfigService.dockPinned.slice();
            const initialVisible = ApplicationService.pinnedApps.slice();

            // 1. Boundary checks: first item ("org.kde.dolphin") cannot move left; last visible item ("systemsettings") cannot move right
            const canFirstMoveLeft = horizMenu.canMoveLeft;
            const canFirstMoveRight = horizMenu.canMoveRight;
            const firstMoveLeftRes = horizMenu.moveLeft();
            const lastMoveRightRes = ApplicationService.movePinnedApp("systemsettings", "right");

            // 2. Invalid indices and unpinned/invalid app IDs must return false and preserve order
            const invIdxNeg = ConfigService.reorderDockPinned(-1, 1);
            const invIdxOob = ConfigService.reorderDockPinned(0, 99);
            const invIdxSame = ConfigService.reorderDockPinned(1, 1);
            const invIdxFloat = ConfigService.reorderDockPinned(0.5, 1);
            const unpinnedMove = ApplicationService.movePinnedApp("unpinned.ghost", "left");
            const emptyMove = ConfigService.moveDockPinned("", "right");
            const invalidDirMove = ConfigService.moveDockPinned("firefox", "diagonal");
            const afterInvalidRaw = ConfigService.dockPinned.slice();

            // 3. Move "org.kde.dolphin" right via horizontal DockMenu -> ["org.kde.konsole", "org.kde.dolphin", "firefox", "systemsettings"]
            const moveDolphinRight = horizMenu.moveRight();
            const visAfterDolphinRight = ApplicationService.pinnedApps.slice();

            // 4. Move "firefox" right via vertical DockMenu -> swaps past uninstalled "code" with "systemsettings" without losing "code"
            const vertIsVertical = vertMenu.isVerticalDock;
            const moveFirefoxRight = vertMenu.moveRight();
            const visAfterFirefoxRight = ApplicationService.pinnedApps.slice();
            const rawAfterFirefoxRight = ConfigService.dockPinned.slice();

            // 5. Duplicate prevention & normalization
            const sanitizedDupes = ConfigService.sanitizeDockPinned(["firefox", "FIREFOX.desktop", "org.kde.dolphin", "org.kde.dolphin.desktop", "", "  ", "env"]);

            // 6. Repeated pin/unpin of "org.kde.konsole" (using .desktop suffix too)
            ApplicationService.togglePin("org.kde.konsole.desktop"); // unpins
            const visAfterUnpinKonsole = ApplicationService.pinnedApps.slice();
            ApplicationService.togglePin("org.kde.konsole"); // pins at end
            ApplicationService.togglePin("org.kde.konsole"); // unpins again
            ApplicationService.togglePin("org.kde.konsole"); // pins at end again
            const visAfterRePinKonsole = ApplicationService.pinnedApps.slice();

            // 7. Move "org.kde.konsole" left once so final visible order is:
            // ["org.kde.dolphin", "systemsettings", "org.kde.konsole", "firefox"]
            const moveKonsoleLeft = ApplicationService.movePinnedApp("org.kde.konsole", "left");
            const finalVisible = ApplicationService.pinnedApps.slice();
            const finalRaw = ConfigService.dockPinned.slice();

            console.log("DOCK_REORDER_RUNTIME:" + JSON.stringify({
                initialRaw: initialRaw,
                initialVisible: initialVisible,
                canFirstMoveLeft: canFirstMoveLeft,
                canFirstMoveRight: canFirstMoveRight,
                firstMoveLeftRes: firstMoveLeftRes,
                lastMoveRightRes: lastMoveRightRes,
                invIdxNeg: invIdxNeg,
                invIdxOob: invIdxOob,
                invIdxSame: invIdxSame,
                invIdxFloat: invIdxFloat,
                unpinnedMove: unpinnedMove,
                emptyMove: emptyMove,
                invalidDirMove: invalidDirMove,
                afterInvalidRaw: afterInvalidRaw,
                moveDolphinRight: moveDolphinRight,
                visAfterDolphinRight: visAfterDolphinRight,
                vertIsVertical: vertIsVertical,
                moveFirefoxRight: moveFirefoxRight,
                visAfterFirefoxRight: visAfterFirefoxRight,
                rawAfterFirefoxRight: rawAfterFirefoxRight,
                sanitizedDupes: sanitizedDupes,
                visAfterUnpinKonsole: visAfterUnpinKonsole,
                visAfterRePinKonsole: visAfterRePinKonsole,
                moveKonsoleLeft: moveKonsoleLeft,
                finalVisible: finalVisible,
                finalRaw: finalRaw
            }));
            quitTimer.running = true;
        }
    }
    Timer {
        id: quitTimer
        interval: 200
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
                marker = "DOCK_REORDER_RUNTIME:"
                self.assertIn(marker, combined, f"Missing marker in output:\n{combined}")
                payload_line = [line for line in combined.splitlines() if marker in line][-1]
                data = json.loads(payload_line.split(marker, 1)[1].strip())

                self.assertEqual(data["initialRaw"], ["org.kde.dolphin", "org.kde.konsole", "firefox", "code", "systemsettings"])
                self.assertEqual(data["initialVisible"], ["org.kde.dolphin", "org.kde.konsole", "firefox", "systemsettings"])

                # Boundary & invalid operations
                self.assertFalse(data["canFirstMoveLeft"])
                self.assertTrue(data["canFirstMoveRight"])
                self.assertFalse(data["firstMoveLeftRes"])
                self.assertFalse(data["lastMoveRightRes"])
                self.assertFalse(data["invIdxNeg"])
                self.assertFalse(data["invIdxOob"])
                self.assertFalse(data["invIdxSame"])
                self.assertFalse(data["invIdxFloat"])
                self.assertFalse(data["unpinnedMove"])
                self.assertFalse(data["emptyMove"])
                self.assertFalse(data["invalidDirMove"])
                self.assertEqual(data["afterInvalidRaw"], data["initialRaw"])

                # Reordering & uninstalled preservation
                self.assertTrue(data["moveDolphinRight"])
                self.assertEqual(data["visAfterDolphinRight"], ["org.kde.konsole", "org.kde.dolphin", "firefox", "systemsettings"])
                self.assertTrue(data["vertIsVertical"])
                self.assertTrue(data["moveFirefoxRight"])
                self.assertEqual(data["visAfterFirefoxRight"], ["org.kde.konsole", "org.kde.dolphin", "systemsettings", "firefox"])
                self.assertIn("code", data["rawAfterFirefoxRight"])

                # Deduplication & normalization
                self.assertEqual(data["sanitizedDupes"], ["firefox", "org.kde.dolphin"])

                # Repeated pin/unpin & final reorder
                self.assertNotIn("org.kde.konsole", data["visAfterUnpinKonsole"])
                self.assertEqual(data["visAfterRePinKonsole"], ["org.kde.dolphin", "systemsettings", "firefox", "org.kde.konsole"])
                self.assertTrue(data["moveKonsoleLeft"])
                self.assertEqual(data["finalVisible"], ["org.kde.dolphin", "systemsettings", "org.kde.konsole", "firefox"])
                self.assertIn("code", data["finalRaw"])

                # Verify on-disk dock_config.json was written
                dock_cfg_file = os.path.join(tmpdir, "quickshell-kde", "dock_config.json")
                self.assertTrue(os.path.isfile(dock_cfg_file), "dock_config.json must be persisted to XDG_CONFIG_HOME")
                with open(dock_cfg_file) as df:
                    persisted_json = json.load(df)
                self.assertEqual(persisted_json["pinned"], data["finalRaw"])

                # Process 2: Fresh Quickshell instance verifying order survives shell reload
                with open(reload_probe_path, "w") as rpf:
                    rpf.write("""import QtQuick
import Quickshell
import "./services"

Scope {
    property var _pinned: ConfigService.dockPinned
    Timer {
        interval: 250
        running: true
        repeat: false
        onTriggered: {
            ApplicationService.applications = [
                { id: "org.kde.dolphin", name: "Dolphin", icon: "system-file-manager", aliases: ["org.kde.dolphin", "dolphin"] },
                { id: "org.kde.konsole", name: "Konsole", icon: "utilities-terminal", aliases: ["org.kde.konsole", "konsole"] },
                { id: "org.mozilla.firefox", name: "Firefox", icon: "org.mozilla.firefox", aliases: ["org.mozilla.firefox", "firefox"] },
                { id: "systemsettings", name: "System Settings", icon: "preferences-system", aliases: ["systemsettings"] }
            ];
            ApplicationService.loading = false;
            console.log("DOCK_RELOAD_RUNTIME:" + JSON.stringify({
                reloadedRaw: ConfigService.dockPinned,
                reloadedVisible: ApplicationService.pinnedApps
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
                reload_marker = "DOCK_RELOAD_RUNTIME:"
                self.assertIn(reload_marker, reload_combined, f"Missing reload marker:\n{reload_combined}")
                reload_line = [line for line in reload_combined.splitlines() if reload_marker in line][-1]
                reload_data = json.loads(reload_line.split(reload_marker, 1)[1].strip())

                self.assertEqual(reload_data["reloadedRaw"], data["finalRaw"])
                self.assertEqual(reload_data["reloadedVisible"], ["org.kde.dolphin", "systemsettings", "org.kde.konsole", "firefox"])
            finally:
                for p in (probe_path, reload_probe_path):
                    if os.path.exists(p):
                        os.remove(p)

    def test_13_static_dock_drag_and_drop_contracts(self):
        """Static verification of Qt Quick native Drag/DropArea facilities, service reuse, and autohide drag protection."""
        with open(os.path.join(REPO_DIR, "modules/dock/DockSeparator.qml")) as f:
            sep_qml = f.read()
        with open(os.path.join(REPO_DIR, "services/applications/ApplicationService.qml")) as f:
            app_service_qml = f.read()

        # Qt Quick native Drag and DropArea in DockItem and DockSeparator
        self.assertIn("DropArea {", self.dock_item_qml)
        self.assertIn('keys: ["quickshell-dock-item"]', self.dock_item_qml)
        self.assertIn("Drag.active: root.dragging", self.dock_item_qml)
        self.assertIn("Drag.source: root", self.dock_item_qml)
        self.assertIn("dragProxy.Drag.drop()", self.dock_item_qml)
        self.assertIn("dragProxy.Drag.cancel()", self.dock_item_qml)
        self.assertIn("DropArea {", sep_qml)
        self.assertIn('keys: ["quickshell-dock-item"]', sep_qml)

        # Service reuse without duplicating persistence/identity logic
        self.assertIn("ApplicationService.reorderPinnedApps", self.dock_item_qml)
        self.assertIn("ApplicationService.pinAppAt", self.dock_item_qml)
        self.assertIn("function pinAppAt(appId, targetIndex)", app_service_qml)
        self.assertIn("if (!togglePin(appId)) return false;", app_service_qml)
        self.assertIn("reorderPinnedApps(newIdx, clamped);", app_service_qml)

        # Autohide protection during active drag in Dock.qml
        self.assertIn("property var activeDragItem: null", self.dock_qml)
        self.assertIn("readonly property bool isDragging: activeDragItem !== null", self.dock_qml)
        self.assertIn("|| isDragging", self.dock_qml)

    def test_14_runtime_horizontal_and_vertical_drag_reordering_and_persistence(self):
        """Real QML Drag Event Test: Verify horizontal and vertical Dock drag-to-reorder across multiple positions in both directions, single-item Dock no-op, uninstalled preservation, and reload persistence."""
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["XDG_CONFIG_HOME"] = tmpdir
            env["QT_QPA_PLATFORM"] = "offscreen"
            probe_path = os.path.join(REPO_DIR, "_test_dock_dnd_reorder_probe.qml")
            reload_probe_path = os.path.join(REPO_DIR, "_test_dock_dnd_reorder_reload_probe.qml")
            try:
                with open(probe_path, "w") as pf:
                    pf.write("""import QtQuick
import QtQuick.Layouts
import QtTest
import Quickshell
import "./services"
import "./modules/dock"

FloatingWindow {
    id: win
    implicitWidth: 800
    implicitHeight: 600
    visible: true

    property string edge: ConfigService.dockEdge
    readonly property bool isVertical: edge === "left" || edge === "right"
    property var activePopupItem: null
    readonly property bool hasActivePopup: activePopupItem !== null
    property var activeDragItem: null
    readonly property bool isDragging: activeDragItem !== null
    property bool isRevealed: true

    RowLayout {
        id: horizLayout
        visible: !win.isVertical
        x: 20
        y: 20
        spacing: 4

        Repeater {
            id: horizPinnedRep
            model: ApplicationService.pinnedApps
            DockItem {
                required property var modelData
                parentWindowRef: win
                appId: modelData
                app: ApplicationService.getAppById(modelData)
            }
        }
    }

    ColumnLayout {
        id: vertLayout
        visible: win.isVertical
        x: 20
        y: 120
        spacing: 4

        Repeater {
            id: vertPinnedRep
            model: ApplicationService.pinnedApps
            DockItem {
                required property var modelData
                parentWindowRef: win
                appId: modelData
                app: ApplicationService.getAppById(modelData)
            }
        }
    }

    TestCase {
        id: tc
        name: "DockDragReorderSuite"
        when: false

        function dragBetween(srcItem, dstItem) {
            mousePress(srcItem, srcItem.width / 2, srcItem.height / 2, Qt.LeftButton);
            mouseMove(srcItem, srcItem.width / 2 + 8, srcItem.height / 2 + 8);
            const pt = srcItem.mapFromItem(dstItem, dstItem.width / 2, dstItem.height / 2);
            mouseMove(srcItem, pt.x, pt.y);
            mouseRelease(srcItem, pt.x, pt.y, Qt.LeftButton);
            wait(25);
        }

        function runTests() {
            wait(25);
            const initialVis = ApplicationService.pinnedApps.slice();
            const initialRaw = ConfigService.dockPinned.slice();

            // 1. Horizontal (bottom edge): Drag index 0 ("org.kde.dolphin") -> index 3 ("systemsettings")
            ConfigService.setDockEdge("bottom");
            wait(20);
            dragBetween(horizPinnedRep.itemAt(0), horizPinnedRep.itemAt(3));
            const afterHorizFwdMulti = ApplicationService.pinnedApps.slice();

            // 2. Horizontal (top edge): Drag index 3 ("org.kde.dolphin") -> index 1 ("firefox")
            ConfigService.setDockEdge("top");
            wait(20);
            dragBetween(horizPinnedRep.itemAt(3), horizPinnedRep.itemAt(1));
            const afterHorizRevMulti = ApplicationService.pinnedApps.slice();

            // 3. Horizontal single-step right: Drag index 0 ("org.kde.konsole") -> index 1 ("org.kde.dolphin")
            dragBetween(horizPinnedRep.itemAt(0), horizPinnedRep.itemAt(1));
            const afterHorizStepRight = ApplicationService.pinnedApps.slice();

            // 4. Vertical (left edge): Drag index 0 ("org.kde.dolphin") down to index 2 ("firefox")
            ConfigService.setDockEdge("left");
            wait(25);
            dragBetween(vertPinnedRep.itemAt(0), vertPinnedRep.itemAt(2));
            const afterVertDown = ApplicationService.pinnedApps.slice();

            // 5. Vertical (right edge): Drag index 3 ("systemsettings") up to index 0 ("org.kde.konsole")
            ConfigService.setDockEdge("right");
            wait(25);
            dragBetween(vertPinnedRep.itemAt(3), vertPinnedRep.itemAt(0));
            const afterVertUp = ApplicationService.pinnedApps.slice();
            const rawAfterMulti = ConfigService.dockPinned.slice();

            // 6. Single-item Dock test: temporarily set dockPinned to ["org.kde.dolphin"]
            ConfigService.dockPinned = ["org.kde.dolphin"];
            wait(25);
            const singleItem = vertPinnedRep.itemAt(0);
            mousePress(singleItem, 26, 26, Qt.LeftButton);
            mouseMove(singleItem, 26, 80);
            mouseRelease(singleItem, 26, 80, Qt.LeftButton);
            wait(20);
            const afterSingleDrag = ApplicationService.pinnedApps.slice();

            // Restore multi-item final state and persist for reload verification
            ConfigService.dockPinned = rawAfterMulti;
            ConfigService.saveDockConfig();
            wait(50);

            console.log("DOCK_DND_REORDER_RESULT:" + JSON.stringify({
                initialVis: initialVis,
                initialRaw: initialRaw,
                afterHorizFwdMulti: afterHorizFwdMulti,
                afterHorizRevMulti: afterHorizRevMulti,
                afterHorizStepRight: afterHorizStepRight,
                afterVertDown: afterVertDown,
                afterVertUp: afterVertUp,
                rawAfterMulti: rawAfterMulti,
                afterSingleDrag: afterSingleDrag
            }));
        }
    }

    Timer {
        interval: 250
        running: true
        repeat: false
        onTriggered: {
            WindowService.outputsOverride = ["eDP-1"];
            ApplicationService.applications = [
                { id: "org.kde.dolphin", name: "Dolphin", icon: "system-file-manager", aliases: ["org.kde.dolphin", "dolphin"] },
                { id: "org.kde.konsole", name: "Konsole", icon: "utilities-terminal", aliases: ["org.kde.konsole", "konsole"] },
                { id: "org.mozilla.firefox", name: "Firefox", icon: "org.mozilla.firefox", aliases: ["org.mozilla.firefox", "firefox"] },
                { id: "systemsettings", name: "System Settings", icon: "preferences-system", aliases: ["systemsettings"] }
            ];
            ApplicationService.loading = false;
            tc.runTests();
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
                    timeout=8
                )
                combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
                marker = "DOCK_DND_REORDER_RESULT:"
                self.assertIn(marker, combined, f"Missing marker in output:\n{combined}")
                payload_line = [line for line in combined.splitlines() if marker in line][-1]
                data = json.loads(payload_line.split(marker, 1)[1].strip())

                self.assertEqual(data["initialVis"], ["org.kde.dolphin", "org.kde.konsole", "firefox", "systemsettings"])
                self.assertEqual(data["afterHorizFwdMulti"], ["org.kde.konsole", "firefox", "systemsettings", "org.kde.dolphin"])
                self.assertEqual(data["afterHorizRevMulti"], ["org.kde.konsole", "org.kde.dolphin", "firefox", "systemsettings"])
                self.assertEqual(data["afterHorizStepRight"], ["org.kde.dolphin", "org.kde.konsole", "firefox", "systemsettings"])
                self.assertEqual(data["afterVertDown"], ["org.kde.konsole", "firefox", "org.kde.dolphin", "systemsettings"])
                self.assertEqual(data["afterVertUp"], ["systemsettings", "org.kde.konsole", "firefox", "org.kde.dolphin"])
                self.assertIn("code", data["rawAfterMulti"])
                self.assertEqual(data["afterSingleDrag"], ["org.kde.dolphin"])

                # Verify reload persistence in fresh Quickshell process
                with open(reload_probe_path, "w") as rpf:
                    rpf.write("""import QtQuick
import Quickshell
import "./services"

Scope {
    property var _pinned: ConfigService.dockPinned
    Timer {
        interval: 250
        running: true
        repeat: false
        onTriggered: {
            ApplicationService.applications = [
                { id: "org.kde.dolphin", name: "Dolphin", icon: "system-file-manager", aliases: ["org.kde.dolphin", "dolphin"] },
                { id: "org.kde.konsole", name: "Konsole", icon: "utilities-terminal", aliases: ["org.kde.konsole", "konsole"] },
                { id: "org.mozilla.firefox", name: "Firefox", icon: "org.mozilla.firefox", aliases: ["org.mozilla.firefox", "firefox"] },
                { id: "systemsettings", name: "System Settings", icon: "preferences-system", aliases: ["systemsettings"] }
            ];
            ApplicationService.loading = false;
            console.log("DOCK_DND_RELOAD_RESULT:" + JSON.stringify({
                reloadedRaw: ConfigService.dockPinned,
                reloadedVis: ApplicationService.pinnedApps,
                reloadedEdge: ConfigService.dockEdge
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
                reload_marker = "DOCK_DND_RELOAD_RESULT:"
                self.assertIn(reload_marker, reload_combined, f"Missing reload marker:\n{reload_combined}")
                reload_line = [line for line in reload_combined.splitlines() if reload_marker in line][-1]
                reload_data = json.loads(reload_line.split(reload_marker, 1)[1].strip())

                self.assertEqual(reload_data["reloadedRaw"], data["rawAfterMulti"])
                self.assertEqual(reload_data["reloadedVis"], ["systemsettings", "org.kde.konsole", "firefox", "org.kde.dolphin"])
                self.assertEqual(reload_data["reloadedEdge"], "right")
            finally:
                for p in (probe_path, reload_probe_path):
                    if os.path.exists(p):
                        os.remove(p)

    def test_15_runtime_drag_to_pin_running_apps_and_session_pin_unpin(self):
        """Real QML Drag Event Test: Verify dragging unpinned running apps into empty, single-item, and multi-item Dock, canonical ID resolution, duplicate icon prevention, unknown app rejection, and session pin/unpin."""
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["XDG_CONFIG_HOME"] = tmpdir
            env["QT_QPA_PLATFORM"] = "offscreen"
            probe_path = os.path.join(REPO_DIR, "_test_dock_dnd_pin_probe.qml")
            try:
                with open(probe_path, "w") as pf:
                    pf.write("""import QtQuick
import QtQuick.Layouts
import QtTest
import Quickshell
import "./services"
import "./modules/dock"

FloatingWindow {
    id: win
    implicitWidth: 800
    implicitHeight: 300
    visible: true

    property string edge: "bottom"
    readonly property bool isVertical: false
    property var activePopupItem: null
    readonly property bool hasActivePopup: activePopupItem !== null
    property var activeDragItem: null
    readonly property bool isDragging: activeDragItem !== null
    property bool isRevealed: true

    readonly property var unpinnedRunningApps: {
        const pinned = ApplicationService.pinnedApps || [];
        const running = WindowService.runningAppIds || [];
        const res = [];
        for (let i = 0; i < running.length; i++) {
            const r = running[i];
            const app = ApplicationService.getAppById(r);
            const canonId = app ? app.id : r;
            let isPinned = false;
            for (let p = 0; p < pinned.length; p++) {
                const pApp = ApplicationService.getAppById(pinned[p]);
                const pCanon = pApp ? pApp.id : pinned[p];
                if (pCanon === canonId || pinned[p] === r || pinned[p] === canonId) {
                    isPinned = true;
                    break;
                }
            }
            if (!isPinned && res.indexOf(canonId) === -1) {
                res.push(canonId);
            }
        }
        return res;
    }

    RowLayout {
        id: rowLayout
        x: 60
        y: 30
        spacing: 4

        DockSeparator { isVertical: false }

        Repeater {
            id: pinnedRep
            model: ApplicationService.pinnedApps
            DockItem {
                required property var modelData
                parentWindowRef: win
                appId: modelData
                app: ApplicationService.getAppById(modelData)
            }
        }

        DockSeparator {
            id: pinSep
            isVertical: false
            acceptPinDrop: true
            visible: win.unpinnedRunningApps.length > 0
        }

        Repeater {
            id: runningRep
            model: win.unpinnedRunningApps
            DockItem {
                required property var modelData
                parentWindowRef: win
                appId: modelData
                app: ApplicationService.getAppById(modelData)
            }
        }
    }

    TestCase {
        id: tc
        name: "DockDragPinSuite"
        when: false

        function dragItemToTarget(srcItem, dstItem, dstX, dstY) {
            mousePress(srcItem, srcItem.width / 2, srcItem.height / 2, Qt.LeftButton);
            mouseMove(srcItem, srcItem.width / 2 - 8, srcItem.height / 2);
            const pt = srcItem.mapFromItem(dstItem, dstX, dstY);
            mouseMove(srcItem, pt.x, pt.y);
            mouseRelease(srcItem, pt.x, pt.y, Qt.LeftButton);
            wait(25);
        }

        function runTests() {
            // Start with EMPTY pinned list
            ConfigService.dockPinned = [];
            wait(25);
            const emptyPinnedStart = ApplicationService.pinnedApps.slice();
            const runningStart = win.unpinnedRunningApps.slice();

            // 1. Empty Dock: Drag running item 0 ("org.kde.gwenview") into the empty pinned zone (left of pinSep)
            dragItemToTarget(runningRep.itemAt(0), pinSep, -20, 12);
            const pinnedAfterEmptyDrop = ApplicationService.pinnedApps.slice();
            const runningAfterEmptyDrop = win.unpinnedRunningApps.slice();

            // 2. Single-item Dock: Drag running item 0 ("com.spotify.Client") onto pinned item 0 ("org.kde.gwenview") -> pins at index 0
            dragItemToTarget(runningRep.itemAt(0), pinnedRep.itemAt(0), 20, 26);
            const pinnedAfterSingleDrop = ApplicationService.pinnedApps.slice();
            const runningAfterSingleDrop = win.unpinnedRunningApps.slice();

            // 3. Multi-item Dock: Drag running item 0 ("org.kde.okular") onto index 1 ("org.kde.gwenview") -> pins at index 1
            dragItemToTarget(runningRep.itemAt(0), pinnedRep.itemAt(1), 20, 26);
            const pinnedAfterMiddleDrop = ApplicationService.pinnedApps.slice();
            const runningAfterMiddleDrop = win.unpinnedRunningApps.slice();

            // 4. Unknown running window ("window-0_{9999...}") remains in runningRep at index 0; dragging it onto pinned item 0 must be rejected!
            dragItemToTarget(runningRep.itemAt(0), pinnedRep.itemAt(0), 26, 26);
            const pinnedAfterUnknownDrop = ApplicationService.pinnedApps.slice();
            const runningAfterUnknownDrop = win.unpinnedRunningApps.slice();

            // 5. Direct service validation for invalid/unknown IDs
            const rejectEmpty = ApplicationService.pinAppAt("", 0);
            const rejectEnv = ApplicationService.pinAppAt("env", 0);
            const rejectWin = ApplicationService.pinAppAt("window-custom-tool", 0);
            const rejectGhost = ApplicationService.pinAppAt("nonexistent.ghost.app", 0);
            const rejectDuplicate = ApplicationService.pinAppAt("com.spotify.Client", 0);

            // 6. Unpin "org.kde.okular" during the same session -> returns to unpinnedRunningApps -> drag to pin at end (via pinSep)
            ApplicationService.togglePin("org.kde.okular");
            wait(25);
            const pinnedAfterUnpinOkular = ApplicationService.pinnedApps.slice();
            const runningAfterUnpinOkular = win.unpinnedRunningApps.slice();

            // Find okular in runningRep (index 0) and drag onto pinSep to pin at the end (index 2)
            dragItemToTarget(runningRep.itemAt(0), pinSep, 0, 12);
            const pinnedAfterRepinEnd = ApplicationService.pinnedApps.slice();
            const runningAfterRepinEnd = win.unpinnedRunningApps.slice();

            console.log("DOCK_DND_PIN_RESULT:" + JSON.stringify({
                emptyPinnedStart: emptyPinnedStart,
                runningStart: runningStart,
                pinnedAfterEmptyDrop: pinnedAfterEmptyDrop,
                runningAfterEmptyDrop: runningAfterEmptyDrop,
                pinnedAfterSingleDrop: pinnedAfterSingleDrop,
                runningAfterSingleDrop: runningAfterSingleDrop,
                pinnedAfterMiddleDrop: pinnedAfterMiddleDrop,
                runningAfterMiddleDrop: runningAfterMiddleDrop,
                pinnedAfterUnknownDrop: pinnedAfterUnknownDrop,
                runningAfterUnknownDrop: runningAfterUnknownDrop,
                rejectEmpty: rejectEmpty,
                rejectEnv: rejectEnv,
                rejectWin: rejectWin,
                rejectGhost: rejectGhost,
                rejectDuplicate: rejectDuplicate,
                pinnedAfterUnpinOkular: pinnedAfterUnpinOkular,
                runningAfterUnpinOkular: runningAfterUnpinOkular,
                pinnedAfterRepinEnd: pinnedAfterRepinEnd,
                runningAfterRepinEnd: runningAfterRepinEnd
            }));
        }
    }

    Timer {
        interval: 250
        running: true
        repeat: false
        onTriggered: {
            WindowService.outputsOverride = ["eDP-1"];
            ApplicationService.applications = [
                { id: "org.kde.gwenview", name: "Gwenview", icon: "gwenview", aliases: ["org.kde.gwenview", "gwenview"] },
                { id: "com.spotify.Client", name: "Spotify", icon: "com.spotify.Client", startupWMClass: "spotify", aliases: ["com.spotify.client", "spotify"] },
                { id: "org.kde.okular", name: "Okular", icon: "okular", startupWMClass: "okular", aliases: ["org.kde.okular", "okular"] }
            ];
            ApplicationService.loading = false;

            const wGwen = "0_{11111111-1111-1111-1111-111111111111}";
            const wSpot = "0_{22222222-2222-2222-2222-222222222222}";
            const wOku  = "0_{33333333-3333-3333-3333-333333333333}";
            const wUnk  = "0_{99999999-9999-9999-9999-999999999999}";

            const rawWins = [
                '[Argument: (sssida{sv}) "' + wGwen + '", "Photo.png", "gwenview", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "' + wSpot + '", "Spotify", "", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "' + wOku + '", "Manual.pdf", "okular", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "' + wUnk + '", "Unknown Tool", "", 100, 1.0, [Argument: a{sv} {}]]',
                '===KWIN_META:' + wSpot + '\\tspotify\\tspotify\\t==='
            ].join("\\n");
            WindowService.handleScannerOutput(rawWins);
            tc.runTests();
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
                    timeout=8
                )
                combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
                marker = "DOCK_DND_PIN_RESULT:"
                self.assertIn(marker, combined, f"Missing marker in output:\n{combined}")
                payload_line = [line for line in combined.splitlines() if marker in line][-1]
                data = json.loads(payload_line.split(marker, 1)[1].strip())

                unk_id = "window-0_{99999999-9999-9999-9999-999999999999}"
                self.assertEqual(data["emptyPinnedStart"], [])
                self.assertEqual(data["runningStart"], ["org.kde.gwenview", "com.spotify.Client", "org.kde.okular", unk_id])

                # 1. Empty Dock pin -> index 0
                self.assertEqual(data["pinnedAfterEmptyDrop"], ["org.kde.gwenview"])
                self.assertEqual(data["runningAfterEmptyDrop"], ["com.spotify.Client", "org.kde.okular", unk_id])

                # 2. Single-item Dock pin -> index 0
                self.assertEqual(data["pinnedAfterSingleDrop"], ["com.spotify.Client", "org.kde.gwenview"])
                self.assertEqual(data["runningAfterSingleDrop"], ["org.kde.okular", unk_id])

                # 3. Multi-item Dock pin -> index 1
                self.assertEqual(data["pinnedAfterMiddleDrop"], ["com.spotify.Client", "org.kde.okular", "org.kde.gwenview"])
                self.assertEqual(data["runningAfterMiddleDrop"], [unk_id])

                # 4. Unknown running window rejected
                self.assertEqual(data["pinnedAfterUnknownDrop"], ["com.spotify.Client", "org.kde.okular", "org.kde.gwenview"])
                self.assertEqual(data["runningAfterUnknownDrop"], [unk_id])
                self.assertFalse(data["rejectEmpty"])
                self.assertFalse(data["rejectEnv"])
                self.assertFalse(data["rejectWin"])
                self.assertFalse(data["rejectGhost"])
                self.assertFalse(data["rejectDuplicate"])

                # 5. Unpin and re-pin in same session
                self.assertEqual(data["pinnedAfterUnpinOkular"], ["com.spotify.Client", "org.kde.gwenview"])
                self.assertEqual(data["runningAfterUnpinOkular"], ["org.kde.okular", unk_id])
                self.assertEqual(data["pinnedAfterRepinEnd"], ["com.spotify.Client", "org.kde.gwenview", "org.kde.okular"])
                self.assertEqual(data["runningAfterRepinEnd"], [unk_id])
            finally:
                if os.path.exists(probe_path):
                    os.remove(probe_path)

    def test_16_runtime_drag_cancellation_invalid_drops_and_interaction_safety(self):
        """Real QML Drag Event Test: Verify drag cancellation, target unavailability, invalid drop no-ops, no accidental launch/toggle on drag, left/middle/right click preservation, wheel cycling, popup/tooltip suppression, and autohide preservation."""
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["XDG_CONFIG_HOME"] = tmpdir
            env["QT_QPA_PLATFORM"] = "offscreen"
            probe_path = os.path.join(REPO_DIR, "_test_dock_dnd_safety_probe.qml")
            try:
                with open(probe_path, "w") as pf:
                    pf.write("""import QtQuick
import QtQuick.Layouts
import QtTest
import Quickshell
import "./services"
import "./modules/dock"

FloatingWindow {
    id: win
    implicitWidth: 800
    implicitHeight: 300
    visible: true

    property string edge: "bottom"
    readonly property bool isVertical: false
    property bool autoHide: true
    property bool hoverRevealed: false
    property var activePopupItem: null
    readonly property bool hasActivePopup: activePopupItem !== null
    property var activeDragItem: null
    readonly property bool isDragging: activeDragItem !== null
    readonly property bool isRevealed: !autoHide || hoverRevealed || hasActivePopup || isDragging

    RowLayout {
        id: rowLayout
        x: 20
        y: 20
        spacing: 4

        Repeater {
            id: pinnedRep
            model: ApplicationService.pinnedApps
            DockItem {
                required property var modelData
                parentWindowRef: win
                appId: modelData
                app: ApplicationService.getAppById(modelData)
            }
        }

        Repeater {
            id: runningRep
            model: ["org.kde.gwenview"]
            DockItem {
                required property var modelData
                parentWindowRef: win
                appId: modelData
                app: ApplicationService.getAppById(modelData)
            }
        }
    }

    TestCase {
        id: tc
        name: "DockSafetySuite"
        when: false

        function runTests() {
            wait(25);
            const baseline = ApplicationService.pinnedApps.slice();
            WindowService.lastExecutedAction = null;

            // 1. Mid-drag explicit cancelDrag() before mouseRelease over another item -> must NOT reorder and must NOT click/launch!
            const item0 = pinnedRep.itemAt(0);
            const item2 = pinnedRep.itemAt(2);
            item0.menuOpen = true;
            item0.tooltipActive = true;
            mousePress(item0, 26, 26, Qt.LeftButton);
            mouseMove(item0, 35, 26);
            mouseMove(item0, 50, 26); // starts drag
            const revealedDuringDrag = win.isRevealed;
            const menuClosedOnDrag = !item0.menuOpen;
            const tooltipClosedOnDrag = !item0.tooltipActive;
            const pt2 = item0.mapFromItem(item2, 26, 26);
            mouseMove(item0, pt2.x, pt2.y);
            item0.cancelDrag();
            mouseRelease(item0, pt2.x, pt2.y, Qt.LeftButton);
            wait(20);
            const afterExplicitCancel = ApplicationService.pinnedApps.slice();
            const actionAfterCancel = WindowService.lastExecutedAction;

            // 2. Drag cancellation when item becomes invisible mid-drag
            mousePress(item0, 26, 26, Qt.LeftButton);
            mouseMove(item0, 35, 26);
            mouseMove(item0, 50, 26);
            const draggingBeforeHide = item0.dragging;
            item0.visible = false;
            const draggingAfterHide = item0.dragging;
            const winDraggingAfterHide = win.isDragging;
            mouseRelease(item0, 45, 26, Qt.LeftButton);
            item0.visible = true;
            wait(20);
            const afterHideCancel = ApplicationService.pinnedApps.slice();

            // 3. Invalid drop outside Dock (far above rowLayout) -> safe no-op, no window action
            mousePress(item0, 26, 26, Qt.LeftButton);
            mouseMove(item0, 26, -120);
            mouseRelease(item0, 26, -120, Qt.LeftButton);
            wait(20);
            const afterOutsideDrop = ApplicationService.pinnedApps.slice();

            // 4. Invalid drop of pinned item onto unpinned running item -> safe no-op
            const runItem = runningRep.itemAt(0);
            const ptRun = item0.mapFromItem(runItem, 26, 26);
            mousePress(item0, 26, 26, Qt.LeftButton);
            mouseMove(item0, 45, 26);
            mouseMove(item0, ptRun.x, ptRun.y);
            mouseRelease(item0, ptRun.x, ptRun.y, Qt.LeftButton);
            wait(20);
            const afterDropOnRunning = ApplicationService.pinnedApps.slice();

            // 5. Right-click toggles context menu and right-button mouse movement must NOT start drag
            mouseClick(item0, 26, 26, Qt.RightButton);
            const menuOpenAfterRightClick = item0.menuOpen;
            item0.menuOpen = false;
            mousePress(item0, 26, 26, Qt.RightButton);
            mouseMove(item0, 35, 26);
            mouseMove(item0, 55, 26);
            const draggingOnRightMove = item0.dragging;
            mouseRelease(item0, 55, 26, Qt.RightButton);
            item0.menuOpen = false;

            // 6. Left-click (without drag) on single-window running item ("org.kde.konsole", index 1) toggles window
            const item1 = pinnedRep.itemAt(1);
            WindowService.lastExecutedAction = null;
            mouseClick(item1, 26, 26, Qt.LeftButton);
            const actionAfterLeftClick = WindowService.lastExecutedAction;

            // 7. Wheel cycling still works after drag operations
            const wheelOk = item1.handleWheel(120);

            console.log("DOCK_DND_SAFETY_RESULT:" + JSON.stringify({
                baseline: baseline,
                revealedDuringDrag: revealedDuringDrag,
                menuClosedOnDrag: menuClosedOnDrag,
                tooltipClosedOnDrag: tooltipClosedOnDrag,
                afterExplicitCancel: afterExplicitCancel,
                actionAfterCancel: actionAfterCancel,
                draggingBeforeHide: draggingBeforeHide,
                draggingAfterHide: draggingAfterHide,
                winDraggingAfterHide: winDraggingAfterHide,
                afterHideCancel: afterHideCancel,
                afterOutsideDrop: afterOutsideDrop,
                afterDropOnRunning: afterDropOnRunning,
                draggingOnRightMove: draggingOnRightMove,
                menuOpenAfterRightClick: menuOpenAfterRightClick,
                actionAfterLeftClick: actionAfterLeftClick,
                wheelOk: wheelOk
            }));
        }
    }

    Timer {
        interval: 250
        running: true
        repeat: false
        onTriggered: {
            WindowService.outputsOverride = ["eDP-1"];
            ApplicationService.applications = [
                { id: "org.kde.dolphin", name: "Dolphin", icon: "system-file-manager", aliases: ["org.kde.dolphin", "dolphin"] },
                { id: "org.kde.konsole", name: "Konsole", icon: "utilities-terminal", aliases: ["org.kde.konsole", "konsole"] },
                { id: "org.mozilla.firefox", name: "Firefox", icon: "org.mozilla.firefox", aliases: ["org.mozilla.firefox", "firefox"] },
                { id: "systemsettings", name: "System Settings", icon: "preferences-system", aliases: ["systemsettings"] },
                { id: "org.kde.gwenview", name: "Gwenview", icon: "gwenview", aliases: ["org.kde.gwenview", "gwenview"] }
            ];
            ApplicationService.loading = false;

            const wKon = "0_{55555555-5555-5555-5555-555555555555}";
            const wGwen = "0_{66666666-6666-6666-6666-666666666666}";
            const rawWins = [
                '[Argument: (sssida{sv}) "' + wKon + '", "Konsole", "utilities-terminal", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "' + wGwen + '", "Gwenview", "gwenview", 100, 1.0, [Argument: a{sv} {}]]',
                '===KWIN_META:' + wKon + '\\torg.kde.konsole\\torg.kde.konsole\\t===',
                '===KWIN_META:' + wGwen + '\\torg.kde.gwenview\\tgwenview\\t==='
            ].join("\\n");
            WindowService.handleScannerOutput(rawWins);
            tc.runTests();
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
                    timeout=8
                )
                combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
                marker = "DOCK_DND_SAFETY_RESULT:"
                self.assertIn(marker, combined, f"Missing marker in output:\n{combined}")
                payload_line = [line for line in combined.splitlines() if marker in line][-1]
                data = json.loads(payload_line.split(marker, 1)[1].strip())

                expected_base = ["org.kde.dolphin", "org.kde.konsole", "firefox", "systemsettings"]
                self.assertEqual(data["baseline"], expected_base)
                self.assertTrue(data["revealedDuringDrag"])
                self.assertTrue(data["menuClosedOnDrag"])
                self.assertTrue(data["tooltipClosedOnDrag"])
                self.assertEqual(data["afterExplicitCancel"], expected_base)
                self.assertIsNone(data["actionAfterCancel"])
                self.assertTrue(data["draggingBeforeHide"])
                self.assertFalse(data["draggingAfterHide"])
                self.assertFalse(data["winDraggingAfterHide"])
                self.assertEqual(data["afterHideCancel"], expected_base)
                self.assertEqual(data["afterOutsideDrop"], expected_base)
                self.assertEqual(data["afterDropOnRunning"], expected_base)
                self.assertFalse(data["draggingOnRightMove"])
                self.assertTrue(data["menuOpenAfterRightClick"])
                self.assertIsNotNone(data["actionAfterLeftClick"])
                self.assertEqual(data["actionAfterLeftClick"]["action"], "toggle")
                self.assertTrue(data["wheelOk"])
            finally:
                if os.path.exists(probe_path):
                    os.remove(probe_path)

if __name__ == "__main__":
    unittest.main()
