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

        # Feature 1: Window cycling contracts (P0 #8 added the screenName
        # argument for per-monitor filtering)
        self.assertIn("function cycleAppWindows(appId, reverse, screenName)", win_service_qml)
        self.assertIn("onWheel: wheel =>", self.dock_item_qml)
        self.assertIn("function handleWheel(delta)", self.dock_item_qml)
        self.assertIn("WindowService.cycleAppWindows(root.appId, delta < 0, root.filterScreenName)", self.dock_item_qml)

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

    def test_17_runtime_window_state_reconciliation_identity_and_cycling_reliability(self):
        """Live QML Runtime Test: Verify late app-index resolution, zero-title windows, shared-icon cross-app isolation, rejected KWin action reconciliation, chooser auto-close, and forward/reverse cycling after start/middle/end window disappearance."""
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["XDG_CONFIG_HOME"] = tmpdir
            probe_path = os.path.join(REPO_DIR, "_test_dock_phase_a_reliability_probe.qml")
            try:
                with open(probe_path, "w") as pf:
                    pf.write("""import QtQuick
import Quickshell
import "./services"
import "./modules/dock"

Scope {
    QtObject {
        id: mockWin
        property var activePopupItem: null
        readonly property bool hasActivePopup: activePopupItem !== null
        property var activeDragItem: null
        readonly property bool isDragging: activeDragItem !== null
        property bool isVertical: false
    }

    DockItem {
        id: konsoleItem
        parentWindowRef: mockWin
        appId: "org.kde.konsole"
    }

    DockItem {
        id: qtermItem
        parentWindowRef: mockWin
        appId: "org.lxqt.qterminal"
    }

    DockItem {
        id: ffItem
        parentWindowRef: mockWin
        appId: "org.mozilla.firefox"
    }

    property string activeDuringUpdateSignal: "UNSET"
    property int cacheKeysDuringUpdateSignal: -1

    Connections {
        target: WindowService
        function onWindowsUpdated() {
            activeDuringUpdateSignal = WindowService.activeWindowId;
            cacheKeysDuringUpdateSignal = Object.keys(WindowService.metadataCache).length;
        }
    }

    Timer {
        interval: 250
        running: true
        repeat: false
        onTriggered: {
            WindowService.outputsOverride = ["eDP-1", "DP-2"];

            // 1. Windows arrive BEFORE ApplicationService.applications is populated
            ApplicationService.applications = [];
            ApplicationService.aliasMap = ({});

            const wKon = "0_{11111111-1111-1111-1111-111111111111}";
            const wZeroTitle = "0_{12121212-1212-1212-1212-121212121212}";
            const wQterm = "0_{22222222-2222-2222-2222-222222222222}";
            const wAlacritty = "0_{33333333-3333-3333-3333-333333333333}";

            const rawPreApps = [
                '[Argument: (sssida{sv}) "' + wKon + '", "Konsole 1", "utilities-terminal", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "' + wZeroTitle + '", "", "", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "' + wQterm + '", "QTerminal", "utilities-terminal", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "' + wAlacritty + '", "Alacritty", "utilities-terminal", 100, 1.0, [Argument: a{sv} {}]]',
                '===KWIN_META:' + wKon + '\\torg.kde.konsole\\tkonsole\\tkonsole===',
                '===KWIN_META:' + wZeroTitle + '\\t\\t\\tkonsole===',
                '===KWIN_META:' + wQterm + '\\torg.lxqt.qterminal\\tqterminal\\tqterminal===',
                '===KWIN_META:' + wAlacritty + '\\tcom.alacritty.Alacritty\\tAlacritty\\talacritty==='
            ].join("\\n");
            WindowService.handleScannerOutput(rawPreApps);
            const runningBeforeAppsLoaded = WindowService.runningAppIds.slice();
            const zeroTitleFoundBefore = WindowService.findWindowById(wZeroTitle) !== null;

            // Pre-app-load cycle state keyed under "window-org.kde.konsole"
            WindowService.appCycleIndices["window-org.kde.konsole"] = 1;
            WindowService.appCycleWindowIds["window-org.kde.konsole"] = WindowService.cleanWindowId(wZeroTitle);

            // 2. ApplicationService.applications finishes loading -> WindowService must immediately re-resolve without new KWin poll
            ApplicationService.applications = [
                {
                    id: "org.kde.konsole.desktop",
                    name: "Konsole",
                    icon: "utilities-terminal",
                    startupWMClass: "konsole",
                    execBinary: "konsole",
                    aliases: ["org.kde.konsole", "konsole", "utilities-terminal"]
                },
                {
                    id: "org.lxqt.qterminal.desktop",
                    name: "QTerminal",
                    icon: "utilities-terminal",
                    startupWMClass: "qterminal",
                    execBinary: "qterminal",
                    aliases: ["org.lxqt.qterminal", "qterminal", "utilities-terminal"]
                },
                {
                    id: "org.mozilla.firefox.desktop",
                    name: "Firefox",
                    icon: "org.mozilla.firefox",
                    startupWMClass: "org.mozilla.firefox",
                    execBinary: "firefox",
                    aliases: ["org.mozilla.firefox", "firefox"]
                }
            ];
            ApplicationService.loading = false;

            const runningAfterAppsLoaded = WindowService.runningAppIds.slice();
            const konsoleWinsCount = WindowService.getWindowsForApp("org.kde.konsole").length;
            const qtermWinsCount = WindowService.getWindowsForApp("org.lxqt.qterminal").length;
            const alacrittyAppId = WindowService.findWindowById(wAlacritty).appId;
            const migratedCycleWid = WindowService.appCycleWindowIds["org.kde.konsole"] || "";

            // 3. Chooser popup auto-closes when windowCount drops from 2 -> 1 -> 0
            konsoleItem.chooserOpen = true;
            const popupActiveWhen2Wins = (mockWin.activePopupItem === konsoleItem);
            const rawOneKonsole = [
                '[Argument: (sssida{sv}) "' + wKon + '", "Konsole 1", "utilities-terminal", 100, 1.0, [Argument: a{sv} {}]]'
            ].join("\\n");
            WindowService.handleScannerOutput(rawOneKonsole);
            const chooserOpenAfterDropTo1 = konsoleItem.chooserOpen;
            const popupClearedAfterDropTo1 = (mockWin.activePopupItem === null);

            // 4. Optimistic activeWindowId reconciliation when KWin rejects activate / minimize
            WindowService.activateWindow(wKon);
            const optimisticActive = WindowService.activeWindowId;
            // KWin reports no active window (e.g. activation rejected or all windows minimized)
            WindowService.handleActiveWindowOutput("");
            const activeAfterEmptyReconcile = WindowService.activeWindowId;
            WindowService.activateWindow(wKon);
            WindowService.handleActiveWindowOutput("null");
            const activeAfterNullReconcile = WindowService.activeWindowId;
            // Toggle minimizes active wKon optimistically (""), but KWin rejects minimize (window not minimizable) and reports wKon still active
            WindowService.activateWindow(wKon);
            WindowService.toggleWindow(wKon);
            const optimisticAfterToggleMinimize = WindowService.activeWindowId;
            WindowService.handleActiveWindowOutput(wKon);
            const reconciledAfterRejectedMinimize = WindowService.activeWindowId;

            // 5. Active window closing during polling clears activeWindowId and prunes caches BEFORE windowsUpdated signal fires
            WindowService.handleScannerOutput("[Argument: a(sssida{sv}) {}]");
            const activeDuringCloseAllSignal = activeDuringUpdateSignal;
            const cacheKeysDuringCloseAllSignal = cacheKeysDuringUpdateSignal;

            // 6. Forward and reverse cycling when start, middle, or end window disappears
            const wFF1 = "0_{aaaa1111-1111-1111-1111-111111111111}";
            const wFF2 = "0_{bbbb2222-2222-2222-2222-222222222222}";
            const wFF3 = "0_{cccc3333-3333-3333-3333-333333333333}";
            const rawThreeFF = [
                '[Argument: (sssida{sv}) "' + wFF1 + '", "FF 1", "org.mozilla.firefox", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "' + wFF2 + '", "FF 2", "org.mozilla.firefox", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "' + wFF3 + '", "FF 3", "org.mozilla.firefox", 100, 1.0, [Argument: a{sv} {}]]',
                '===KWIN_META:' + wFF1 + '\\torg.mozilla.firefox\\torg.mozilla.firefox\\t===',
                '===KWIN_META:' + wFF2 + '\\torg.mozilla.firefox\\torg.mozilla.firefox\\t===',
                '===KWIN_META:' + wFF3 + '\\torg.mozilla.firefox\\torg.mozilla.firefox\\t==='
            ].join("\\n");
            WindowService.handleScannerOutput(rawThreeFF);

            // 6a. Middle window (wFF2) focused, then wFF2 closes -> reverse cycle must select wFF1 (predecessor)
            WindowService.activateWindow(wFF2);
            const rawNoFF2 = [
                '[Argument: (sssida{sv}) "' + wFF1 + '", "FF 1", "org.mozilla.firefox", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "' + wFF3 + '", "FF 3", "org.mozilla.firefox", 100, 1.0, [Argument: a{sv} {}]]'
            ].join("\\n");
            WindowService.handleScannerOutput(rawNoFF2);
            ffItem.handleWheel(-120);
            const revAfterMiddleClose = WindowService.activeWindowId;

            // 6b. End window (wFF3) focused, then wFF3 closes -> forward cycle wraps to wFF1; reverse cycle selects wFF2
            WindowService.handleScannerOutput(rawThreeFF);
            WindowService.activateWindow(wFF3);
            const rawNoFF3 = [
                '[Argument: (sssida{sv}) "' + wFF1 + '", "FF 1", "org.mozilla.firefox", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "' + wFF2 + '", "FF 2", "org.mozilla.firefox", 100, 1.0, [Argument: a{sv} {}]]'
            ].join("\\n");
            WindowService.handleScannerOutput(rawNoFF3);
            ffItem.handleWheel(120);
            const fwdAfterEndClose = WindowService.activeWindowId;

            WindowService.handleScannerOutput(rawThreeFF);
            WindowService.activateWindow(wFF3);
            WindowService.handleScannerOutput(rawNoFF3);
            ffItem.handleWheel(-120);
            const revAfterEndClose = WindowService.activeWindowId;

            // 7. Metadata retry exhaustion on partial/unformatted parseMetaOutput
            const wMetaFail = "0_{dddd4444-4444-4444-4444-444444444444}";
            WindowService.handleScannerOutput('[Argument: (sssida{sv}) "' + wMetaFail + '", "Mystery", "utilities-terminal", 100, 1.0, [Argument: a{sv} {}]]');
            WindowService.inFlightWids = [wMetaFail];
            WindowService.parseMetaOutput("unrelated_output");
            WindowService.inFlightWids = [wMetaFail];
            WindowService.parseMetaOutput("unrelated_output");
            WindowService.inFlightWids = [wMetaFail];
            WindowService.parseMetaOutput("unrelated_output");
            const retriesAfter3 = WindowService.metaRetries[wMetaFail] || 0;
            const cachedEmptyAfter3 = (WindowService.metadataCache[wMetaFail] !== undefined);

            console.log("PHASE_A_RELIABILITY_RESULT:" + JSON.stringify({
                runningBeforeAppsLoaded: runningBeforeAppsLoaded,
                zeroTitleFoundBefore: zeroTitleFoundBefore,
                runningAfterAppsLoaded: runningAfterAppsLoaded,
                konsoleWinsCount: konsoleWinsCount,
                qtermWinsCount: qtermWinsCount,
                alacrittyAppId: alacrittyAppId,
                migratedCycleWid: migratedCycleWid,
                popupActiveWhen2Wins: popupActiveWhen2Wins,
                chooserOpenAfterDropTo1: chooserOpenAfterDropTo1,
                popupClearedAfterDropTo1: popupClearedAfterDropTo1,
                optimisticActive: optimisticActive,
                activeAfterEmptyReconcile: activeAfterEmptyReconcile,
                activeAfterNullReconcile: activeAfterNullReconcile,
                optimisticAfterToggleMinimize: optimisticAfterToggleMinimize,
                reconciledAfterRejectedMinimize: reconciledAfterRejectedMinimize,
                activeDuringCloseAllSignal: activeDuringCloseAllSignal,
                cacheKeysDuringCloseAllSignal: cacheKeysDuringCloseAllSignal,
                revAfterMiddleClose: revAfterMiddleClose,
                fwdAfterEndClose: fwdAfterEndClose,
                revAfterEndClose: revAfterEndClose,
                retriesAfter3: retriesAfter3,
                cachedEmptyAfter3: cachedEmptyAfter3
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
                    timeout=8
                )
                combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
                marker = "PHASE_A_RELIABILITY_RESULT:"
                self.assertIn(marker, combined, f"Missing marker in output:\n{combined}")
                payload_line = [line for line in combined.splitlines() if marker in line][-1]
                data = json.loads(payload_line.split(marker, 1)[1].strip())

                self.assertTrue(data["zeroTitleFoundBefore"])
                self.assertIn("window-org.kde.konsole", data["runningBeforeAppsLoaded"])
                self.assertEqual(
                    data["runningAfterAppsLoaded"],
                    ["org.kde.konsole.desktop", "org.lxqt.qterminal.desktop", "window-com.alacritty.alacritty"]
                )
                self.assertEqual(data["konsoleWinsCount"], 2)
                self.assertEqual(data["qtermWinsCount"], 1)
                self.assertEqual(data["alacrittyAppId"], "window-com.alacritty.alacritty")
                self.assertEqual(data["migratedCycleWid"], "12121212-1212-1212-1212-121212121212")

                self.assertTrue(data["popupActiveWhen2Wins"])
                self.assertFalse(data["chooserOpenAfterDropTo1"])
                self.assertTrue(data["popupClearedAfterDropTo1"])

                self.assertEqual(data["optimisticActive"], "11111111-1111-1111-1111-111111111111")
                self.assertEqual(data["activeAfterEmptyReconcile"], "")
                self.assertEqual(data["activeAfterNullReconcile"], "")
                self.assertEqual(data["optimisticAfterToggleMinimize"], "")
                self.assertEqual(data["reconciledAfterRejectedMinimize"], "11111111-1111-1111-1111-111111111111")

                self.assertEqual(data["activeDuringCloseAllSignal"], "")
                self.assertEqual(data["cacheKeysDuringCloseAllSignal"], 0)

                self.assertEqual(data["revAfterMiddleClose"], "aaaa1111-1111-1111-1111-111111111111")
                self.assertEqual(data["fwdAfterEndClose"], "aaaa1111-1111-1111-1111-111111111111")
                self.assertEqual(data["revAfterEndClose"], "bbbb2222-2222-2222-2222-222222222222")

                self.assertEqual(data["retriesAfter3"], 3)
                self.assertTrue(data["cachedEmptyAfter3"])
            finally:
                if os.path.exists(probe_path):
                    os.remove(probe_path)

    def test_18_runtime_pin_atomicity_canonical_dedup_and_mid_drag_disappearance(self):
        """Live QML Runtime Test: Verify pinAppAt atomicity, invalid index rejection without partial state, canonical/alias dedup, uninstalled preservation, and mid-drag app/window disappearance safety."""
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["XDG_CONFIG_HOME"] = tmpdir
            probe_path = os.path.join(REPO_DIR, "_test_dock_phase_b_reliability_probe.qml")
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
    implicitHeight: 200
    visible: true
    property bool isVertical: false
    property var activePopupItem: null
    readonly property bool hasActivePopup: activePopupItem !== null
    property var activeDragItem: null
    readonly property bool isDragging: activeDragItem !== null

    RowLayout {
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

        DockSeparator {
            id: pinSep
            isVertical: false
            acceptPinDrop: true
        }

        DockItem {
            id: gwenItem
            parentWindowRef: win
            appId: "org.kde.gwenview"
            app: ApplicationService.getAppById("org.kde.gwenview")
        }
    }

    TestCase {
        id: tc
        name: "PhaseBReliabilitySuite"
        when: false

        function runTests() {
            wait(25);

            // 1. Canonical duplicate prevention when dockPinned has both alias and canonical ID
            ConfigService.dockPinned = ["firefox", "org.mozilla.firefox", "org.kde.dolphin", "code"];
            const sanitizedFromBoth = ConfigService.sanitizeDockPinned(ConfigService.dockPinned);
            ConfigService.dockPinned = ["firefox", "org.mozilla.firefox", "org.kde.dolphin", "code"];
            const visibleWithDupeRaw = ApplicationService.pinnedApps.slice();
            ApplicationService.togglePin("org.mozilla.firefox.desktop");
            const stillPinnedAfterToggle = ApplicationService.isPinned("firefox");
            const rawAfterUnpinFirefox = ConfigService.dockPinned.slice();

            // 2. pinAppAt invalid targetIndex rejection (must return false and NOT pin the app)
            const beforeInvalidPin = ConfigService.dockPinned.slice();
            const pinNeg = ApplicationService.pinAppAt("org.mozilla.firefox", -1);
            const pinOob = ApplicationService.pinAppAt("org.mozilla.firefox", 99);
            const pinStr = ApplicationService.pinAppAt("org.mozilla.firefox", "bad");
            const pinFloat = ApplicationService.pinAppAt("org.mozilla.firefox", 0.5);
            const pinNaN = ApplicationService.pinAppAt("org.mozilla.firefox", NaN);
            const afterInvalidPin = ConfigService.dockPinned.slice();
            const isFirefoxPinnedAfterInvalid = ApplicationService.isPinned("org.mozilla.firefox");

            // 3. Valid pinAppAt with uninstalled entry preservation
            // Current raw: ["org.kde.dolphin", "code"], visible: ["org.kde.dolphin"] (len 1)
            const pinAtZero = ApplicationService.pinAppAt("org.mozilla.firefox", 0);
            const visAfterPinZero = ApplicationService.pinnedApps.slice();
            const rawAfterPinZero = ConfigService.dockPinned.slice();

            const pinAtEnd = ApplicationService.pinAppAt("org.kde.konsole", 2);
            const visAfterPinEnd = ApplicationService.pinnedApps.slice();
            const rawAfterPinEnd = ConfigService.dockPinned.slice();
            wait(25);

            // 4. Mid-drag window disappearance on unpinned running item ("org.kde.gwenview")
            mousePress(gwenItem, 26, 26, Qt.LeftButton);
            mouseMove(gwenItem, 36, 26);
            mouseMove(gwenItem, 56, 26);
            const draggingBeforeWindowClose = gwenItem.dragging;
            // Gwenview window closes while user is mid-drag!
            WindowService.handleScannerOutput("[Argument: a(sssida{sv}) {}]");
            const draggingAfterWindowClose = gwenItem.dragging;
            const winDraggingAfterWindowClose = win.isDragging;
            const commitAfterWindowClose = gwenItem.commitDrop({ targetIndex: 0, targetAppId: "org.mozilla.firefox" });
            mouseRelease(gwenItem, 56, 26, Qt.LeftButton);
            wait(20);
            const pinnedAfterMidDragClose = ApplicationService.pinnedApps.slice();

            // 5. Mid-drag target unpinning on pinned item reorder
            const pinItem0 = pinnedRep.itemAt(0); // org.mozilla.firefox
            const commitUnpinnedTarget = pinItem0.commitDrop({ targetIndex: 2, targetAppId: "org.kde.gwenview" });
            const pinnedAfterUnpinnedTarget = ApplicationService.pinnedApps.slice();

            console.log("PHASE_B_RELIABILITY_RESULT:" + JSON.stringify({
                sanitizedFromBoth: sanitizedFromBoth,
                visibleWithDupeRaw: visibleWithDupeRaw,
                stillPinnedAfterToggle: stillPinnedAfterToggle,
                rawAfterUnpinFirefox: rawAfterUnpinFirefox,
                beforeInvalidPin: beforeInvalidPin,
                pinNeg: pinNeg,
                pinOob: pinOob,
                pinStr: pinStr,
                pinFloat: pinFloat,
                pinNaN: pinNaN,
                afterInvalidPin: afterInvalidPin,
                isFirefoxPinnedAfterInvalid: isFirefoxPinnedAfterInvalid,
                pinAtZero: pinAtZero,
                visAfterPinZero: visAfterPinZero,
                rawAfterPinZero: rawAfterPinZero,
                pinAtEnd: pinAtEnd,
                visAfterPinEnd: visAfterPinEnd,
                rawAfterPinEnd: rawAfterPinEnd,
                draggingBeforeWindowClose: draggingBeforeWindowClose,
                draggingAfterWindowClose: draggingAfterWindowClose,
                winDraggingAfterWindowClose: winDraggingAfterWindowClose,
                commitAfterWindowClose: commitAfterWindowClose,
                pinnedAfterMidDragClose: pinnedAfterMidDragClose,
                commitUnpinnedTarget: commitUnpinnedTarget,
                pinnedAfterUnpinnedTarget: pinnedAfterUnpinnedTarget
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
                { id: "org.kde.gwenview", name: "Gwenview", icon: "gwenview", aliases: ["org.kde.gwenview", "gwenview"] }
            ];
            ApplicationService.loading = false;

            const wGwen = "0_{66666666-6666-6666-6666-666666666666}";
            WindowService.handleScannerOutput(
                '[Argument: (sssida{sv}) "' + wGwen + '", "Gwenview", "gwenview", 100, 1.0, [Argument: a{sv} {}]]\\n' +
                '===KWIN_META:' + wGwen + '\\torg.kde.gwenview\\tgwenview\\t==='
            );
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
                marker = "PHASE_B_RELIABILITY_RESULT:"
                self.assertIn(marker, combined, f"Missing marker in output:\n{combined}")
                payload_line = [line for line in combined.splitlines() if marker in line][-1]
                data = json.loads(payload_line.split(marker, 1)[1].strip())

                self.assertEqual(data["sanitizedFromBoth"], ["firefox", "org.kde.dolphin", "code"])
                self.assertEqual(data["visibleWithDupeRaw"], ["firefox", "org.kde.dolphin"])
                self.assertFalse(data["stillPinnedAfterToggle"])
                self.assertEqual(data["rawAfterUnpinFirefox"], ["org.kde.dolphin", "code"])

                self.assertFalse(data["pinNeg"])
                self.assertFalse(data["pinOob"])
                self.assertFalse(data["pinStr"])
                self.assertFalse(data["pinFloat"])
                self.assertFalse(data["pinNaN"])
                self.assertEqual(data["afterInvalidPin"], data["beforeInvalidPin"])
                self.assertFalse(data["isFirefoxPinnedAfterInvalid"])

                self.assertTrue(data["pinAtZero"])
                self.assertEqual(data["visAfterPinZero"], ["org.mozilla.firefox", "org.kde.dolphin"])
                self.assertIn("code", data["rawAfterPinZero"])

                self.assertTrue(data["pinAtEnd"])
                self.assertEqual(data["visAfterPinEnd"], ["org.mozilla.firefox", "org.kde.dolphin", "org.kde.konsole"])
                self.assertIn("code", data["rawAfterPinEnd"])

                self.assertTrue(data["draggingBeforeWindowClose"])
                self.assertFalse(data["draggingAfterWindowClose"])
                self.assertFalse(data["winDraggingAfterWindowClose"])
                self.assertFalse(data["commitAfterWindowClose"])
                self.assertEqual(data["pinnedAfterMidDragClose"], ["org.mozilla.firefox", "org.kde.dolphin", "org.kde.konsole"])

                self.assertFalse(data["commitUnpinnedTarget"])
                self.assertEqual(data["pinnedAfterUnpinnedTarget"], ["org.mozilla.firefox", "org.kde.dolphin", "org.kde.konsole"])
            finally:
                if os.path.exists(probe_path):
                    os.remove(probe_path)

    def test_19_runtime_kwin_native_window_actions_and_capabilities(self):
        """Phase 1 (P0 #5): Verify KWin native window actions (maximize, minimize, fullscreen, keep-above, move-desktop, move-output, close), capability gating, non-optimistic reconciliation, and DockMenu integration."""
        import json
        import tempfile

        script_path = os.path.join(REPO_DIR, "services/kwin/scripts/kwin-window-action.sh")
        # 1. Verify script rejects malformed UUIDs and invalid target args safely without calling KWin
        bad_uuid_res = subprocess.run([script_path, "maximize", "bad;uuid"], capture_output=True, text=True)
        self.assertNotEqual(bad_uuid_res.returncode, 0)
        bad_desk_res = subprocess.run([script_path, "move-desktop", "0_{11111111-1111-1111-1111-111111111111}", "desk;rm"], capture_output=True, text=True)
        self.assertNotEqual(bad_desk_res.returncode, 0)
        bad_fs_res = subprocess.run([script_path, "fullscreen", "0_{11111111-1111-1111-1111-111111111111}", "invalid_bool"], capture_output=True, text=True)
        self.assertNotEqual(bad_fs_res.returncode, 0)

        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["XDG_CONFIG_HOME"] = tmpdir
            probe_path = os.path.join(REPO_DIR, "_test_phase1_window_actions_probe.qml")
            try:
                with open(probe_path, "w") as pf:
                    pf.write("""import QtQuick
import Quickshell
import "./services"
import "./modules/dock"

Scope {
    DockMenu {
        id: menu
        appId: "org.mozilla.firefox"
        isRunning: true
        isPinned: true
    }

    Timer {
        interval: 200
        running: true
        repeat: false
        onTriggered: {
            WindowService.outputsOverride = ["eDP-1", "DP-2"];
            WindowService.desktopsOverride = [
                { id: "desk-1", name: "Desktop 1", index: 0 },
                { id: "desk-2", name: "Desktop 2", index: 1 },
                { id: "desk-3", name: "Desktop 3", index: 2 }
            ];

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

            const uuidA = "0_{11111111-1111-1111-1111-111111111111}";
            const uuidB = "0_{22222222-2222-2222-2222-222222222222}";
            const staleUuid = "0_{99999999-9999-9999-9999-999999999999}";

            const rawWin = [
                '[Argument: (sssida{sv}) "' + uuidA + '", "Firefox Main", "org.mozilla.firefox", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "' + uuidB + '", "Firefox Fixed Dialog", "org.mozilla.firefox", 100, 1.0, [Argument: a{sv} {}]]',
                '===KWIN_META:' + uuidA + '\\torg.mozilla.firefox\\torg.mozilla.firefox\\t===',
                '===KWIN_META:' + uuidB + '\\torg.mozilla.firefox\\torg.mozilla.firefox\\t==='
            ].join("\\n");
            WindowService.handleScannerOutput(rawWin);

            // Seed initial KWin state: uuidA full capabilities, uuidB restricted capabilities
            WindowService.parseWindowStatesJson(JSON.stringify([
                {
                    id: uuidA,
                    output: "eDP-1",
                    minimized: false,
                    minimizable: true,
                    maximized: false,
                    maximizable: true,
                    fullScreen: false,
                    fullScreenable: true,
                    keepAbove: false,
                    keepAboveable: true,
                    closeable: true,
                    moveableAcrossScreens: true,
                    onAllDesktops: false,
                    desktops: ["desk-1"]
                },
                {
                    id: uuidB,
                    output: "eDP-1",
                    minimized: false,
                    minimizable: false,
                    maximized: false,
                    maximizable: false,
                    fullScreen: false,
                    fullScreenable: false,
                    keepAbove: false,
                    keepAboveable: false,
                    closeable: false,
                    moveableAcrossScreens: false,
                    onAllDesktops: false,
                    desktops: ["desk-1"]
                }
            ]));

            const capsA = WindowService.getWindowCapabilities(uuidA);
            const capsB = WindowService.getWindowCapabilities(uuidB);

            // 1. Maximize / Unmaximize + non-optimistic reconciliation
            const maxDispatchA = WindowService.toggleMaximizeWindow(uuidA);
            const maxActName1 = WindowService.lastExecutedAction ? WindowService.lastExecutedAction.action : "";
            const maxStateBeforeConfirm = WindowService.getWindowState(uuidA).maximized;
            // KWin confirms maximize
            WindowService.parseWindowStatesJson(JSON.stringify([{ id: uuidA, maximized: true, maximizeMode: 3 }]));
            const maxStateAfterConfirm = WindowService.getWindowState(uuidA).maximized;
            const maxRedundantDispatch = WindowService.setWindowMaximized(uuidA, true);
            const unmaxDispatchA = WindowService.toggleMaximizeWindow(uuidA);
            const maxActName2 = WindowService.lastExecutedAction ? WindowService.lastExecutedAction.action : "";
            WindowService.parseWindowStatesJson(JSON.stringify([{ id: uuidA, maximized: false, maximizeMode: 0 }]));
            const maxStateAfterRestore = WindowService.getWindowState(uuidA).maximized;

            // Restricted window B rejects maximize
            const maxRejectB = WindowService.toggleMaximizeWindow(uuidB);

            // 2. Minimize / Restore + non-minimizable restoration safety
            const minDispatchA = WindowService.toggleMinimizeWindow(uuidA);
            const minActName1 = WindowService.lastExecutedAction ? WindowService.lastExecutedAction.action : "";
            const minStateBeforeConfirm = WindowService.getWindowState(uuidA).minimized;
            WindowService.parseWindowStatesJson(JSON.stringify([{ id: uuidA, minimized: true }]));
            const minStateAfterConfirm = WindowService.getWindowState(uuidA).minimized;
            const unminDispatchA = WindowService.toggleMinimizeWindow(uuidA);
            const minActName2 = WindowService.lastExecutedAction ? WindowService.lastExecutedAction.action : "";
            WindowService.parseWindowStatesJson(JSON.stringify([{ id: uuidA, minimized: false }]));

            const minRejectB = WindowService.toggleMinimizeWindow(uuidB);
            // If KWin marks uuidB as minimized despite minimizable:false, restoring it must still be allowed
            WindowService.parseWindowStatesJson(JSON.stringify([{ id: uuidB, minimized: true, minimizable: false }]));
            const canRestoreMinimizedB = WindowService.canMinimizeWindow(uuidB);
            const restoreMinimizedB = WindowService.toggleMinimizeWindow(uuidB);
            WindowService.parseWindowStatesJson(JSON.stringify([{ id: uuidB, minimized: false, minimizable: false }]));

            // 3. Fullscreen toggle
            const fsDispatchA = WindowService.toggleFullScreenWindow(uuidA);
            const fsBeforeConfirm = WindowService.getWindowState(uuidA).fullScreen;
            WindowService.parseWindowStatesJson(JSON.stringify([{ id: uuidA, fullScreen: true }]));
            const fsAfterConfirm = WindowService.getWindowState(uuidA).fullScreen;
            const fsExitDispatchA = WindowService.toggleFullScreenWindow(uuidA);
            WindowService.parseWindowStatesJson(JSON.stringify([{ id: uuidA, fullScreen: false }]));
            const fsRejectB = WindowService.toggleFullScreenWindow(uuidB);

            // 4. Keep Above / Always on Top toggle
            const kaDispatchA = WindowService.toggleKeepAboveWindow(uuidA);
            const kaBeforeConfirm = WindowService.getWindowState(uuidA).keepAbove;
            WindowService.parseWindowStatesJson(JSON.stringify([{ id: uuidA, keepAbove: true }]));
            const kaAfterConfirm = WindowService.getWindowState(uuidA).keepAbove;
            const kaOffDispatchA = WindowService.toggleKeepAboveWindow(uuidA);
            WindowService.parseWindowStatesJson(JSON.stringify([{ id: uuidA, keepAbove: false }]));
            const kaRejectB = WindowService.toggleKeepAboveWindow(uuidB);

            // 5. Move window to Virtual Desktop & All Desktops
            const targetsDeskInitial = WindowService.getTargetDesktopsForWindow(uuidA).map(d => d.id);
            const moveSameDesk = WindowService.moveWindowToDesktop(uuidA, "desk-1");
            const moveUnknownDesk = WindowService.moveWindowToDesktop(uuidA, "desk-999");
            const moveBadDesk = WindowService.moveWindowToDesktop(uuidA, "desk-2;rm");
            const moveDesk2Dispatch = WindowService.moveWindowToDesktop(uuidA, "desk-2");
            const desksBeforeConfirm = WindowService.getWindowDesktops(uuidA);
            WindowService.parseWindowStatesJson(JSON.stringify([{ id: uuidA, onAllDesktops: false, desktops: ["desk-2"] }]));
            const desksAfterConfirm = WindowService.getWindowDesktops(uuidA);
            const targetsDeskAfterMove2 = WindowService.getTargetDesktopsForWindow(uuidA).map(d => d.id);

            const moveAllDesksDispatch = WindowService.moveWindowToDesktop(uuidA, "all");
            WindowService.parseWindowStatesJson(JSON.stringify([{ id: uuidA, onAllDesktops: true, desktops: [] }]));
            const desksAfterAll = WindowService.getWindowDesktops(uuidA);
            const moveAllDesksRedundant = WindowService.moveWindowToDesktop(uuidA, "all");
            const targetsDeskWhenOnAll = WindowService.getTargetDesktopsForWindow(uuidA).map(d => d.id);

            // Single-desktop environment disables moveWindowToDesktop
            WindowService.desktopsOverride = [{ id: "desk-1", name: "Desktop 1", index: 0 }];
            const singleDeskTargets = WindowService.getTargetDesktopsForWindow(uuidA);
            const singleDeskMoveAttempt = WindowService.moveWindowToDesktop(uuidA, "desk-1");

            // 6. Restricted close & output movement + stale/invalid UUIDs
            const closeRejectB = WindowService.closeWindow(uuidB);
            const moveOutRejectB = WindowService.moveWindowToOutput(uuidB, "DP-2");
            WindowService.lastExecutedAction = null;
            const staleMax = WindowService.toggleMaximizeWindow(staleUuid);
            const staleDesk = WindowService.moveWindowToDesktop(staleUuid, "desk-2");
            const invalidMax = WindowService.toggleMaximizeWindow("not_a_uuid");
            const actionAfterStale = WindowService.lastExecutedAction;

            // 7. DockMenu triggerWindowAction integration
            const menuMaxOk = menu.triggerWindowAction(uuidA, "maximize", "");
            const menuMaxRejectB = menu.triggerWindowAction(uuidB, "maximize", "");

            console.log("PHASE1_WINDOW_ACTIONS_RESULT:" + JSON.stringify({
                capsA: capsA,
                capsB: capsB,
                maxDispatchA: maxDispatchA,
                maxActName1: maxActName1,
                maxStateBeforeConfirm: maxStateBeforeConfirm,
                maxStateAfterConfirm: maxStateAfterConfirm,
                maxRedundantDispatch: maxRedundantDispatch,
                unmaxDispatchA: unmaxDispatchA,
                maxActName2: maxActName2,
                maxStateAfterRestore: maxStateAfterRestore,
                maxRejectB: maxRejectB,
                minDispatchA: minDispatchA,
                minActName1: minActName1,
                minStateBeforeConfirm: minStateBeforeConfirm,
                minStateAfterConfirm: minStateAfterConfirm,
                unminDispatchA: unminDispatchA,
                minActName2: minActName2,
                minRejectB: minRejectB,
                canRestoreMinimizedB: canRestoreMinimizedB,
                restoreMinimizedB: restoreMinimizedB,
                fsDispatchA: fsDispatchA,
                fsBeforeConfirm: fsBeforeConfirm,
                fsAfterConfirm: fsAfterConfirm,
                fsExitDispatchA: fsExitDispatchA,
                fsRejectB: fsRejectB,
                kaDispatchA: kaDispatchA,
                kaBeforeConfirm: kaBeforeConfirm,
                kaAfterConfirm: kaAfterConfirm,
                kaOffDispatchA: kaOffDispatchA,
                kaRejectB: kaRejectB,
                targetsDeskInitial: targetsDeskInitial,
                moveSameDesk: moveSameDesk,
                moveUnknownDesk: moveUnknownDesk,
                moveBadDesk: moveBadDesk,
                moveDesk2Dispatch: moveDesk2Dispatch,
                desksBeforeConfirm: desksBeforeConfirm,
                desksAfterConfirm: desksAfterConfirm,
                targetsDeskAfterMove2: targetsDeskAfterMove2,
                moveAllDesksDispatch: moveAllDesksDispatch,
                desksAfterAll: desksAfterAll,
                moveAllDesksRedundant: moveAllDesksRedundant,
                targetsDeskWhenOnAll: targetsDeskWhenOnAll,
                singleDeskTargets: singleDeskTargets,
                singleDeskMoveAttempt: singleDeskMoveAttempt,
                closeRejectB: closeRejectB,
                moveOutRejectB: moveOutRejectB,
                staleMax: staleMax,
                staleDesk: staleDesk,
                invalidMax: invalidMax,
                actionAfterStale: actionAfterStale,
                menuMaxOk: menuMaxOk,
                menuMaxRejectB: menuMaxRejectB
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
                    timeout=8
                )
                combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
                marker = "PHASE1_WINDOW_ACTIONS_RESULT:"
                self.assertIn(marker, combined, f"Missing marker in output:\n{combined}")
                payload_line = [line for line in combined.splitlines() if marker in line][-1]
                data = json.loads(payload_line.split(marker, 1)[1].strip())

                # Capabilities for normal vs restricted window
                self.assertTrue(all(data["capsA"].values()))
                self.assertTrue(data["capsB"]["valid"])
                self.assertTrue(data["capsB"]["activate"])
                self.assertFalse(data["capsB"]["minimize"])
                self.assertFalse(data["capsB"]["maximize"])
                self.assertFalse(data["capsB"]["fullscreen"])
                self.assertFalse(data["capsB"]["keepAbove"])
                self.assertFalse(data["capsB"]["close"])
                self.assertFalse(data["capsB"]["moveToOutput"])
                self.assertTrue(data["capsB"]["moveToDesktop"])

                # Maximize / Unmaximize
                self.assertTrue(data["maxDispatchA"])
                self.assertEqual(data["maxActName1"], "maximize")
                self.assertFalse(data["maxStateBeforeConfirm"])
                self.assertTrue(data["maxStateAfterConfirm"])
                self.assertFalse(data["maxRedundantDispatch"])
                self.assertTrue(data["unmaxDispatchA"])
                self.assertEqual(data["maxActName2"], "unmaximize")
                self.assertFalse(data["maxStateAfterRestore"])
                self.assertFalse(data["maxRejectB"])

                # Minimize / Restore
                self.assertTrue(data["minDispatchA"])
                self.assertEqual(data["minActName1"], "minimize")
                self.assertFalse(data["minStateBeforeConfirm"])
                self.assertTrue(data["minStateAfterConfirm"])
                self.assertTrue(data["unminDispatchA"])
                self.assertEqual(data["minActName2"], "unminimize")
                self.assertFalse(data["minRejectB"])
                self.assertTrue(data["canRestoreMinimizedB"])
                self.assertTrue(data["restoreMinimizedB"])

                # Fullscreen
                self.assertTrue(data["fsDispatchA"])
                self.assertFalse(data["fsBeforeConfirm"])
                self.assertTrue(data["fsAfterConfirm"])
                self.assertTrue(data["fsExitDispatchA"])
                self.assertFalse(data["fsRejectB"])

                # Keep Above
                self.assertTrue(data["kaDispatchA"])
                self.assertFalse(data["kaBeforeConfirm"])
                self.assertTrue(data["kaAfterConfirm"])
                self.assertTrue(data["kaOffDispatchA"])
                self.assertFalse(data["kaRejectB"])

                # Move to Virtual Desktop
                self.assertEqual(data["targetsDeskInitial"], ["desk-2", "desk-3"])
                self.assertFalse(data["moveSameDesk"])
                self.assertFalse(data["moveUnknownDesk"])
                self.assertFalse(data["moveBadDesk"])
                self.assertTrue(data["moveDesk2Dispatch"])
                self.assertEqual(data["desksBeforeConfirm"], ["desk-1"])
                self.assertEqual(data["desksAfterConfirm"], ["desk-2"])
                self.assertEqual(data["targetsDeskAfterMove2"], ["desk-1", "desk-3"])
                self.assertTrue(data["moveAllDesksDispatch"])
                self.assertEqual(data["desksAfterAll"], ["all"])
                self.assertFalse(data["moveAllDesksRedundant"])
                self.assertEqual(data["targetsDeskWhenOnAll"], ["desk-1", "desk-2", "desk-3"])
                self.assertEqual(data["singleDeskTargets"], [])
                self.assertFalse(data["singleDeskMoveAttempt"])

                # Restricted close / output move + stale / invalid UUIDs
                self.assertFalse(data["closeRejectB"])
                self.assertFalse(data["moveOutRejectB"])
                self.assertFalse(data["staleMax"])
                self.assertFalse(data["staleDesk"])
                self.assertFalse(data["invalidMax"])
                self.assertIsNone(data["actionAfterStale"])

                # DockMenu integration
                self.assertTrue(data["menuMaxOk"])
                self.assertFalse(data["menuMaxRejectB"])
            finally:
                if os.path.exists(probe_path):
                    os.remove(probe_path)

    def test_20_xdg_desktop_quick_actions_fixtures_and_runtime(self):
        """Phase 2 (P0 #6): Verify XDG Desktop Entry Quick Actions parsing, ordering, localization, field code safety, identity isolation, and DockMenu runtime execution."""
        import json
        import sys
        import tempfile

        apps_dir = os.path.join(REPO_DIR, "services", "applications")
        if apps_dir not in sys.path:
            sys.path.insert(0, apps_dir)
        import importlib
        import scan_apps
        importlib.reload(scan_apps)

        fixture_dir = os.path.join(REPO_DIR, "tests", "fixtures", "applications")
        apps_en = scan_apps.scan_all(extra_dirs=[fixture_dir], locale="C")
        apps_tr = scan_apps.scan_all(extra_dirs=[fixture_dir], locale="tr_TR.UTF-8")

        by_id_en = {a["id"]: a for a in apps_en}
        by_id_tr = {a["id"]: a for a in apps_tr}

        self.assertIn("org.mozilla.firefox", by_id_en)
        self.assertIn("org.kde.dolphin", by_id_en)
        self.assertNotIn("org.example.hidden", by_id_en)

        ff_en = by_id_en["org.mozilla.firefox"]
        ff_tr = by_id_tr["org.mozilla.firefox"]
        dolphin_en = by_id_en["org.kde.dolphin"]

        # 1. Exact action ordering & invalid/undeclared/GNOME-only filtering
        self.assertEqual([a["id"] for a in ff_en["actions"]], ["new-window", "new-private-window", "profile-manager"])
        self.assertEqual([a["name"] for a in ff_en["actions"]], ["New Window", "New Private Window", "Profile Manager"])

        # 2. Localized action names (tr_TR.UTF-8 falls back from [tr_TR] to [tr] to default)
        self.assertEqual([a["name"] for a in ff_tr["actions"]], ["Yeni Pencere", "Yeni Gizli Pencere", "Profil Yöneticisi"])

        # 3. Field codes & quoting safety
        self.assertEqual(ff_en["actions"][0]["execArgs"], ["firefox", "--new-window"])
        self.assertEqual(ff_en["actions"][1]["execArgs"], ["firefox", "--private-window", "https://example.org/?progress=100%"])
        self.assertEqual(ff_en["actions"][2]["execArgs"], ["firefox", "--ProfileManager", "--icon", "user-identity", "Profile Manager"])

        # 4. Applications without quick actions have empty actions list
        self.assertEqual(dolphin_en["actions"], [])

        # 5. Action commands / icons / names are never added to application identity aliases
        for forbidden_alias in ["hijack-binary", "hijack-icon", "window-new", "view-private", "user-identity", "profile manager"]:
            self.assertNotIn(forbidden_alias, ff_en["aliases"])

        # 6. Live QML Runtime Test with ApplicationService & DockMenu
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["XDG_CONFIG_HOME"] = tmpdir
            probe_path = os.path.join(REPO_DIR, "_test_phase2_quick_actions_probe.qml")
            try:
                with open(probe_path, "w") as pf:
                    pf.write("""import QtQuick
import Quickshell
import "./services"
import "./modules/dock"

Scope {
    DockMenu {
        id: ffMenu
        appId: "org.mozilla.firefox"
        isRunning: true
        isPinned: true
    }

    DockMenu {
        id: dolphinMenu
        appId: "org.kde.dolphin"
        isRunning: false
        isPinned: true
    }

    Timer {
        interval: 200
        running: true
        repeat: false
        onTriggered: {
            ApplicationService.launchDryRun = true;
            ApplicationService.applications = """ + json.dumps(apps_en) + """;
            ApplicationService.loading = false;

            const ffActions = ApplicationService.getAppActions("org.mozilla.firefox");
            const dolphinActions = ApplicationService.getAppActions("org.kde.dolphin");
            const unknownActions = ApplicationService.getAppActions("nonexistent.app");

            // Verify action names/binaries are not mistaken for app identities
            const hijackLookup = ApplicationService.getAppById("hijack-binary");
            const actionIconLookup = ApplicationService.findAppByTitleOrIcon("Some Title", "view-private", "", "", "");

            // Trigger valid quick action via DockMenu
            const privOk = ffMenu.triggerQuickAction("new-private-window");
            const privCmd = ApplicationService.lastLaunchedCommand;

            const profOk = ffMenu.triggerQuickAction("profile-manager");
            const profCmd = ApplicationService.lastLaunchedCommand;

            // Reject invalid / nonexistent quick actions
            const badActOk = ffMenu.triggerQuickAction("undeclared-action");
            const dolphinActOk = dolphinMenu.triggerQuickAction("new-window");

            // Normal app launch still works
            const normalDolphinOk = ApplicationService.launchAppId("org.kde.dolphin");
            const normalDolphinCmd = ApplicationService.lastLaunchedCommand;

            // Verify parseExecArguments rejects unbalanced quotes in QML as well
            const unbalancedParsed = ApplicationService.parseExecArguments('firefox "unterminated');

            console.log("PHASE2_QUICK_ACTIONS_RESULT:" + JSON.stringify({
                ffActionIds: ffActions.map(a => a.id),
                ffMenuActionIds: (ffMenu.appActions || []).map(a => a.id),
                ffHasCustomNewWin: ffMenu.hasCustomNewWindowAction,
                dolphinHasCustomNewWin: dolphinMenu.hasCustomNewWindowAction,
                dolphinActionsLen: dolphinActions.length,
                unknownActionsLen: unknownActions.length,
                hijackLookupNull: hijackLookup === null,
                actionIconLookupNull: actionIconLookup === null,
                privOk: privOk,
                privCmd: privCmd,
                profOk: profOk,
                profCmd: profCmd,
                badActOk: badActOk,
                dolphinActOk: dolphinActOk,
                normalDolphinOk: normalDolphinOk,
                normalDolphinCmd: normalDolphinCmd,
                unbalancedLen: unbalancedParsed.length
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
                    timeout=8
                )
                combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
                marker = "PHASE2_QUICK_ACTIONS_RESULT:"
                self.assertIn(marker, combined, f"Missing marker in output:\n{combined}")
                payload_line = [line for line in combined.splitlines() if marker in line][-1]
                data = json.loads(payload_line.split(marker, 1)[1].strip())

                self.assertEqual(data["ffActionIds"], ["new-window", "new-private-window", "profile-manager"])
                self.assertEqual(data["ffMenuActionIds"], ["new-window", "new-private-window", "profile-manager"])
                self.assertTrue(data["ffHasCustomNewWin"])
                self.assertFalse(data["dolphinHasCustomNewWin"])
                self.assertEqual(data["dolphinActionsLen"], 0)
                self.assertEqual(data["unknownActionsLen"], 0)
                self.assertTrue(data["hijackLookupNull"])
                self.assertTrue(data["actionIconLookupNull"])

                self.assertTrue(data["privOk"])
                self.assertEqual(data["privCmd"]["type"], "action")
                self.assertEqual(data["privCmd"]["actionId"], "new-private-window")
                self.assertEqual(data["privCmd"]["args"], ["firefox", "--private-window", "https://example.org/?progress=100%"])

                self.assertTrue(data["profOk"])
                self.assertEqual(data["profCmd"]["args"], ["firefox", "--ProfileManager", "--icon", "user-identity", "Profile Manager"])

                self.assertFalse(data["badActOk"])
                self.assertFalse(data["dolphinActOk"])

                self.assertTrue(data["normalDolphinOk"])
                self.assertEqual(data["normalDolphinCmd"]["type"], "app")
                self.assertEqual(data["normalDolphinCmd"]["appId"], "org.kde.dolphin")
                self.assertEqual(data["unbalancedLen"], 0)
            finally:
                if os.path.exists(probe_path):
                    os.remove(probe_path)

if __name__ == "__main__":
    unittest.main()
