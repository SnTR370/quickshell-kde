#!/usr/bin/env python3
"""
P1 regression: AnchoredPopup must establish its active-window baseline from a
*fresh* query, not from the cached KWinService.activeWindowId.

Layer: OFFSCREEN runtime. The real components/AnchoredPopup.qml and the real
services/kwin/KWinService.qml run in `QT_QPA_PLATFORM=offscreen` with a private
XDG_RUNTIME_DIR / XDG_CONFIG_HOME and a private D-Bus session
(dbus-run-session). `kdotool` is replaced by a tiny script that returns the
contents of a state file, so focus changes are simulated deterministically.
No KWin compositor and no live Plasma session is involved.

Defect (pre-fix): onVisibleChanged captured `KWinService.activeWindowId`
(cached and potentially stale) as `initialActiveWindow`, then called
refreshActiveWindow(). If the fresh result differed from the stale cache, the
popup treated its own baseline sync as a focus change and closed immediately.

Expected after the fix:
  * a popup opened while the cache is stale stays open,
  * genuine focus changes after opening still dismiss it,
  * Escape, owner/compositor dismissal, desktop switches and repeated
    open/close cycles keep their current semantics.
"""

import os
import shutil
import subprocess
import tempfile
import unittest

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HARNESS = r"""import QtQuick
import QtTest
import Quickshell
import Quickshell.Io
import "./services"
import "./components"

FloatingWindow {
    id: win
    implicitWidth: 500
    implicitHeight: 400
    visible: true

    Rectangle { id: anchor; x: 10; y: 10; width: 100; height: 30; color: "red" }

    property int closedCount: 0

    AnchoredPopup {
        id: popup
        parentWindow: win
        anchorItem: anchor
        visible: false
        onClosed: win.closedCount++
    }

    Process {
        id: stateProc
        onExited: stateProc.done = true
        property bool done: false
    }

    TestCase {
        id: tc
        name: "AnchoredPopupBaseline"
        when: false
        property var res: ({})

        function setActive(v) {
            stateProc.command = ["sh", "-c", "printf '%s' '" + v + "' > \"$FAKE_KWIN_STATE/active\""];
            stateProc.running = true;
            wait(150);
        }

        function setBlock(on) {
            stateProc.command = ["sh", "-c", on
                ? "touch \"$FAKE_KWIN_STATE/block\""
                : "rm -f \"$FAKE_KWIN_STATE/block\""];
            stateProc.running = true;
            wait(120);
        }

        function waitFor(fn, ms) {
            const t0 = Date.now();
            while (!fn() && Date.now() - t0 < ms) wait(20);
            return fn();
        }

        function primeActive(v) {
            setActive(v);
            KWinService.refreshActiveWindow();
            return waitFor(() => KWinService.activeWindowId === v, 3000);
        }

        // Opens the popup and gives the fresh refresh + two poll cycles time to run.
        function openPopup() {
            popup.visible = true;
            wait(650);
            return popup.visible;
        }

        function runTests() {
            const R = {};
            tc.res = R;

            // ---- 0. Prime the cache with W1 ----------------------------------------
            R.primed = primeActive("W1");
            R.cachedBeforeOpen = KWinService.activeWindowId;

            // The compositor focus changes out-of-band; the cache is now stale.
            setActive("W2");

            // ---- 1. Stale baseline must not close the popup -------------------------
            R.openedWithStaleCache = openPopup();
            R.staleBaselineVisible = popup.visible;
            R.baselineAfterOpen = popup.initialActiveWindow;
            R.closedAfterStaleOpen = win.closedCount;
            R.activeAfterStaleOpen = KWinService.activeWindowId;

            if (popup.visible) popup.close();
            wait(80);

            // ---- 2. Genuine focus change after opening still dismisses --------------
            const c0 = win.closedCount;
            popup.visible = true;
            wait(650);
            R.reopenedFresh = popup.visible;
            R.baselineFresh = popup.initialActiveWindow;
            setActive("W3");
            R.focusChangeClosed = waitFor(() => !popup.visible, 2000);
            R.focusChangeClosedSignal = win.closedCount > c0;
            wait(80);

            // ---- 3. Reopen after focus changed while closed -------------------------
            setActive("W4");
            R.reopenAfterFocusChange = openPopup();
            R.reopenBaseline = popup.initialActiveWindow;
            const c1 = win.closedCount;
            popup.handleKeyEvent({ key: Qt.Key_Escape, accepted: false });
            wait(50);
            R.escapeClosed = !popup.visible;
            R.escapeSignal = win.closedCount > c1;
            R.escapeResetBaseline = (popup.initialActiveWindow === "");

            // ---- 4. Owner/compositor dismissal (outside click / popup_done) ---------
            // An xdg_popup is dismissed by the compositor by hiding the window;
            // AnchoredPopup's contract is to clean up and emit closed() that way.
            R.ownerOpen = openPopup();
            const c2 = win.closedCount;
            popup.visible = false;      // what popup_done / owner dismissal does
            wait(50);
            R.ownerDismissClosed = (win.closedCount > c2);
            R.ownerDismissResetBaseline = (popup.initialActiveWindow === "");
            R.ownerDismissedInvisible = !popup.visible;

            // ---- 5. Desktop change still dismisses ---------------------------------
            KWinService.currentDesktopId = "d1";
            setActive("W5");
            R.desktopOpen = openPopup();
            R.desktopBaseline = popup.initialActiveWindow;
            const c3 = win.closedCount;
            KWinService.desktopChanged(1, "d2");
            wait(50);
            R.desktopChangeClosed = !popup.visible;
            R.desktopChangeSignal = win.closedCount > c3;

            // ---- 6. "Show desktop" still dismisses ---------------------------------
            KWinService.currentDesktopId = "d1";
            setActive("W6");
            R.showDesktopOpen = openPopup();
            const c4 = win.closedCount;
            KWinService.showingDesktopChanged();
            wait(50);
            R.showDesktopClosed = !popup.visible;
            R.showDesktopSignal = win.closedCount > c4;

            // ---- 7. Repeated open/close cycles stay stable -------------------------
            const cycleVisible = [];
            for (let i = 0; i < 3; i++) {
                const id = "C" + i;
                setActive(id);
                popup.visible = true;
                wait(650);
                cycleVisible.push(popup.visible);
                popup.close();
                wait(80);
            }
            R.cyclesVisible = cycleVisible;
            R.cyclesBaselineReset = (popup.initialActiveWindow === "");

            // ---- 8. Open while an earlier active-window query is in flight ---------
            // The fake kdotool reads the active id and then blocks until the
            // block file is removed. A query started before the popup opens
            // therefore samples a pre-open focus and completes late; the
            // popup must not adopt that sample as its baseline.
            R.inflightPrimed = primeActive("F1");
            setBlock(true);
            KWinService.refreshActiveWindow();   // starts and blocks, sampled F1
            wait(300);
            R.inflightQueryGeneration = KWinService.activeWindowQueryGeneration;
            setActive("F2");                     // focus converges while blocked
            popup.visible = true;
            wait(500);                           // still blocked: popup must stay open
            R.inflightStayedOpenWhileBlocked = popup.visible;
            R.inflightAwaiting = popup._awaitingActiveWindowBaseline;
            setBlock(false);                     // stale sample (F1) now completes
            wait(900);                           // in-flight sample ignored, next poll adopts F2
            R.inflightVisibleAfterStaleSample = popup.visible;
            R.inflightBaseline = popup.initialActiveWindow;
            R.inflightGenerationAdvanced = (KWinService.activeWindowQueryGeneration > R.inflightQueryGeneration);
            setActive("F3");                     // genuine change after baseline
            R.inflightFocusClosed = waitFor(() => !popup.visible, 2000);
            wait(80);
            R.inflightBaselineReset = (popup.initialActiveWindow === "");

            console.log("POPUP_BASELINE_RESULT:" + JSON.stringify(R));
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
                console.log("POPUP_BASELINE_ERROR:" + e + " @ " + e.stack + " PARTIAL=" + JSON.stringify(tc.res));
            }
            Qt.quit();
        }
    }
}
"""

FAKE_KDOTOOL = """#!/bin/sh
if [ "$1" = "getactivewindow" ]; then
  # Sample first, then optionally block: this lets a test create an in-flight
  # query whose result predates a later focus change.
  val=$(cat "$FAKE_KWIN_STATE/active" 2>/dev/null)
  if [ -e "$FAKE_KWIN_STATE/block" ]; then
    while [ -e "$FAKE_KWIN_STATE/block" ]; do sleep 0.02; done
  fi
  printf '%s' "$val"
  exit 0
fi
exit 0
"""

FAKE_QDBUS = """#!/bin/sh
exit 1
"""


def run_harness(timeout=120):
    if shutil.which("quickshell") is None or shutil.which("dbus-run-session") is None:
        raise unittest.SkipTest("quickshell or dbus-run-session not available")
    tmp = tempfile.TemporaryDirectory(prefix="qs-popup-baseline-")
    root = tmp.name
    bindir = os.path.join(root, "bin")
    state = os.path.join(root, "state")
    runtime_dir = os.path.join(root, "runtime")
    config_home = os.path.join(root, "cfg")
    os.makedirs(bindir)
    os.makedirs(state)
    os.makedirs(runtime_dir, mode=0o700)
    os.makedirs(config_home, exist_ok=True)
    for name, body in (("kdotool", FAKE_KDOTOOL), ("qdbus6", FAKE_QDBUS)):
        p = os.path.join(bindir, name)
        with open(p, "w") as f:
            f.write(body)
        os.chmod(p, 0o755)
    with open(os.path.join(state, "active"), "w") as f:
        f.write("")

    # Never inherit the live graphical session or its session bus.
    env = os.environ.copy()
    env.pop("WAYLAND_DISPLAY", None)
    env.pop("DISPLAY", None)
    env.pop("DBUS_SESSION_BUS_ADDRESS", None)
    env.pop("JOURNAL_STREAM", None)
    env.pop("INVOCATION_ID", None)
    env.update({
        "XDG_CONFIG_HOME": config_home,
        "XDG_RUNTIME_DIR": runtime_dir,
        "XDG_CURRENT_DESKTOP": "KDE",
        "KDE_FULL_SESSION": "true",
        "QT_QPA_PLATFORM": "offscreen",
        "FAKE_KWIN_STATE": state,
        "PATH": bindir + os.pathsep + env.get("PATH", ""),
    })

    probe = os.path.join(REPO_DIR, "_test_popup_baseline_probe.qml")
    try:
        with open(probe, "w") as f:
            f.write(HARNESS)
        proc = subprocess.run(
            ["dbus-run-session", "--", "quickshell", "-p", probe, "--no-duplicate"],
            cwd=REPO_DIR, env=env, capture_output=True, text=True, timeout=timeout,
        )
    finally:
        if os.path.exists(probe):
            os.remove(probe)
        tmp.cleanup()

    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    marker = "POPUP_BASELINE_RESULT:"
    if "POPUP_BASELINE_ERROR:" in combined:
        raise AssertionError(combined[combined.index("POPUP_BASELINE_ERROR:"):][:2500])
    if marker not in combined:
        raise AssertionError("Missing result marker in output:\n" + combined[-4000:])
    import json
    line = [l for l in combined.splitlines() if marker in l][-1]
    return json.loads(line.split(marker, 1)[1])


class TestAnchoredPopupBaseline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.R = run_harness()

    def test_01_cache_primed(self):
        self.assertTrue(self.R["primed"], "fake kdotool priming failed")
        self.assertEqual(self.R["cachedBeforeOpen"], "W1")

    def test_02_stale_baseline_does_not_close_popup(self):
        # Core P1 regression.
        self.assertTrue(self.R["openedWithStaleCache"])
        self.assertTrue(
            self.R["staleBaselineVisible"],
            "popup closed because it used the stale cached active window as baseline",
        )
        self.assertEqual(self.R["baselineAfterOpen"], "W2")
        self.assertEqual(self.R["activeAfterStaleOpen"], "W2")

    def test_03_genuine_focus_change_dismisses(self):
        self.assertTrue(self.R["reopenedFresh"])
        self.assertEqual(self.R["baselineFresh"], "W2")
        self.assertTrue(self.R["focusChangeClosed"], "focus change must dismiss")
        self.assertTrue(self.R["focusChangeClosedSignal"])

    def test_04_reopen_after_focus_change_uses_new_baseline(self):
        self.assertTrue(self.R["reopenAfterFocusChange"])
        self.assertEqual(self.R["reopenBaseline"], "W4")

    def test_05_escape_dismisses(self):
        self.assertTrue(self.R["escapeClosed"])
        self.assertTrue(self.R["escapeSignal"])
        self.assertTrue(self.R["escapeResetBaseline"])

    def test_06_owner_or_compositor_dismissal(self):
        self.assertTrue(self.R["ownerOpen"])
        self.assertTrue(self.R["ownerDismissClosed"], "closed() must be emitted")
        self.assertTrue(self.R["ownerDismissResetBaseline"])
        self.assertTrue(self.R["ownerDismissedInvisible"])

    def test_07_desktop_change_dismisses(self):
        self.assertTrue(self.R["desktopOpen"])
        self.assertEqual(self.R["desktopBaseline"], "W5")
        self.assertTrue(self.R["desktopChangeClosed"])
        self.assertTrue(self.R["desktopChangeSignal"])

    def test_08_show_desktop_dismisses(self):
        self.assertTrue(self.R["showDesktopOpen"])
        self.assertTrue(self.R["showDesktopClosed"])
        self.assertTrue(self.R["showDesktopSignal"])

    def test_09_repeated_open_close_cycles(self):
        self.assertEqual(self.R["cyclesVisible"], [True, True, True])
        self.assertTrue(self.R["cyclesBaselineReset"])

    def test_10_open_during_inflight_query(self):
        self.assertTrue(self.R["inflightPrimed"])
        # The popup must stay open while the pre-open query is still blocked.
        self.assertTrue(self.R["inflightStayedOpenWhileBlocked"])
        self.assertTrue(self.R["inflightAwaiting"])
        # Its late, stale sample must be ignored rather than used as baseline.
        self.assertTrue(self.R["inflightVisibleAfterStaleSample"])
        self.assertTrue(self.R["inflightGenerationAdvanced"])
        self.assertEqual(self.R["inflightBaseline"], "F2")
        # Once a fresh baseline exists, genuine focus changes still dismiss.
        self.assertTrue(self.R["inflightFocusClosed"])
        self.assertTrue(self.R["inflightBaselineReset"])


if __name__ == "__main__":
    unittest.main()
