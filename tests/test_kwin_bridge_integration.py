#!/usr/bin/env python3
"""
P0 #9 Intellihide — isolated KWin event bridge integration test.

Runs the real compiled bridge plugin (Loader + BridgeHost.qml, exactly as
WindowService loads it) against a resident KWin script inside a throwaway
D-Bus session with `kwin_wayland --virtual`. The harness QML mirrors
WindowService.handleBridgeBatch: every batchReceived is JSON-parsed and merged
through BridgeRecords.applyBatch, and the merged state is printed for
assertion. Covers:

  phase A: bridge start, script load, live window events (add/move/resize/
           minimize/unminimize/fullscreen/close) merged into windowStates,
           desktop switch forwarding, spoofed record rejection, clean
           script unload on exit
  phase B: harness SIGKILL leaves an orphan script loaded in KWin
  phase C: a fresh harness start cleans the orphan and unloads on exit

SAFE: private XDG_RUNTIME_DIR/XDG_CONFIG_HOME, own bus, own kwin; the live
Plasma session is never touched. Skipped when kwin_wayland, dbus-run-session,
qdbus6, kdotool, the qml binary or the built bridge plugin are missing.

Run with: python3 -m unittest tests.test_kwin_bridge_integration
"""
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRIDGE_DIR = os.path.join(REPO, "services/kwin", "bridge")
TEMPLATE = os.path.join(REPO, "services/kwin", "scripts", "kwin-event-bridge.js")
RECORDS_JS = os.path.join(REPO, "services/kwin", "BridgeRecords.js")
QML_BIN = "/usr/lib/qt6/bin/qml" if os.path.exists("/usr/lib/qt6/bin/qml") else shutil.which("qml")

OBJECT_PATH = "/org/quickshell/kwinbridge"

# Driven test window: created -> moved -> resized -> minimized -> restored ->
# fullscreened -> closed, one step per 1.5 s (same cadence as .rig/e2e.sh).
WIN_QML = """import QtQuick
import QtQuick.Window
Window {
    id: win
    width: 400; height: 300; visible: true; title: "e2e-window"
    property int step: 0
    Component.onCompleted: { win.x = 100; win.y = 100; console.log("WIN-CREATED") }
    Timer {
        interval: 1500; repeat: true; running: true
        onTriggered: {
            step++;
            switch (step) {
                case 1: win.x = 50; win.y = 500; console.log("WIN-MOVE"); break;
                case 2: win.width = 900; console.log("WIN-RESIZE"); break;
                case 3: win.showMinimized(); console.log("WIN-MINIMIZE"); break;
                case 4: win.showNormal(); win.requestActivate(); console.log("WIN-RESTORE"); break;
                case 5: win.visibility = Window.FullScreen; console.log("WIN-FULLSCREEN"); break;
                case 6: console.log("WIN-CLOSE"); Qt.exit(0); break;
            }
        }
    }
}
"""

# Mirrors WindowService: Loader for bridge/BridgeHost.qml, Connections for
# batchReceived/desynchronized, BridgeRecords.applyBatch merge. Prints the
# merged state after every batch so the python side can assert on it.
def harness_qml(runtime_ms):
    return """import QtQuick
import "file:%s" as BridgeRecords

Item {
    id: root
    property var windowStates: ({})
    property var windowOutputs: ({})
    property int windowStateRevision: 0
    property string desktopId: ""

    Loader {
        id: bridgeLoader
        active: true
        source: "file:%s/BridgeHost.qml"
        onLoaded: console.log("HARNESS-START-RESULT:" +
            item.enable("%s"))
    }
    Connections {
        target: bridgeLoader.item
        function onBatchReceived(jsonArray) { root.handleBridgeBatch(jsonArray) }
        function onDesynchronized(reason) {
            console.log("DESYNC:" + reason);
            root.windowStates = {};
            root.windowOutputs = {};
        }
    }
    readonly property bool bridgeActive: bridgeLoader.item !== null
        && bridgeLoader.item.active && bridgeLoader.item.connected
    onBridgeActiveChanged: console.log("BRIDGE-ACTIVE:" + root.bridgeActive)

    function handleBridgeBatch(jsonArray) {
        let payloads;
        try { payloads = JSON.parse(jsonArray) } catch (e) { console.log("BATCH-PARSE-FAIL"); return }
        if (!Array.isArray(payloads)) return
        const res = BridgeRecords.applyBatch(root.windowStates, root.windowOutputs, payloads)
        if (!res.ok) return
        root.windowStates = res.states
        root.windowOutputs = res.outputs
        if (res.changed) root.windowStateRevision += 1
        if (res.desktopId) root.desktopId = res.desktopId
        console.log("MERGED:" + JSON.stringify({
            desktopId: root.desktopId, states: root.windowStates}))
    }

    Timer { interval: %d; running: true; onTriggered: { console.log("HARNESS-EXIT"); Qt.exit(0) } }
}
""" % (RECORDS_JS, BRIDGE_DIR, TEMPLATE, runtime_ms)


def wait_for(predicate, timeout_s, what):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.2)
    raise AssertionError("timed out waiting for " + what)


def merged_states(log_text):
    """All MERGED lines of a harness log, parsed."""
    out = []
    for line in log_text.splitlines():
        if line.startswith("MERGED:") or "MERGED:" in line:
            raw = line.split("MERGED:", 1)[1].strip()
            try:
                out.append(json.loads(raw))
            except ValueError:
                pass
    return out


def run_inner(testroot):
    """Phases A/B/C inside the dbus-run-session. Raises on any failure."""
    logs = os.path.join(testroot, "logs")
    scripts = os.path.join(testroot, "scripts")
    runtime = os.path.join(testroot, "runtime")
    config = os.path.join(testroot, "config")
    for d in (logs, scripts, config):
        os.makedirs(d, exist_ok=True)
    os.makedirs(runtime, exist_ok=True)
    os.chmod(runtime, 0o700)

    template_canonical = os.path.realpath(TEMPLATE)
    plugin_hash = hashlib.sha256(template_canonical.encode()).hexdigest()[:8]
    plugin_name = "quickshell-kwineventbridge-" + plugin_hash
    bus_name = "org.quickshell.kwineventbridge." + plugin_hash

    with open(os.path.join(scripts, "e2ewin.qml"), "w") as f:
        f.write(WIN_QML)

    def run(cmd, **kw):
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30, **kw)

    def qdbus(*args):
        return run(["qdbus6"] + list(args))

    def script_loaded():
        r = qdbus("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.isScriptLoaded", plugin_name)
        return "true" in r.stdout.lower()

    def start_harness(logfile, runtime_ms):
        with open(os.path.join(scripts, "harness.qml"), "w") as f:
            f.write(harness_qml(runtime_ms))
        logf = open(logfile, "w")
        proc = subprocess.Popen(
            [QML_BIN, "-platform", "offscreen", os.path.join(scripts, "harness.qml")],
            stdout=logf, stderr=subprocess.STDOUT,
            env=dict(os.environ, QT_QPA_PLATFORM="offscreen"))
        return proc, logf

    kwin = subprocess.Popen(
        ["kwin_wayland", "--virtual", "--width", "1280", "--height", "800",
         "--no-lockscreen", "--no-global-shortcuts", "--no-kactivities",
         "--socket", "kwine2e"],
        stdout=open(os.path.join(logs, "kwin.log"), "w"),
        stderr=subprocess.STDOUT, env=os.environ)
    harness = None
    harness_logf = None
    try:
        socket = os.path.join(runtime, "kwine2e")
        wait_for(lambda: os.path.exists(socket), 15, "kwin wayland socket")
        os.environ["WAYLAND_DISPLAY"] = "kwine2e"
        wait_for(lambda: qdbus("org.kde.KWin", "/KWin", "org.kde.KWin.activeOutputName").returncode == 0,
                 30, "kwin D-Bus availability")
        print("E2E-STEP kwin-up")

        # --- phase A: lifecycle + events + merge ---
        harness, harness_logf = start_harness(os.path.join(logs, "harnessA.log"), 14000)
        wait_for(lambda: "HARNESS-START-RESULT:true" in open(os.path.join(logs, "harnessA.log")).read(),
                 20, "harness A start")
        wait_for(script_loaded, 15, "bridge script loaded in KWin")
        print("E2E-STEP harnessA-started scriptLoaded=true")

        win = subprocess.Popen(
            [QML_BIN, "-platform", "wayland", os.path.join(scripts, "e2ewin.qml")],
            stdout=open(os.path.join(logs, "e2ewin.log"), "w"),
            stderr=subprocess.STDOUT, env=os.environ)
        time.sleep(4.6)  # created, moved, resized, minimized
        # Reactivate the minimized window so its own showNormal() is honored.
        subprocess.run(
            ["bash", "-c", 'kdotool activate "$(kdotool search --name e2e-window | head -1)" || true'],
            capture_output=True, text=True, timeout=20)
        qdbus("org.kde.KWin", "/VirtualDesktopManager",
              "org.kde.KWin.VirtualDesktopManager.createDesktop", "1", "e2e-second")
        qdbus("org.kde.KWin", "/KWin", "org.kde.KWin.setCurrentDesktop", "2")
        desk2 = qdbus("org.kde.KWin", "/VirtualDesktopManager",
                      "org.kde.KWin.VirtualDesktopManager.current").stdout.strip()
        print("E2E-DESK2:" + desk2)
        time.sleep(3.2)  # restored, fullscreened, closed

        # Spoofed record from a non-KWin sender must be rejected.
        spoof = qdbus(bus_name, OBJECT_PATH, "record",
                      '{"v":1,"gen":1,"seq":1,"type":"desktop","desktop":"evil"}')
        print("E2E-SPOOF-REPLY:[" + (spoof.stdout + spoof.stderr).strip() + "]")
        assert "error:sender" in spoof.stdout + spoof.stderr, "spoofed record was not rejected"

        win.wait(timeout=30)
        harness.wait(timeout=30)
        harness_logf.close()
        logA = open(os.path.join(logs, "harnessA.log")).read()
        assert "DESYNC:" not in logA, "unexpected desynchronization in phase A:\n" + logA
        assert "BATCH-PARSE-FAIL" not in logA

        states_log = merged_states(logA)
        assert states_log, "no merged batches in phase A log"
        # The driven window is the only normal window on the virtual kwin.
        with_state = [m for m in states_log if m.get("states")]
        assert with_state, "window never appeared in merged state"
        uuids = set(with_state[0]["states"])
        assert len(uuids) == 1, "expected exactly the e2e window, got " + str(uuids)
        uuid = uuids.pop()
        assert re.fullmatch(r"[0-9a-f-]{36}", uuid), "uuid not normalized: " + uuid

        def ever(key, value):
            return any(m["states"].get(uuid, {}).get(key) == value for m in states_log)

        assert ever("minimized", True), "minimize event never merged"
        assert ever("minimized", False), "unminimize event never merged"
        assert ever("fullScreen", True), "fullscreen event never merged"
        assert ever("maximized", False), "window record missing from merged state"
        last = states_log[-1]
        assert uuid not in last.get("states", {}), "closed window still in merged state"
        # The desktop switch must be forwarded; KWin may legitimately switch
        # back afterwards (e.g. reactivating a window on the old desktop), so
        # only require the target desktop to appear in the merged stream.
        desks = [m.get("desktopId") for m in states_log if m.get("desktopId")]
        assert desks and desk2 in desks, \
            "desktop switch not forwarded, saw=" + str(desks) + " want " + desk2
        assert not script_loaded(), "bridge script still loaded after clean harness exit"
        print("E2E-STEP harnessA-exited scriptLoadedAfterA=false")

        # --- phase B: crash leaves an orphan ---
        harness, harness_logf = start_harness(os.path.join(logs, "harnessB.log"), 30000)
        wait_for(lambda: "HARNESS-START-RESULT:true" in open(os.path.join(logs, "harnessB.log")).read(),
                 20, "harness B start")
        time.sleep(1.0)
        harness.send_signal(signal.SIGKILL)
        harness.wait(timeout=10)
        harness_logf.close()
        assert script_loaded(), "orphan script not loaded after SIGKILL"
        print("E2E-STEP orphanAfterCrash=true")

        # --- phase C: restart cleans the orphan ---
        harness, harness_logf = start_harness(os.path.join(logs, "harnessC.log"), 5000)
        wait_for(lambda: "HARNESS-START-RESULT:true" in open(os.path.join(logs, "harnessC.log")).read(),
                 20, "harness C start")
        harness.wait(timeout=30)
        harness_logf.close()
        logC = open(os.path.join(logs, "harnessC.log")).read()
        assert merged_states(logC), "fresh harness received no snapshot"
        assert not script_loaded(), "script still loaded after harness C exit"
        print("E2E-STEP scriptLoadedAfterC=false")
    finally:
        for p in (harness, kwin):
            if p is not None and p.poll() is None:
                p.kill()
        if harness_logf is not None:
            harness_logf.close()
        try:
            subprocess.run(["pkill", "-P", str(kwin.pid)], timeout=10)
        except Exception:
            pass
        kwin.wait(timeout=15)


class TestKWinBridgeIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        missing = [t for t in ("kwin_wayland", "dbus-run-session", "qdbus6", "kdotool")
                   if shutil.which(t) is None]
        if QML_BIN is None:
            missing.append("qml")
        for f in ("libkwineventbridgeplugin.so", "libkwineventbridge.so", "qmldir"):
            if not os.path.exists(os.path.join(BRIDGE_DIR, f)):
                missing.append("services/kwin/bridge/" + f)
        if missing:
            raise unittest.SkipTest("missing required tools: " + ", ".join(missing))
        cls.testroot = tempfile.mkdtemp(prefix="qs-bridge-e2e-")

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "testroot"):
            shutil.rmtree(cls.testroot, ignore_errors=True)

    def test_bridge_lifecycle_and_event_merge(self):
        env = dict(
            os.environ,
            XDG_RUNTIME_DIR=os.path.join(self.testroot, "runtime"),
            XDG_CONFIG_HOME=os.path.join(self.testroot, "config"),
            XDG_CURRENT_DESKTOP="KDE",
            KDE_FULL_SESSION="true",
            QT_QPA_PLATFORM="wayland",
            QT_FORCE_STDERR_LOGGING="1",
        )
        env.pop("JOURNAL_STREAM", None)
        env.pop("INVOCATION_ID", None)
        os.makedirs(env["XDG_RUNTIME_DIR"], mode=0o700, exist_ok=True)

        proc = subprocess.run(
            ["dbus-run-session", "--", sys.executable, os.path.abspath(__file__),
             "--inner", self.testroot],
            env=env, capture_output=True, text=True, timeout=240)
        out = proc.stdout + proc.stderr
        self.assertIn("PY-E2E-PASS", out,
                      "isolated bridge E2E failed (rc=%d):\n%s" % (proc.returncode, out[-4000:]))
        self.assertNotIn("PY-E2E-FAIL", out)
        self.assertEqual(proc.returncode, 0)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--inner":
        try:
            run_inner(sys.argv[2])
        except Exception as e:  # noqa: BLE001 - report and fail the outer test
            print("PY-E2E-FAIL: %s" % e)
            sys.exit(1)
        print("PY-E2E-PASS")
        sys.exit(0)
    # Drop argv so `python3 tests/test_kwin_bridge_integration.py` runs unittest.
    sys.argv = [sys.argv[0]]
    unittest.main()
