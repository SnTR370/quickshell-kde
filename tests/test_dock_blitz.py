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

if __name__ == "__main__":
    unittest.main()
