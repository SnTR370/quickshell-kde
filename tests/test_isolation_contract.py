#!/usr/bin/env python3
"""Isolation contract regression tests (Colosseum test isolation waves 1–2).

These tests guard the guarantee that quickshell runtime probes can never
attach to the developer's live Plasma/KWin session:

  C1  isolated_probe_env() strips every session-bound variable, agent socket
      and credential-shaped variable from ANY base environment (synthetic
      *and* the real host environment) and confines all state to the caller's
      temporary directory.
  C2  Static contract: no test source may spawn quickshell (or embed a
      `quickshell -p` launch in a driver script) unless the same scope wires
      the launch through `dbus-run-session` and passes an explicit `env=`.
      Wave 2 upgraded this from a single literal-regex tripwire to an
      AST-based scanner that also catches `Popen`, variable-built argv,
      f-string/concatenated argv and env-less launches.
  C3  Runtime proof: a probe started through the harness observes NO
      compositor handle (WAYLAND_DISPLAY/DISPLAY unset) and a throwaway
      session bus that differs from the live one, while still running to
      completion (marker emitted, exit 0) — isolation without vacuous tests.
  C4  Workspace contract: `isolated_probe_workspace()` resolves repo-relative
      QML imports through symlinks only (never copies), is idempotent, and
      never touches repository content; `write_probe()` stays inside the
      workspace.

Honesty note: C2 is a *tripwire*, not a proof. Static analysis of Python
test sources cannot prove that no launched process ever reaches the live
session (a subprocess could reconstruct coordinates from elsewhere, and the
scanner is deliberately name-based). What it does guarantee is that the
known-unsafe patterns of the past — including the ones reintroduced as
synthetic fixtures below — fail the suite loudly. The runtime proof (C3)
complements it behaviorally; together they pin the contract, neither alone
proves it.

Reproduction of the original flaw (source inspection): before wave 1,
tests/test_dock_blitz.py, test_dock_keyboard.py and test_dock_file_drop.py
launched probes with `env = os.environ.copy()` + a bare quickshell argv,
inheriting WAYLAND_DISPLAY and DBUS_SESSION_BUS_ADDRESS from the live
desktop shell. C2 is the regression tripwire for that pattern; C1/C3 pin the
repaired contract.
"""

import ast
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
    AGENT_BOUND_VARS,
    SESSION_BOUND_VARS,
    isolated_probe_env,
    isolated_probe_workspace,
    run_isolated_probe,
    write_probe,
)

# --- C2 scanner ----------------------------------------------------------------

# quickshell referenced AS A COMMAND (argv element, script text), not merely
# mentioned inside identifiers like "org.quickshell.kwinbridge" or
# "quickshell-kwineventbridge-<hash>".
UNSAFE_QUICKSHELL_CMD = re.compile(r'(?<![\w./-])quickshell(?=$|\s|["\'])')

# Process-spawning entry points that inherit or receive an environment.
SPAWN_FUNCS = {
    "subprocess.run", "subprocess.Popen", "subprocess.call",
    "subprocess.check_call", "subprocess.check_output",
    "os.system", "os.popen", "os.execv", "os.execve", "os.spawnl", "os.spawnv",
}


def _dotted_name(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def _docstring_constants(tree):
    """String constants that are (module/class/function) docstrings."""
    docstrings = set()
    for n in ast.walk(tree):
        body = None
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = n.body
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            docstrings.add(id(body[0].value))
    return docstrings


def _string_constants_in(node, docstrings):
    """All non-docstring string constants within an AST subtree."""
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings:
            out.append(n.value)
    return out


def _is_spawn_call(node):
    return isinstance(node, ast.Call) and _dotted_name(node.func) in SPAWN_FUNCS


def _has_env_kwarg(call):
    return any(kw.arg == "env" for kw in call.keywords)


def scan_source_for_isolation_violations(source, relpath="<source>"):
    """Static isolation tripwire over one Python test source.

    Returns a list of human-readable violation strings (empty = pass).
    Rules (all triggered only by a quickshell COMMAND reference):

      R1  raw argv: a subprocess launch whose inlined argv contains
          "quickshell" without a "dbus-run-session" wrapper constant.
      R2  driver scripts: `os.system`/`os.popen`/`exec*`/`spawn*` carrying a
          quickshell command (no env control is possible at all).
      R3  unsafe environment inheritance: any launch that embeds a
          quickshell command but passes no explicit `env=`.
      R4  indirect launches (variable-built argv / concatenated bash rigs):
          if a function (or module top level) mentions a quickshell command
          anywhere, that scope must also wire `dbus-run-session` into the
          launch path, and EVERY launch call in that scope must pass an
          explicit `env=` (an env-less `subprocess.run(cmd)` with a
          variable-built `cmd` inherits the developer's full environment).

    Deliberate limitations (tripwire, not proof): names only — dynamic
    argv assembly from non-literal parts, or a scope that satisfies R4 with
    an unrelated "dbus-run-session" string, are out of reach of static
    analysis; C3 covers the behavior side.
    """
    violations = []
    tree = ast.parse(source, filename=relpath)
    docstrings = _docstring_constants(tree)

    def unsafe_consts(nodes):
        consts = []
        for n in nodes:
            consts.extend(_string_constants_in(n, docstrings))
        return [c for c in consts if UNSAFE_QUICKSHELL_CMD.search(c)]

    # R1/R2/R3 at call level.
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _dotted_name(node.func) in SPAWN_FUNCS):
            continue
        fname = _dotted_name(node.func)
        call_consts = _string_constants_in(node, docstrings)
        unsafe = [c for c in call_consts if UNSAFE_QUICKSHELL_CMD.search(c)]
        if not unsafe:
            continue
        if fname in ("os.system", "os.popen", "os.execv", "os.execve",
                     "os.spawnl", "os.spawnv"):
            violations.append(
                f"{relpath}: line {node.lineno}: {fname}() launches quickshell "
                "outside the harness (no env control, no private bus wrapper "
                "guarantee)")
            continue
        wrapped = any("dbus-run-session" in c for c in call_consts)
        if not wrapped:
            violations.append(
                f"{relpath}: line {node.lineno}: {fname}() launches quickshell "
                "without the dbus-run-session private-bus wrapper; use "
                "qs_test_env.run_isolated_probe()/run_isolated_command()")
        if not _has_env_kwarg(node):
            violations.append(
                f"{relpath}: line {node.lineno}: {fname}() launching quickshell "
                "has no explicit env= — the probe would inherit the developer's "
                "full environment")

    # R4 at scope level (catches `cmd = ["quickshell", ...]; run(cmd)` and
    # bash-rig strings assigned separately from the launch call).
    scopes = [tree] + [n for n in ast.walk(tree)
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    for scope in scopes:
        body_stmts = [s for s in getattr(scope, "body", [])
                      if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)
                              and isinstance(s.value.value, str))]
        unsafe = unsafe_consts(body_stmts)
        if not unsafe:
            continue
        scope_consts = []
        for s in body_stmts:
            scope_consts.extend(_string_constants_in(s, docstrings))
        if not any("dbus-run-session" in c for c in scope_consts):
            name = getattr(scope, "name", None)
            where = f"{relpath}: function '{name}'" if name else f"{relpath}: module top level"
            violations.append(
                f"{where}: launches quickshell with no 'dbus-run-session' in "
                "scope — every quickshell execution path must be wrapped in a "
                "private D-Bus session")
        # Function scope: every launch call there must pass env= (a
        # variable-built argv with no env= inherits the developer's full
        # environment; env-less qmllint-only functions are untouched).
        if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for node in ast.walk(scope):
                if _is_spawn_call(node) and not _has_env_kwarg(node):
                    violations.append(
                        f"{relpath}: line {node.lineno}: launch inside a function "
                        f"that runs quickshell ('{scope.name}') has no explicit env=")
    return violations


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
            "XAUTHORITY": "/home/user/.Xauthority",
            "DBUS_SESSION_BUS_ADDRESS": live_dbus,
            "KDE_FULL_SESSION": "true",
            "KDE_SESSION_UID": "9999",
            "JOURNAL_STREAM": "8:12345",
            "SSH_AUTH_SOCK": "/run/user/9999/gnupg/S.gpg-agent.ssh",
            "GPG_AGENT_INFO": "/run/user/9999/gnupg/S.gpg-agent:0:1",
            "GNOME_KEYRING_CONTROL": "/run/user/9999/keyring-XXXX",
            "STARTUP_ID": "1234-5678-time_x",
            "MYAPP_API_KEY": "super-secret",
            "GITHUB_TOKEN": "ghp_xxx",
            "AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI",
            "DB_PASSWORD": "hunter2",
            "XDG_RUNTIME_DIR": "/run/user/9999",
            "XDG_CONFIG_HOME": "/home/user/.config",
            "HOME": "/home/user",
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            env = isolated_probe_env(tmpdir, base_env=base)
            for var in SESSION_BOUND_VARS + AGENT_BOUND_VARS:
                self.assertNotIn(var, env, f"{var} leaks live session access into probes")
            for var in ("MYAPP_API_KEY", "GITHUB_TOKEN", "AWS_SECRET_ACCESS_KEY",
                        "DB_PASSWORD"):
                self.assertNotIn(var, env, f"credential variable {var} leaks into probes")
            # Legitimate dependencies survive the sweep.
            self.assertIn("PATH", env)
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
            self.assertNotIn("XAUTHORITY", env)
            self.assertNotIn("SSH_AUTH_SOCK", env)
            self.assertEqual(env["QT_QPA_PLATFORM"], "offscreen")
            self.assertEqual(env["HOME"], tmpdir,
                             "probe HOME must not be the developer's real profile")

    def test_c2_no_raw_quickshell_argv_in_test_sources(self):
        """C2: the AST scanner finds no un-wrapped quickshell launch in any test source.

        Raw argv inherits whatever environment the caller assembles; the
        only sanctioned entry points are run_isolated_probe()/
        run_isolated_command(), which pin the process to a private D-Bus
        session. This check reproduced the pre-fix state of test_dock_blitz /
        test_dock_keyboard / test_dock_file_drop as a failure when run
        against the old code.
        """
        offenders = []
        for path in collect_test_source_files():
            with open(path, encoding="utf-8") as f:
                source = f.read()
            offenders.extend(scan_source_for_isolation_violations(
                source, os.path.relpath(path, REPO_DIR)))
        self.assertEqual(
            offenders, [],
            "Test files must launch probes via qs_test_env.run_isolated_probe()/"
            f"run_isolated_command():\n" + "\n".join(offenders),
        )

    def test_c2_probe_launchers_are_dbus_wrapped(self):
        """C2: the sanctioned launcher itself guarantees a private session bus."""
        with open(os.path.join(TESTS_DIR, "qs_test_env.py"), encoding="utf-8") as f:
            source = f.read()
        self.assertIn('"dbus-run-session", "--", "quickshell"', source,
                      "run_isolated_probe must wrap quickshell in dbus-run-session")

    # --- deliberate reintroduction fixtures (wave 2) --------------------------
    #
    # Each SNIPPET_* source below re-implements a historically observed
    # unsafe pattern. The scanner MUST flag it, while the sanctioned pattern
    # must pass. If you weaken the scanner, these tests fail first.

    SNIPPET_RAW_ARGV = '''\
import os, subprocess
def run_probe(probe):
    env = os.environ.copy()
    env.pop("WAYLAND_DISPLAY", None)
    return subprocess.run(["quickshell", "-p", probe, "--no-duplicate"], env=env)
'''

    SNIPPET_POPEN = '''\
import subprocess
def start(probe, env):
    return subprocess.Popen(["quickshell", "-p", probe], stdout=subprocess.PIPE)
'''

    SNIPPET_VARIABLE_ARGV = '''\
import subprocess
def launch(probe):
    cmd = ["quickshell", "-p", probe, "--no-duplicate"]
    return subprocess.run(cmd, env={"PATH": "/usr/bin"}, capture_output=True)
'''

    SNIPPET_ENVLESS_LAUNCH = '''\
import subprocess
def launch(probe):
    cmd = ["dbus-run-session", "--", "quickshell", "-p", probe]
    return subprocess.run(cmd, capture_output=True)
'''

    SNIPPET_DRIVER_SCRIPT = '''\
import os
def drive(probe):
    return os.system("quickshell -p %s --no-duplicate" % probe)
'''

    SNIPPET_BASH_RIG_UNWRAPPED = '''\
import subprocess
def rig(tmpdir):
    script = "kwin_wayland --virtual & quickshell -p /repo/shell.qml\\n"
    return subprocess.run(["bash", "-c", script], env={}, capture_output=True)
'''

    SNIPPET_SANCTIONED = '''\
from qs_test_env import isolated_probe_env, run_isolated_probe
def launch(probe, tmpdir):
    env = isolated_probe_env(tmpdir)
    return run_isolated_probe(probe, env, timeout=30)
'''

    def test_c2_scanner_flags_known_unsafe_patterns(self):
        cases = [
            ("SNIPPET_RAW_ARGV", self.SNIPPET_RAW_ARGV, ["dbus-run-session"]),
            ("SNIPPET_POPEN", self.SNIPPET_POPEN, ["Popen"]),
            ("SNIPPET_VARIABLE_ARGV", self.SNIPPET_VARIABLE_ARGV, ["dbus-run-session"]),
            ("SNIPPET_ENVLESS_LAUNCH", self.SNIPPET_ENVLESS_LAUNCH, ["env="]),
            ("SNIPPET_DRIVER_SCRIPT", self.SNIPPET_DRIVER_SCRIPT, ["os.system"]),
            ("SNIPPET_BASH_RIG_UNWRAPPED", self.SNIPPET_BASH_RIG_UNWRAPPED,
             ["dbus-run-session"]),
        ]
        for name, src, expect_substrings in cases:
            with self.subTest(pattern=name):
                violations = scan_source_for_isolation_violations(src, name)
                self.assertTrue(violations, f"{name} must be flagged but scanner stayed clean")
                joined = "\n".join(violations)
                for want in expect_substrings:
                    self.assertIn(want, joined,
                                  f"{name}: violation should mention {want!r}: {joined}")

    def test_c2_scanner_passes_sanctioned_and_surgical_sources(self):
        # 1. synthetic sanctioned source
        self.assertEqual(
            scan_source_for_isolation_violations(self.SNIPPET_SANCTIONED, "sanctioned"),
            [], "sanctioned harness usage must not be flagged")
        # 2. the harness itself: legitimately contains the wrapped argv
        with open(os.path.join(TESTS_DIR, "qs_test_env.py"), encoding="utf-8") as f:
            self.assertEqual(
                scan_source_for_isolation_violations(f.read(), "qs_test_env.py"), [],
                "the harness wraps quickshell in dbus-run-session; it must pass")
        # 3. namespaced mentions only (D-Bus paths / plugin names) must not trip
        benign = '''\
import subprocess
OBJECT_PATH = "/org/quickshell/kwinbridge"
def qdbus():
    return subprocess.run(["qdbus6", "org.quickshell.kwineventbridge.abc"])
'''
        self.assertEqual(scan_source_for_isolation_violations(benign, "benign"), [],
                         "namespaced 'quickshell' strings must not be flagged as launches")

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
                configHome: Quickshell.env("XDG_CONFIG_HOME") ?? "",
                home: Quickshell.env("HOME") ?? "",
                sshAgent: Quickshell.env("SSH_AUTH_SOCK") ?? ""
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
            self.assertEqual(data["home"], tmpdir,
                             "probe sees the developer's real HOME")
            self.assertEqual(data["sshAgent"], "", "probe sees the SSH agent socket")
            self.assertTrue(data["configHome"].startswith(tmpdir),
                            "probe XDG_CONFIG_HOME escaped the temporary directory")
            # A private bus must exist (dbus-run-session) and it must not be
            # the live session bus the developer's shell is using.
            self.assertTrue(data["dbus"].startswith("unix:path="),
                            f"probe has no session bus at all: {data['dbus']!r}")
            if live_dbus:
                self.assertNotEqual(data["dbus"], live_dbus,
                                    "probe is attached to the LIVE session bus")

    def test_c4_workspace_resolves_imports_via_symlinks_only(self):
        """C4: the probe workspace links (never copies) and stays idempotent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = isolated_probe_workspace(os.path.join(tmpdir, "ws"))
            # Idempotent re-call must not raise or duplicate.
            isolated_probe_workspace(workspace)
            for name in ("services", "config", "components", "modules"):
                link = os.path.join(workspace, name)
                self.assertTrue(os.path.islink(link), f"{name} must be a symlink")
                self.assertEqual(os.path.realpath(link), os.path.realpath(os.path.join(REPO_DIR, name)),
                                 f"{name} must resolve to the repository copy, not a snapshot")
            # write_probe lands inside the workspace only.
            probe = write_probe(workspace, "// probe\n", "_x.qml")
            self.assertTrue(probe.startswith(workspace + os.sep))
            self.assertTrue(os.path.isfile(probe))
            # Repository content untouched: no probe litter, no stray links.
            for name in ("services", "config", "components", "modules"):
                repo_root = os.path.join(REPO_DIR, name)
                self.assertNotExistsInRepo(repo_root, "_x.qml")

    def assertNotExistsInRepo(self, root, filename):
        for dirpath, _dirs, files in os.walk(root):
            self.assertNotIn(filename, files,
                             f"{os.path.join(dirpath, filename)} must not exist")

    def test_c4_repo_root_has_no_probe_litter(self):
        """C4: the repository root contains no generated `_test_*.qml` files."""
        litter = [n for n in os.listdir(REPO_DIR) if n.startswith("_test_") and n.endswith(".qml")]
        self.assertEqual(
            litter, [],
            f"generated probes leaked into the repository root: {litter} — "
            "move probe creation into qs_test_env workspaces")


if __name__ == "__main__":
    unittest.main()
