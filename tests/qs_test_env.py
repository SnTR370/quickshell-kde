#!/usr/bin/env python3
"""Session-safe launch harness for quickshell runtime probes.

Every quickshell probe in this repository imports the full services tree,
which can talk to the compositor and to the session D-Bus. Launching such a
probe with an environment copied from the developer's shell therefore lets
the test attach to the user's LIVE Plasma/KWin session. That is forbidden:
tests must never touch live userspace (CLAUDE.md "SAFETY", RUSH_PROTOCOL.md
"Host safety").

This module is the single source of truth for the isolation contract:

  1. No compositor handle: WAYLAND_DISPLAY / WAYLAND_SOCKET / DISPLAY are
     removed; QT_QPA_PLATFORM is forced to `offscreen`.
  2. No live session bus: DBUS_SESSION_BUS_ADDRESS (and friends) are removed
     from the environment and every probe is executed under
     `dbus-run-session --`, which injects a private throwaway bus.
  3. No writes to the real user profile: XDG_CONFIG_HOME, XDG_CACHE_HOME,
     XDG_DATA_HOME, XDG_STATE_HOME, XDG_RUNTIME_DIR and HOME all point inside
     the caller-provided temporary directory (runtime dir is chmod 700 as
     required for D-Bus/XDG sockets).

Runtime probes must be started through `run_isolated_probe()` (or, for
non-quickshell helpers, `run_isolated_command()`); never call
`subprocess.run(["quickshell", ...])` directly from a test.

`tests/test_isolation_contract.py` enforces this contract and proves the
runtime effect; do not weaken it.
"""

import os
import subprocess

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Variables that identify (and grant access to) the user's live graphical
# session. They must never reach a probe process.
SESSION_BOUND_VARS = (
    "WAYLAND_DISPLAY",
    "WAYLAND_SOCKET",
    "DISPLAY",
    "DBUS_SESSION_BUS_ADDRESS",
    "DBUS_SYSTEM_BUS_ADDRESS",
    "DBUS_STARTER_ADDRESS",
    "KDE_FULL_SESSION",
    "KDE_SESSION_UID",
    "KDE_SESSION_VERSION",
    "JOURNAL_STREAM",
    "INVOCATION_ID",
    "SYSTEMD_EXEC_PID",
)


def isolated_probe_env(tmpdir, base_env=None):
    """Return an environment for probes that cannot reach the live session.

    `tmpdir` is a caller-owned temporary directory (e.g. from
    tempfile.TemporaryDirectory()) that receives all private XDG state.
    `base_env` defaults to os.environ; tests of this helper pass a synthetic
    environment containing live-session coordinates.
    """
    env = dict(os.environ if base_env is None else base_env)
    for var in SESSION_BOUND_VARS:
        env.pop(var, None)

    runtime_dir = os.path.join(tmpdir, "probe-runtime")
    config_dir = os.path.join(tmpdir, "config")
    os.makedirs(runtime_dir, mode=0o700, exist_ok=True)
    os.makedirs(config_dir, exist_ok=True)

    env["QT_QPA_PLATFORM"] = "offscreen"
    env["XDG_RUNTIME_DIR"] = runtime_dir
    env["XDG_CONFIG_HOME"] = config_dir
    env["XDG_CACHE_HOME"] = os.path.join(tmpdir, "cache")
    env["XDG_DATA_HOME"] = os.path.join(tmpdir, "data")
    env["XDG_STATE_HOME"] = os.path.join(tmpdir, "state")
    env["HOME"] = tmpdir
    return env


def run_isolated_probe(probe_path, env, timeout=20, cwd=None):
    """Run a quickshell probe on a private D-Bus session, offscreen.

    `dbus-run-session --` guarantees a throwaway session bus regardless of
    what the ambient environment contained, so services that speak D-Bus
    (org.kde.KWin, StatusNotifier, ...) can only ever see the private bus.
    """
    return subprocess.run(
        ["dbus-run-session", "--", "quickshell", "-p", probe_path, "--no-duplicate"],
        cwd=cwd or REPO_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def run_isolated_command(argv, env, timeout=20, cwd=None):
    """Run a helper command (e.g. a kwin action script) off the live bus."""
    return subprocess.run(
        ["dbus-run-session", "--"] + list(argv),
        cwd=cwd or REPO_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
