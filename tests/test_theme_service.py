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
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
            probe = os.path.join(REPO, "_test_theme_validation_probe.qml")
            with open(probe, "w") as f:
                f.write(PROBE_QML)
            try:
                runtime_dir = os.path.join(tmpdir, "runtime")
                os.makedirs(runtime_dir, mode=0o700, exist_ok=True)
                env = dict(os.environ)
                env.pop("WAYLAND_DISPLAY", None)
                env.pop("DISPLAY", None)
                env.update({
                    "QT_QPA_PLATFORM": "offscreen",
                    "XDG_RUNTIME_DIR": runtime_dir,
                    "XDG_CONFIG_HOME": tmpdir,
                })
                proc = subprocess.run(
                    ["dbus-run-session", "--", "quickshell", "-p", probe, "--no-duplicate"],
                    cwd=REPO, env=env, capture_output=True, text=True, timeout=60)
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
            finally:
                if os.path.exists(probe):
                    os.remove(probe)


if __name__ == "__main__":
    unittest.main()
