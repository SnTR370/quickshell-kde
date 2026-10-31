#!/usr/bin/env python3
"""
P0 #9 Intellihide — bridge plugin fallback regression test.

WindowService loads services/kwin/bridge/BridgeHost.qml through a Loader and
keeps the snapshot-based sync path when the compiled plugin cannot load. This
suite verifies the three Loader outcomes in an offscreen `qml` runtime with
throwaway copies of the bridge directory (the real checkout is never
modified):

  * plugin missing (sources-only checkout, `optional plugin` qmldir)
  * plugin binary present but not loadable (wrong ABI / not a Qt plugin)
  * plugin built and loadable -> Loader.Ready

SAFE: QT_QPA_PLATFORM=offscreen, no window, no D-Bus name is taken
(BridgeHost.qml only instantiates the element; `enable()` is never called),
the live Plasma session is never touched. Skipped when the Qt6 `qml` runtime
is missing.

Run with: python3 -m unittest tests.test_bridge_fallback
"""
import os
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRIDGE_DIR = os.path.join(REPO, "services/kwin", "bridge")
QML_BIN = "/usr/lib/qt6/bin/qml" if os.path.exists("/usr/lib/qt6/bin/qml") else shutil.which("qml")

# Mirrors WindowService's Loader (source: "bridge/BridgeHost.qml") and reports
# the resulting status; exits 0 on Ready, 3 on Error, like a shell that stays
# alive either way.
HARNESS = """import QtQuick
Item {
    width: 10; height: 10
    Loader {
        id: ld
        source: "file:%s/BridgeHost.qml"
        onStatusChanged: {
            console.log("BRIDGE-CHECK:" + (status === Loader.Ready ? "READY" : "ERROR"));
            Qt.exit(status === Loader.Ready ? 0 : 3);
        }
    }
    // Loader finished before the window was shown: evaluate once more.
    Component.onCompleted: {
        if (ld.status === Loader.Ready) Qt.exit(0);
        if (ld.status === Loader.Error) Qt.exit(3);
    }
}
"""


def run_loader_check(bridge_copy_dir):
    """Run the offscreen Loader harness against a bridge directory copy.

    Returns (returncode, combined_output)."""
    with tempfile.TemporaryDirectory(prefix="qs-bridge-fallback-") as tmp:
        harness = os.path.join(tmp, "check.qml")
        with open(harness, "w") as f:
            f.write(HARNESS % bridge_copy_dir)
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_FORCE_STDERR_LOGGING="1")
        proc = subprocess.run(
            [QML_BIN, "-platform", "offscreen", harness],
            capture_output=True, text=True, timeout=30, env=env)
        return proc.returncode, (proc.stdout or "") + "\n" + (proc.stderr or "")


def copy_bridge(tmp, with_binaries=None, garbage_plugin=False):
    """Copy the tracked bridge files into tmp; optionally add binaries."""
    dst = os.path.join(tmp, "bridge")
    os.makedirs(dst)
    for name in ("BridgeHost.qml", "qmldir", "kwineventbridge.qmltypes"):
        shutil.copy(os.path.join(BRIDGE_DIR, name), dst)
    if garbage_plugin:
        # A shared library that is not a Qt QML plugin: same failure class as
        # an ABI-incompatible or corrupt build of kwineventbridgeplugin.
        donor = os.path.join(os.path.dirname(QML_BIN), "..", "lib", "libQt6Network.so.6")
        if not os.path.exists(donor):
            donor = "/usr/lib/libQt6Network.so.6"
        shutil.copy(donor, os.path.join(dst, "libkwineventbridgeplugin.so"))
    elif with_binaries:
        for name in ("libkwineventbridgeplugin.so", "libkwineventbridge.so"):
            shutil.copy(os.path.join(BRIDGE_DIR, name), dst)
    return dst


class TestBridgePluginFallback(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if QML_BIN is None:
            raise unittest.SkipTest("missing required tool: qml (Qt6 qml runtime)")

    def test_01_missing_plugin_degrades_to_loader_error(self):
        """A sources-only checkout (no built .so) must fail the Loader, not crash."""
        with tempfile.TemporaryDirectory(prefix="qs-bridge-fallback-") as tmp:
            dst = copy_bridge(tmp)
            rc, out = run_loader_check(dst)
            self.assertEqual(rc, 3, "missing plugin must surface Loader.Error:\n" + out)
            self.assertIn("BRIDGE-CHECK:ERROR", out)
            self.assertIn("not found", out)  # qmldir `optional plugin` message

    def test_02_incompatible_plugin_degrades_to_loader_error(self):
        """An unloadable binary in plugin position must fail the Loader, not crash."""
        with tempfile.TemporaryDirectory(prefix="qs-bridge-fallback-") as tmp:
            dst = copy_bridge(tmp, garbage_plugin=True)
            rc, out = run_loader_check(dst)
            self.assertEqual(rc, 3, "incompatible plugin must surface Loader.Error:\n" + out)
            self.assertIn("BRIDGE-CHECK:ERROR", out)

    def test_03_built_plugin_loads_ready(self):
        """With the locally built binaries in place the Loader must succeed."""
        if not os.path.exists(os.path.join(BRIDGE_DIR, "libkwineventbridgeplugin.so")):
            self.skipTest("bridge plugin not built in this checkout (see services/kwin/bridge/README.md)")
        with tempfile.TemporaryDirectory(prefix="qs-bridge-fallback-") as tmp:
            dst = copy_bridge(tmp, with_binaries=True)
            rc, out = run_loader_check(dst)
            self.assertEqual(rc, 0, "built plugin must load:\n" + out)
            self.assertIn("BRIDGE-CHECK:READY", out)

    def test_04_windowservice_fallback_wiring(self):
        """Static contract: the shell keeps the snapshot path on bridge failure."""
        with open(os.path.join(REPO, "services/kwin/WindowService.qml")) as f:
            src = f.read()
        # Loader error is tolerated with a warning, never fatal.
        self.assertIn("if (status === Loader.Error)", src)
        # Snapshot sync stays gated on the bridge being inactive, so it
        # resumes exactly when the bridge is unavailable.
        self.assertIn("if (!root.isLiveKWinSession || root.bridgeActive) return;", src)
        self.assertIn("if (exitCode === 0 && !root.bridgeActive", src)
        # Bridge drop repopulates state through the snapshot path.
        self.assertIn("if (!root.bridgeActive && root.isLiveKWinSession)", src)

    def test_05_windowservice_bridge_polling_reduction(self):
        """Static contract (P1-2): no 1 Hz window-list scan while the bridge is healthy.

        The active-window poll keeps its 1 s cadence (no bridge event source
        for focus changes); the window-list scan must not run from the 1 s
        timer while bridgeActive, must keep a slow safety net, and bridge
        membership changes must trigger the debounced refresh.
        """
        with open(os.path.join(REPO, "services/kwin/WindowService.qml")) as f:
            src = f.read()
        # 1 s timer: active window always, window scan only without the bridge.
        self.assertIn("if (!root.bridgeActive) {\n                root.refreshWindows();", src)
        # Slow safety net gated on the bridge being active.
        self.assertIn("id: bridgeScannerTimer", src)
        self.assertIn("running: root.bridgeActive && KWinService.isKWin && root.outputsOverride === null", src)
        # Debounced event-driven refresh for bridge membership changes.
        self.assertIn("id: bridgeMembershipTimer", src)
        self.assertIn("repeat: false", src)
        self.assertIn("const membership = BridgeRecords.membershipChanged(root.windowStates, payloads);", src)
        self.assertIn("bridgeMembershipTimer.restart();", src)


if __name__ == "__main__":
    unittest.main()
