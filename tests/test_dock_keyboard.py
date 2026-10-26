#!/usr/bin/env python3
"""
P0 #7 Keyboard Accessibility verification.

Layers (kept distinct):
  * STATIC    - source contract checks (no Wayland/KWin keyboard-grab claims).
  * OFFSCREEN - real DockItem / IconButton / DockKeyboardNav / DockMenu / WindowChooserPopup
                driven by QtTest key + mouse events in `QT_QPA_PLATFORM=offscreen`, isolated
                XDG_CONFIG_HOME and WindowService overrides (no KWin/qdbus calls).
                The harness window re-implements ONLY the thin Dock window API
                (delegation to DockKeyboardNav); the real PanelWindow cannot run offscreen.
  * PHYSICAL  - NOT covered here: compositor keyboard-focus grant on a real KWin Wayland session.
"""

import json
import os
import subprocess
import tempfile
import unittest

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WFF1 = "0_{11111111-1111-1111-1111-111111111111}"
WFF2 = "0_{22222222-2222-2222-2222-222222222222}"
WKON = "0_{55555555-5555-5555-5555-555555555555}"


def read(rel):
    with open(os.path.join(REPO_DIR, rel)) as f:
        return f.read()


def layout_block(kind, vertical):
    """Dock-shaped layout: launcher, pinned, unpinned running, settings (+ separators)."""
    tag = "ColumnLayout" if vertical else "RowLayout"
    p = "v" if vertical else "h"
    return f"""
    {tag} {{
        id: {p}Layout
        visible: win.isVertical === {"true" if vertical else "false"}
        x: 20
        y: 20
        spacing: 4
        IconButton {{
            id: {p}Launcher
            parentWindow: win
            edge: win.edge
            size: 40
            icon: "start-here-kde"
            tooltip: "Applications"
            onClicked: win.launcherClicks++
        }}
        DockSeparator {{ isVertical: {"true" if vertical else "false"} }}
        Repeater {{
            id: {p}Pinned
            model: ApplicationService.pinnedApps
            DockItem {{
                required property var modelData
                parentWindowRef: win
                appId: modelData
                app: ApplicationService.getAppById(modelData)
            }}
        }}
        DockSeparator {{ isVertical: {"true" if vertical else "false"} }}
        Repeater {{
            id: {p}Running
            model: ["org.kde.kate"]
            DockItem {{
                required property var modelData
                parentWindowRef: win
                appId: modelData
                app: ApplicationService.getAppById(modelData)
            }}
        }}
        DockSeparator {{ isVertical: {"true" if vertical else "false"} }}
        IconButton {{
            id: {p}Settings
            parentWindow: win
            edge: win.edge
            size: 40
            icon: "preferences-system"
            tooltip: "Settings"
            onClicked: win.settingsClicks++
        }}
    }}
"""


HARNESS = """import QtQuick
import QtQuick.Layouts
import QtTest
import Quickshell
import "./services"
import "./components"
import "./modules/dock"

FloatingWindow {
    id: win
    implicitWidth: 900
    implicitHeight: 700
    visible: true

    property string edge: "bottom"
    readonly property bool isVertical: edge === "left" || edge === "right"
    property var activePopupItem: null
    readonly property bool hasActivePopup: activePopupItem !== null
    property var activeDragItem: null
    readonly property bool isDragging: activeDragItem !== null
    property bool isRevealed: true
    property bool keyboardNavActive: false
    property var focusedDockItem: null
    property int launcherClicks: 0
    property int settingsClicks: 0

    onFocusedDockItemChanged: { if (focusedDockItem) nav.lastItem = focusedDockItem; }

    // Mirrors the Dock.qml window API (thin delegation to DockKeyboardNav).
    function getFocusableDockItems() { return nav.items(); }
    function moveDockFocus(from, step) { return nav.move(from, step); }
    function focusDockBoundary(last) { return nav.boundary(last); }
    function tabDockFocus(from, step) {
        if (nav.tabStep(from, step)) return true;
        win.releaseKeyboardFocus();
        return false;
    }
    function requestKeyboardFocus() {
        win.keyboardNavActive = true;
        return nav.focusInitial();
    }
    function releaseKeyboardFocus() {
        if (win.focusedDockItem) win.focusedDockItem.focus = false;
        win.focusedDockItem = null;
        win.activePopupItem = null;
        win.keyboardNavActive = false;
    }

    DockKeyboardNav {
        id: nav
        layout: win.isVertical ? vLayout : hLayout
    }
""" + layout_block("h", False) + layout_block("v", True) + """
    TestCase {
        id: tc
        name: "DockKeyboard"
        when: false
        property var partial: null

        function names(list) {
            const out = [];
            for (let i = 0; i < list.length; i++) out.push(list[i].Accessible.name);
            return out;
        }
        function focusName() {
            return win.focusedDockItem ? win.focusedDockItem.Accessible.name : "";
        }
        function itemFor(rep, appId) {
            for (let i = 0; i < rep.count; i++) if (rep.itemAt(i).appId === appId) return rep.itemAt(i);
            return null;
        }
        function allMouseAreas(item, out) {
            const kids = item.children;
            for (let i = 0; i < kids.length; i++) {
                const c = kids[i];
                if (!c || !c.visible) continue;
                if (c.acceptedButtons !== undefined && c.containsMouse !== undefined) out.push(c);
                allMouseAreas(c, out);
            }
            return out;
        }

        function runTests() {
            const R = {};
            tc.partial = R;
            wait(50);
            wait(50);
            WindowService.outputsOverride = ["eDP-1"];
            WindowService.desktopsOverride = [{ id: "d1", name: "Desktop 1", index: 0 }];
            ApplicationService.applications = [
                { id: "org.kde.dolphin", name: "Dolphin", icon: "system-file-manager", aliases: ["org.kde.dolphin", "dolphin"] },
                { id: "org.kde.konsole", name: "Konsole", icon: "utilities-terminal", aliases: ["org.kde.konsole", "konsole"] },
                { id: "org.mozilla.firefox", name: "Firefox", icon: "org.mozilla.firefox", aliases: ["org.mozilla.firefox", "firefox"] },
                { id: "systemsettings", name: "System Settings", icon: "preferences-system", aliases: ["systemsettings"] },
                { id: "org.kde.kate", name: "Kate", icon: "kate", aliases: ["org.kde.kate", "kate"] }
            ];
            ApplicationService.loading = false;
            const raw = [
                '[Argument: (sssida{sv}) "' + "WFF1" + '", "FF 1", "org.mozilla.firefox", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "' + "WFF2" + '", "FF 2", "org.mozilla.firefox", 100, 1.0, [Argument: a{sv} {}]]',
                '[Argument: (sssida{sv}) "' + "WKON" + '", "Konsole 1", "org.kde.konsole", 100, 1.0, [Argument: a{sv} {}]]',
                '===KWIN_META:' + "WFF1" + '\\torg.mozilla.firefox\\torg.mozilla.firefox\\t===',
                '===KWIN_META:' + "WFF2" + '\\torg.mozilla.firefox\\torg.mozilla.firefox\\t===',
                '[Argument: (sssida{sv}) "0_{66666666-6666-6666-6666-666666666666}", "Kate 1", "org.kde.kate", 100, 1.0, [Argument: a{sv} {}]]',
                '===KWIN_META:' + "WKON" + '\\torg.kde.konsole\\torg.kde.konsole\\t===',
                '===KWIN_META:0_{66666666-6666-6666-6666-666666666666}\\torg.kde.kate\\torg.kde.kate\\t==='
            ].join("\\n");
            WindowService.handleScannerOutput(raw);
            WindowService.activeWindowId = "";
            wait(80);

            R.pinned = ApplicationService.pinnedApps.slice();

            // ---- 1. Horizontal order: launcher, pinned, unpinned running, settings -------
            ConfigService.setDockEdge("bottom");
            win.edge = "bottom";
            wait(30);
            R.hOrder = names(win.getFocusableDockItems());
            R.hItemCount = win.getFocusableDockItems().length;
            R.sepsFocusable = false;
            for (let i = 0; i < hLayout.children.length; i++) {
                const c = hLayout.children[i];
                if (c && c.activeFocusOnTab === true && c.Accessible.role === Accessible.Separator) R.sepsFocusable = true;
            }
            R.hiddenLayoutItems = vLayout.children.length > 0 ? vLayout.visible : false;

            R.entry = win.requestKeyboardFocus();
            wait(30);
            R.entryFocus = focusName();
            R.entryActive = hLauncher.activeFocus;

            // Right x N, wrap
            const seqRight = [];
            for (let i = 0; i < R.hItemCount; i++) { keyClick(Qt.Key_Right); wait(5); seqRight.push(focusName()); }
            R.seqRight = seqRight;
            keyClick(Qt.Key_Left); wait(5);
            R.leftFromFirstWrap = focusName();   // after full cycle we are on launcher; Left wraps to settings
            keyClick(Qt.Key_Home); wait(5);
            R.home = focusName();
            keyClick(Qt.Key_End); wait(5);
            R.end = focusName();
            // Up/Down must not navigate on a horizontal dock
            keyClick(Qt.Key_Down); wait(5);
            R.downOnHoriz = focusName();
            keyClick(Qt.Key_Up); wait(5);
            R.upOnHoriz = focusName();

            // ---- 2. Tab / Shift+Tab, no trap -------------------------------------------
            keyClick(Qt.Key_Home); wait(5);
            const tabSeq = [focusName()];
            for (let i = 0; i < R.hItemCount - 1; i++) { keyClick(Qt.Key_Tab); wait(5); tabSeq.push(focusName()); }
            R.tabSeq = tabSeq;
            keyClick(Qt.Key_Tab); wait(5);
            R.tabPastEndReleased = (win.focusedDockItem === null && win.keyboardNavActive === false);
            win.requestKeyboardFocus(); wait(20);
            R.reentryRestored = focusName();     // last item (Settings) restored
            keyClick(Qt.Key_Home); wait(5);
            keyClick(Qt.Key_Backtab); wait(5);
            R.backtabBeforeStartReleased = (win.focusedDockItem === null && win.keyboardNavActive === false);

            // ---- 3. Disabled / hidden items skipped -------------------------------------
            hSettings.enabled = false;
            wait(10);
            R.orderWithoutSettings = names(win.getFocusableDockItems());
            hSettings.enabled = true;
            wait(10);

            // ---- 4. Enter / Space activation --------------------------------------------
            win.requestKeyboardFocus(); wait(20);
            keyClick(Qt.Key_Home); wait(5);
            keyClick(Qt.Key_Return); wait(5);
            R.launcherEnter = win.launcherClicks;
            keyClick(Qt.Key_Space); wait(5);
            R.launcherSpace = win.launcherClicks;
            keyClick(Qt.Key_End); wait(5);
            keyClick(Qt.Key_Enter); wait(5);
            R.settingsEnter = win.settingsClicks;

            const kon = itemFor(hPinned, "org.kde.konsole");
            kon.forceActiveFocus(); wait(10);
            WindowService.activeWindowId = "";
            WindowService.lastExecutedAction = null;
            keyClick(Qt.Key_Return); wait(10);
            R.konEnter = WindowService.lastExecutedAction ? WindowService.lastExecutedAction.windowId : "";
            WindowService.activeWindowId = "";
            WindowService.lastExecutedAction = null;
            keyClick(Qt.Key_Space); wait(10);
            R.konSpace = WindowService.lastExecutedAction ? WindowService.lastExecutedAction.windowId : "";

            // ---- 5. Context menu keyboard access + enabled-only navigation --------------
            kon.forceActiveFocus(); wait(10);
            keyClick(Qt.Key_Menu); wait(80);
            R.menuOpen = kon.menuOpen;
            R.menuIsActivePopup = (win.activePopupItem === kon);
            const popup = kon.currentPopupItem();
            R.menuPopupExists = popup !== null;
            R.menuInitialTarget = popup && popup.keyboardTarget !== null;
            const all = allMouseAreas(popup.surface, []);
            const acts = popup.keyboardActions();
            R.menuActionCount = acts.length;
            R.menuAllEnabled = acts.every(a => a.enabled === true && a.visible === true);
            const seen = [];
            const first = popup.keyboardTarget;
            seen.push(first);
            for (let i = 0; i < acts.length; i++) {
                keyClick(Qt.Key_Down); wait(5);
                seen.push(popup.keyboardTarget);
            }
            R.menuWrapsToFirst = (seen[seen.length - 1] === first);
            R.menuUniqueTargets = (new Set(seen.slice(0, acts.length))).size === acts.length;
            keyClick(Qt.Key_End); wait(5);
            const lastT = popup.keyboardTarget;
            R.menuEndIsLast = (lastT === acts[acts.length - 1]);
            keyClick(Qt.Key_Home); wait(5);
            R.menuHomeIsFirst = (popup.keyboardTarget === acts[0]);
            keyClick(Qt.Key_Up); wait(5);
            R.menuUpWrapsToLast = (popup.keyboardTarget === acts[acts.length - 1]);
            keyClick(Qt.Key_Tab); wait(5);
            R.menuTabToFirst = (popup.keyboardTarget === acts[0]);
            keyClick(Qt.Key_Backtab); wait(5);
            R.menuBacktabToLast = (popup.keyboardTarget === acts[acts.length - 1]);
            R.menuRing = popup.keyboardRing !== null && popup.keyboardRing.visible;
            // Enter on first action (activate window) closes the menu, keeps dock focus
            keyClick(Qt.Key_Home); wait(5);
            WindowService.lastExecutedAction = null;
            keyClick(Qt.Key_Return); wait(30);
            R.menuEnterAction = WindowService.lastExecutedAction ? WindowService.lastExecutedAction.action : "";
            R.menuClosedAfterEnter = (kon.menuOpen === false && win.activePopupItem === null);
            R.focusAfterMenuEnter = kon.activeFocus;

            // Disabled action skipped: dolphin is first pinned -> "Move Left" disabled
            const dol = itemFor(hPinned, "org.kde.dolphin");
            dol.forceActiveFocus(); wait(10);
            keyClick(Qt.Key_Menu); wait(80);
            const dpop = dol.currentPopupItem();
            const dall = allMouseAreas(dpop.surface, []);
            const dacts = dpop.keyboardActions();
            R.dolphinAllVsActions = [dall.length, dacts.length];
            R.dolphinSkipsDisabled = dacts.length < dall.length && dacts.every(a => a.enabled);
            // Escape closes popup, focus stays on item
            keyClick(Qt.Key_Escape); wait(30);
            R.escClosesMenu = (dol.menuOpen === false && win.activePopupItem === null);
            R.escFocusRestored = dol.activeFocus;
            R.escDockStillActive = win.keyboardNavActive;
            // Second Escape leaves the dock
            keyClick(Qt.Key_Escape); wait(10);
            R.escReleasesDock = (win.keyboardNavActive === false && win.focusedDockItem === null);

            // ---- 6. Window chooser keyboard navigation ----------------------------------
            const ff = itemFor(hPinned, "firefox");
            ff.forceActiveFocus(); wait(10);
            WindowService.activeWindowId = "";
            keyClick(Qt.Key_Return); wait(80);
            R.chooserOpen = ff.chooserOpen;
            const cpop = ff.currentPopupItem();
            R.chooserPopup = cpop !== null;
            const cacts = cpop.keyboardActions();
            R.chooserActionCount = cacts.length;   // win1, close1, win2, close2, New Window
            R.chooserInitial = cpop.keyboardTarget === cacts[0];
            keyClick(Qt.Key_Down); wait(5);
            keyClick(Qt.Key_Down); wait(5);
            R.chooserThird = cpop.keyboardTarget === cacts[2];
            WindowService.lastExecutedAction = null;
            keyClick(Qt.Key_Space); wait(30);
            R.chooserSelected = WindowService.lastExecutedAction ? WindowService.lastExecutedAction.cleanId : "";
            R.chooserClosed = (ff.chooserOpen === false && win.activePopupItem === null);
            R.chooserFocusKept = ff.activeFocus;
            // Escape from chooser
            WindowService.activeWindowId = "";
            keyClick(Qt.Key_Return); wait(80);
            R.chooserReopen = ff.chooserOpen;
            keyClick(Qt.Key_Escape); wait(30);
            R.chooserEscClosed = (ff.chooserOpen === false);
            R.chooserEscFocus = ff.activeFocus;
            keyClick(Qt.Key_Escape); wait(10);

            // ---- 7. Vertical dock ------------------------------------------------------
            ConfigService.setDockEdge("left");
            win.edge = "left";
            wait(40);
            R.vOrder = names(win.getFocusableDockItems());
            win.requestKeyboardFocus(); wait(30);
            R.vEntry = focusName();
            keyClick(Qt.Key_Right); wait(5);
            R.vRightIgnored = focusName();
            keyClick(Qt.Key_Down); wait(5);
            R.vDown1 = focusName();
            keyClick(Qt.Key_Down); wait(5);
            R.vDown2 = focusName();
            keyClick(Qt.Key_Up); wait(5);
            R.vUp = focusName();
            keyClick(Qt.Key_Left); wait(5);
            R.vLeftIgnored = focusName();
            keyClick(Qt.Key_End); wait(5);
            R.vEnd = focusName();
            keyClick(Qt.Key_Down); wait(5);
            R.vWrapDown = focusName();
            keyClick(Qt.Key_Escape); wait(10);
            R.vReleased = (win.keyboardNavActive === false);

            // ---- 8. Mouse regression ---------------------------------------------------
            win.edge = "bottom";
            ConfigService.setDockEdge("bottom");
            wait(40);
            const kon2 = itemFor(hPinned, "org.kde.konsole");
            WindowService.activeWindowId = "";
            WindowService.lastExecutedAction = null;
            mouseClick(kon2, kon2.width / 2, kon2.height / 2, Qt.LeftButton);
            wait(30);
            R.mouseLeftActivates = WindowService.lastExecutedAction ? WindowService.lastExecutedAction.windowId : "";
            mouseClick(kon2, kon2.width / 2, kon2.height / 2, Qt.RightButton);
            wait(60);
            R.mouseRightMenu = kon2.menuOpen;
            R.mouseNoKeyboardFocusSteal = (win.keyboardNavActive === false);
            mouseClick(kon2, kon2.width / 2, kon2.height / 2, Qt.RightButton);
            wait(30);
            R.mouseRightToggleClose = (kon2.menuOpen === false);
            R.noFocusWithoutRequest = (win.focusedDockItem === null);

            console.log("DOCK_KEYBOARD_RESULT:" + JSON.stringify(R));
        }
    }

    Timer {
        interval: 300
        running: true
        repeat: false
        onTriggered: {
            try {
                tc.runTests();
            } catch (e) {
                console.log("DOCK_KEYBOARD_ERROR:" + e + " @ " + e.stack + " PARTIAL=" + JSON.stringify(tc.partial));
            }
            Qt.quit();
        }
    }
}
""".replace("WFF1", WFF1).replace("WFF2", WFF2).replace("WKON", WKON)


class TestDockKeyboardStatic(unittest.TestCase):
    """STATIC source contracts."""

    def test_01_dock_window_contract(self):
        dock = read("modules/dock/Dock.qml")
        self.assertIn("DockKeyboardNav {", dock)
        self.assertIn("function requestKeyboardFocus()", dock)
        self.assertIn("function releaseKeyboardFocus()", dock)
        self.assertIn("function tabDockFocus(", dock)
        # Never grabs keyboard focus on its own: None unless explicitly requested.
        self.assertIn("WlrLayershell.keyboardFocus: keyboardNavActive ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None", dock)
        self.assertNotIn("WlrKeyboardFocus.Exclusive", dock)
        self.assertIn("property bool keyboardNavActive: false", dock)
        # Reveal when keyboard-driven, re-arm hide timer when released.
        self.assertIn("|| keyboardNavActive\n", dock)
        self.assertIn("if (!keyboardNavActive && autoHide", dock)
        # Local IPC entry only; no global shortcut API or KDE shortcut configuration.
        self.assertIn("IpcHandler", dock)
        for forbidden in ("GlobalShortcut", "kglobalaccel", "kwriteconfig", "khotkeys"):
            self.assertNotIn(forbidden, dock)
        # Focus loss hands focus back instead of trapping it.
        self.assertIn("Window.onActiveChanged", dock)

    def test_02_roles_names_and_focus_indicators(self):
        item = read("modules/dock/DockItem.qml")
        self.assertIn("Accessible.role: Accessible.Button", item)
        self.assertIn("Accessible.name: root.accessibleLabel", item)
        self.assertIn("Accessible.focused: root.activeFocus", item)
        self.assertIn("id: focusRing", item)
        self.assertIn("visible: root.activeFocus", item)
        btn = read("components/IconButton.qml")
        self.assertIn("Accessible.role: Accessible.Button", btn)
        self.assertIn("root.activeFocus ? Theme.accent", btn)
        sep = read("modules/dock/DockSeparator.qml")
        self.assertIn("activeFocusOnTab: false", sep)
        self.assertIn("Accessible.ignored: true", sep)
        popup = read("components/AnchoredPopup.qml")
        self.assertIn("Accessible.role: Accessible.PopupMenu", popup)
        self.assertIn("grabFocus: false", popup)
        menu = read("modules/dock/DockMenu.qml")
        chooser = read("modules/dock/WindowChooserPopup.qml")
        self.assertGreaterEqual(menu.count("Accessible.role: Accessible.MenuItem"), 14)
        self.assertEqual(chooser.count("Accessible.role: Accessible.MenuItem"), 3)
        # Every MouseArea in the menus/chooser is an accessible menu item.
        self.assertEqual(menu.count("MouseArea {"), menu.count("Accessible.role: Accessible.MenuItem"))
        self.assertEqual(chooser.count("MouseArea {"), chooser.count("Accessible.role: Accessible.MenuItem"))

    def test_03_no_new_polling_or_processes(self):
        for rel in ("modules/dock/DockKeyboardNav.qml",):
            src = read(rel)
            for forbidden in ("Timer", "Process", "execDetached", "SocketServer"):
                self.assertNotIn(forbidden, src)
        # DockItem keyboard path adds no Timer beyond the pre-existing dwell timer.
        self.assertEqual(read("modules/dock/DockItem.qml").count("Timer {"), 1)

    def test_04_mouse_dnd_paths_preserved(self):
        item = read("modules/dock/DockItem.qml")
        for needle in ("drag.target:", "function finishDrag()", "function handleWheel(delta)",
                       "acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton",
                       "root.toggleContextMenu();", "root.launchNewInstance();", "root.activateItem();"):
            self.assertIn(needle, item)


class TestDockKeyboardRuntime(unittest.TestCase):
    """OFFSCREEN simulated key/mouse events against real components."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        env = os.environ.copy()
        env["XDG_CONFIG_HOME"] = cls.tmp.name
        env["QT_QPA_PLATFORM"] = "offscreen"
        probe = os.path.join(REPO_DIR, "_test_dock_keyboard_probe.qml")
        try:
            with open(probe, "w") as f:
                f.write(HARNESS)
            proc = subprocess.run(
                ["quickshell", "-p", probe, "--no-duplicate"],
                cwd=REPO_DIR, env=env, capture_output=True, text=True, timeout=60,
            )
        finally:
            if os.path.exists(probe):
                os.remove(probe)
        combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
        marker = "DOCK_KEYBOARD_RESULT:"
        if "DOCK_KEYBOARD_ERROR:" in combined:
            raise AssertionError(combined[combined.index("DOCK_KEYBOARD_ERROR:"):][:2000])
        if marker not in combined:
            raise AssertionError("Missing marker in output:\n" + combined[-4000:])
        line = [l for l in combined.splitlines() if marker in l][-1]
        cls.R = json.loads(line.split(marker, 1)[1].strip())
        cls.output = combined

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_10_horizontal_focus_order_pinned_then_running(self):
        R = self.R
        self.assertEqual(R["pinned"], ["org.kde.dolphin", "org.kde.konsole", "firefox", "systemsettings"])
        expected = ["Applications", "Dolphin, pinned", "Konsole, running, pinned",
                    "Firefox, 2 windows, pinned", "System Settings, pinned", "Kate, running", "Settings"]
        self.assertEqual(R["hOrder"], expected)
        self.assertFalse(R["sepsFocusable"])

    def test_11_horizontal_arrow_home_end(self):
        R = self.R
        self.assertTrue(R["entry"])
        self.assertEqual(R["entryFocus"], "Applications")
        self.assertTrue(R["entryActive"])
        self.assertEqual(R["seqRight"], ["Dolphin, pinned", "Konsole, running, pinned",
                                         "Firefox, 2 windows, pinned", "System Settings, pinned",
                                         "Kate, running", "Settings", "Applications"])
        self.assertEqual(R["leftFromFirstWrap"], "Settings")
        self.assertEqual(R["home"], "Applications")
        self.assertEqual(R["end"], "Settings")
        # Up/Down are inert on a horizontal Dock
        self.assertEqual(R["downOnHoriz"], "Settings")
        self.assertEqual(R["upOnHoriz"], "Settings")

    def test_12_tab_shift_tab_no_trap(self):
        R = self.R
        self.assertEqual(R["tabSeq"], R["hOrder"])
        self.assertTrue(R["tabPastEndReleased"])
        self.assertEqual(R["reentryRestored"], "Settings")
        self.assertTrue(R["backtabBeforeStartReleased"])
        self.assertNotIn("Settings", R["orderWithoutSettings"])
        self.assertEqual(len(R["orderWithoutSettings"]), len(R["hOrder"]) - 1)

    def test_13_enter_space_activation(self):
        R = self.R
        self.assertEqual(R["launcherEnter"], 1)
        self.assertEqual(R["launcherSpace"], 2)
        self.assertEqual(R["settingsEnter"], 1)
        self.assertEqual(R["konEnter"], WKON)
        self.assertEqual(R["konSpace"], WKON)

    def test_14_context_menu_keyboard(self):
        R = self.R
        self.assertTrue(R["menuOpen"])
        self.assertTrue(R["menuIsActivePopup"])
        self.assertTrue(R["menuPopupExists"])
        self.assertTrue(R["menuInitialTarget"])
        self.assertGreaterEqual(R["menuActionCount"], 4)
        self.assertTrue(R["menuAllEnabled"])
        self.assertTrue(R["menuWrapsToFirst"])
        self.assertTrue(R["menuUniqueTargets"])
        self.assertTrue(R["menuEndIsLast"])
        self.assertTrue(R["menuHomeIsFirst"])
        self.assertTrue(R["menuUpWrapsToLast"])
        self.assertTrue(R["menuTabToFirst"])
        self.assertTrue(R["menuBacktabToLast"])
        self.assertTrue(R["menuRing"])
        self.assertEqual(R["menuEnterAction"], "activate")
        self.assertTrue(R["menuClosedAfterEnter"])
        self.assertTrue(R["focusAfterMenuEnter"])
        self.assertTrue(R["dolphinSkipsDisabled"], R["dolphinAllVsActions"])

    def test_15_escape_and_focus_restoration(self):
        R = self.R
        self.assertTrue(R["escClosesMenu"])
        self.assertTrue(R["escFocusRestored"])
        self.assertTrue(R["escDockStillActive"])
        self.assertTrue(R["escReleasesDock"])

    def test_16_window_chooser_keyboard(self):
        R = self.R
        self.assertTrue(R["chooserOpen"])
        self.assertTrue(R["chooserPopup"])
        self.assertEqual(R["chooserActionCount"], 5)
        self.assertTrue(R["chooserInitial"])
        self.assertTrue(R["chooserThird"])
        self.assertEqual(R["chooserSelected"], "22222222-2222-2222-2222-222222222222")
        self.assertTrue(R["chooserClosed"])
        self.assertTrue(R["chooserFocusKept"])
        self.assertTrue(R["chooserReopen"])
        self.assertTrue(R["chooserEscClosed"])
        self.assertTrue(R["chooserEscFocus"])

    def test_17_vertical_navigation(self):
        R = self.R
        self.assertEqual(R["vOrder"], R["hOrder"])
        self.assertEqual(R["vEntry"], "Applications")
        self.assertEqual(R["vRightIgnored"], "Applications")
        self.assertEqual(R["vDown1"], "Dolphin, pinned")
        self.assertEqual(R["vDown2"], "Konsole, running, pinned")
        self.assertEqual(R["vUp"], "Dolphin, pinned")
        self.assertEqual(R["vLeftIgnored"], "Dolphin, pinned")
        self.assertEqual(R["vEnd"], "Settings")
        self.assertEqual(R["vWrapDown"], "Applications")
        self.assertTrue(R["vReleased"])

    def test_18_mouse_interaction_and_no_focus_steal(self):
        R = self.R
        self.assertEqual(R["mouseLeftActivates"], WKON)
        self.assertTrue(R["mouseRightMenu"])
        self.assertTrue(R["mouseRightToggleClose"])
        self.assertTrue(R["mouseNoKeyboardFocusSteal"])
        self.assertTrue(R["noFocusWithoutRequest"])


if __name__ == "__main__":
    unittest.main()
