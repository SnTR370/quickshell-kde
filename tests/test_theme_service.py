#!/usr/bin/env python3
"""
P2 remediation: ThemeService theme id / path validation.

The persisted theme_config.json "activeTheme" value was substituted into a
file path and read with `cat` without validation. A user-writable config
could point the shell at arbitrary files outside themes/ (the content only
ever reached Theme.applyTheme as JSON, but the read itself must not be
attacker-steerable).

- Static contract: selectTheme/saveThemeSelection gate on isValidThemeId.
- Isolated headless probe: isValidThemeId accepts the shipped theme ids and
  rejects traversal, separators, absolute paths, empties and garbage.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from qs_test_env import (  # noqa: E402
    isolated_probe_env,
    isolated_probe_workspace,
    run_isolated_probe,
    write_probe,
)


PROBE_QML = """import QtQuick
import Quickshell
import "./services"

Scope {
    Timer {
        interval: 400; running: true; repeat: false
        onTriggered: {
            console.log("THEME-VALIDATION-RESULT:" + JSON.stringify({
                breeze: ThemeService.isValidThemeId("breeze-dark"),
                traversal: ThemeService.isValidThemeId("../../etc/passwd"),
                slash: ThemeService.isValidThemeId("a/b"),
                dotdot: ThemeService.isValidThemeId(".."),
                leadingDot: ThemeService.isValidThemeId(".hidden"),
                leadingDash: ThemeService.isValidThemeId("-arg"),
                number: ThemeService.isValidThemeId(42),
                nul: ThemeService.isValidThemeId(null),
                empty: ThemeService.isValidThemeId(""),
                space: ThemeService.isValidThemeId("   "),
                long: ThemeService.isValidThemeId("x".repeat(65)),
                ok64: ThemeService.isValidThemeId("x".repeat(64)),
                defaultApplied: Theme.activeThemeId === "breeze-dark" || Theme.activeThemeId === ""
            }));
            Qt.exit(0);
        }
    }
}
"""


class TestThemeServiceValidation(unittest.TestCase):
    def test_select_theme_gates_on_validation(self):
        with open(os.path.join(REPO, "services/theme/ThemeService.qml")) as f:
            src = f.read()
        self.assertIn("function isValidThemeId(themeId)", src)
        self.assertIn('if (!isValidThemeId(themeId)) {\n            Log.warn("ThemeService", "Rejected invalid theme id: " + themeId);', src)
        self.assertIn('if (!isValidThemeId(themeId)) {\n            Log.warn("ThemeService", "Refused to save invalid theme id: " + themeId);', src)

    def test_qml_lint(self):
        res = subprocess.run(
            ["qmllint", "services/theme/ThemeService.qml"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"qmllint failed: {res.stderr}")

    def test_probe_validation_results(self):
        if shutil.which("quickshell") is None or shutil.which("dbus-run-session") is None:
            self.skipTest("quickshell or dbus-run-session not available")
        with tempfile.TemporaryDirectory(prefix="qs-theme-") as tmpdir:
            # Probe lives in a throwaway symlink workspace inside tmpdir:
            # repo-relative imports resolve, nothing is written to the repo.
            workspace = isolated_probe_workspace(os.path.join(tmpdir, "ws"))
            probe = write_probe(workspace, PROBE_QML, "_theme_validation_probe.qml")
            env = isolated_probe_env(tmpdir)
            env.update({
                "XDG_CONFIG_HOME": tmpdir,
            })
            proc = run_isolated_probe(probe, env, timeout=60)
            combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
            lines = [ln for ln in combined.splitlines() if "THEME-VALIDATION-RESULT:" in ln]
            self.assertTrue(lines, f"missing marker in output:\n{combined}")
            data = json.loads(lines[-1].split("THEME-VALIDATION-RESULT:", 1)[1])
            for key in ("breeze",):
                self.assertTrue(data[key], f"{key} must be a valid theme id")
            for key in ("traversal", "slash", "dotdot", "leadingDot", "leadingDash",
                        "number", "nul", "empty", "space", "long"):
                self.assertFalse(data[key], f"{key} must be rejected")
            self.assertTrue(data["ok64"], "64-char id within charset must be accepted")


if __name__ == "__main__":
    unittest.main()
