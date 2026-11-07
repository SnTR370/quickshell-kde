#!/usr/bin/env python3
"""Isolation contract regression tests (Colosseum test isolation wave 1).

These tests guard the guarantee that quickshell runtime probes can never
attach to the developer's live Plasma/KWin session:

  C1  isolated_probe_env() strips every session-bound variable from ANY base
      environment (synthetic *and* the real host environment) and confines
      all state to the caller's temporary directory.
  C2  Static contract: no test file may build a raw `["quickshell", ...]`
      argv — probes launch only through qs_test_env.run_isolated_probe()
      (which wraps `dbus-run-session --`).
  C3  Runtime proof: a probe started through the harness observes NO
      compositor handle (WAYLAND_DISPLAY/DISPLAY unset) and a throwaway
      session bus that differs from the live one, while still running to
      completion (marker emitted, exit 0) — isolation without vacuous tests.

Reproduction of the original flaw (source inspection): before this wave,
tests/test_dock_blitz.py, test_dock_keyboard.py and test_dock_file_drop.py
launched probes with `env = os.environ.copy()` + a bare quickshell argv
(`quickshell -p <probe>`), inheriting WAYLAND_DISPLAY and
DBUS_SESSION_BUS_ADDRESS straight from the live desktop shell. C2 is the
regression tripwire for that pattern; C1/C3 pin the repaired contract.
"""

import json
import os
import re
import shutil
import stat
import sys
import tempfile
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, TESTS_DIR)

from qs_test_env import (  # noqa: E402
    SESSION_BOUND_VARS,
    isolated_probe_env,
    run_isolated_probe,
)


def collect_test_source_files():
    """All python test sources that may launch quickshell probes."""
    candidates = [os.path.join(TESTS_DIR, n) for n in sorted(os.listdir(TESTS_DIR)) if n.endswith(".py")]
    cc = os.path.join(REPO_DIR, "modules", "controlcenter")
    if os.path.isdir(cc):
        candidates += [os.path.join(cc, n) for n in sorted(os.listdir(cc)) if n.startswith("test_") and n.endswith(".py")]
    return candidates


class TestIsolationContract(unittest.TestCase):

    def test_c1_strips_synthetic_live_session(self):
        """C1: a synthetic live-session environment is fully neutralized."""
        live_dbus = "unix:path=/run/user/9999/bus"
        base = {
            "WAYLAND_DISPLAY": "wayland-1",
            "WAYLAND_SOCKET": "/tmp/wayland-sock",
            "DISPLAY": ":1",
            "DBUS_SESSION_BUS_ADDRESS": live_dbus,
            "KDE_FULL_SESSION": "true",
            "KDE_SESSION_UID": "9999",
            "JOURNAL_STREAM": "8:12345",
            "XDG_RUNTIME_DIR": "/run/user/9999",
            "XDG_CONFIG_HOME": "/home/user/.config",
            "HOME": "/home/user",
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            env = isolated_probe_env(tmpdir, base_env=base)
            for var in SESSION_BOUND_VARS:
                self.assertNotIn(var, env, f"{var} leaks live session access into probes")
            self.assertEqual(env["QT_QPA_PLATFORM"], "offscreen")
            root = os.path.realpath(tmpdir)
            for key in ("XDG_RUNTIME_DIR", "XDG_CONFIG_HOME", "XDG_CACHE_HOME",
                        "XDG_DATA_HOME", "XDG_STATE_HOME", "HOME"):
                real = os.path.realpath(env[key])
                self.assertTrue(
                    real == root or real.startswith(root + os.sep),
                    f"{key}={env[key]} escapes the isolated temporary directory",
                )
            mode = stat.S_IMODE(os.stat(env["XDG_RUNTIME_DIR"]).st_mode)
            self.assertEqual(mode, 0o700, "XDG_RUNTIME_DIR must be private (0700)")

    def test_c1_strips_the_real_host_session(self):
        """C1: isolating from the REAL developer environment removes all live handles."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = isolated_probe_env(tmpdir)
            self.assertNotIn("WAYLAND_DISPLAY", env)
            self.assertNotIn("DISPLAY", env)
            self.assertNotIn("DBUS_SESSION_BUS_ADDRESS", env)
            self.assertEqual(env["QT_QPA_PLATFORM"], "offscreen")

    def test_c2_no_raw_quickshell_argv_in_test_sources(self):
        """C2: no test source may spawn `["quickshell", ...]` directly.

        Raw argv inherits whatever environment the caller assembles; the
        only sanctioned entry point is run_isolated_probe(), which pins the
        process to a private D-Bus session. This check reproduced the
        pre-fix state of test_dock_blitz / test_dock_keyboard /
        test_dock_file_drop as a failure when run against the old code.
        """
        raw_launch = re.compile(r'\[\s*"quickshell"\s*,\s*"-p"')
        offenders = []
        for path in collect_test_source_files():
            with open(path, encoding="utf-8") as f:
                source = f.read()
            if raw_launch.search(source):
                offenders.append(os.path.relpath(path, REPO_DIR))
        self.assertEqual(
            offenders, [],
            "Test files must launch probes via qs_test_env.run_isolated_probe(), "
            f"never a raw quickshell argv: {offenders}",
        )

    def test_c2_probe_launchers_are_dbus_wrapped(self):
        """C2: the sanctioned launcher itself guarantees a private session bus."""
        with open(os.path.join(TESTS_DIR, "qs_test_env.py"), encoding="utf-8") as f:
            source = f.read()
        self.assertIn('"dbus-run-session", "--", "quickshell"', source,
                      "run_isolated_probe must wrap quickshell in dbus-run-session")

    def test_c3_runtime_proof_probe_has_no_live_session(self):
        """C3: an isolated quickshell probe observes no compositor and no live bus.

        The probe still runs to completion (marker + clean exit), so this is
        a behavioral proof of isolation, not a skipped/vacuous one.
        """
        if shutil.which("quickshell") is None or shutil.which("dbus-run-session") is None:
            self.skipTest("quickshell or dbus-run-session not available")
        live_dbus = os.environ.get("DBUS_SESSION_BUS_ADDRESS", "")
        probe_qml = """import QtQuick
import Quickshell

Scope {
    Timer {
        interval: 150
        running: true
        onTriggered: {
            console.log("ISOLATION_CONTRACT:" + JSON.stringify({
                wayland: Quickshell.env("WAYLAND_DISPLAY") ?? "",
                display: Quickshell.env("DISPLAY") ?? "",
                dbus: Quickshell.env("DBUS_SESSION_BUS_ADDRESS") ?? "",
                qpa: Quickshell.env("QT_QPA_PLATFORM") ?? "",
                configHome: Quickshell.env("XDG_CONFIG_HOME") ?? ""
            }));
            Qt.quit();
        }
    }
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = isolated_probe_env(tmpdir)
            # Probe lives inside the isolated dir: nothing is generated in the repo.
            probe_path = os.path.join(tmpdir, "_isolation_contract_probe.qml")
            with open(probe_path, "w") as f:
                f.write(probe_qml)
            proc = run_isolated_probe(probe_path, env, timeout=20, cwd=tmpdir)
            combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
            marker = "ISOLATION_CONTRACT:"
            self.assertIn(marker, combined,
                          f"Isolated probe failed to run (exit {proc.returncode}):\n{combined}")
            self.assertEqual(proc.returncode, 0, f"Isolated probe exited uncleanly:\n{combined}")
            line = [l for l in combined.splitlines() if marker in l][-1]
            data = json.loads(line.split(marker, 1)[1].strip())

            self.assertEqual(data["wayland"], "", "probe sees a Wayland compositor")
            self.assertEqual(data["display"], "", "probe sees an X11 display")
            self.assertEqual(data["qpa"], "offscreen")
            self.assertTrue(data["configHome"].startswith(tmpdir),
                            "probe XDG_CONFIG_HOME escaped the temporary directory")
            # A private bus must exist (dbus-run-session) and it must not be
            # the live session bus the developer's shell is using.
            self.assertTrue(data["dbus"].startswith("unix:path="),
                            f"probe has no session bus at all: {data['dbus']!r}")
            if live_dbus:
                self.assertNotEqual(data["dbus"], live_dbus,
                                    "probe is attached to the LIVE session bus")


if __name__ == "__main__":
    unittest.main()
