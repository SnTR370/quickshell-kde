#!/usr/bin/env python3
"""Session-safe launch harness for quickshell runtime probes.

Every quickshell probe in this repository imports the full services tree,
which can talk to the compositor and to the session D-Bus. Launching such a
probe with an environment copied from the developer's shell therefore lets
the test attach to the user's LIVE Plasma/KWin session. That is forbidden:
tests must never touch live userspace (CLAUDE.md "SAFETY", RUSH_PROTOCOL.md
"Host safety").

This module is the single source of truth for the isolation contract:

  1. No compositor handle: WAYLAND_DISPLAY / WAYLAND_SOCKET / DISPLAY /
     XAUTHORITY are removed; QT_QPA_PLATFORM is forced to `offscreen`.
  2. No live session bus: DBUS_SESSION_BUS_ADDRESS (and friends) are removed
     from the environment and every probe is executed under
     `dbus-run-session --`, which injects a private throwaway bus.
  3. No writes to the real user profile: XDG_CONFIG_HOME, XDG_CACHE_HOME,
     XDG_DATA_HOME, XDG_STATE_HOME, XDG_RUNTIME_DIR and HOME all point inside
     the caller-provided temporary directory (runtime dir is chmod 700 as
     required for D-Bus/XDG sockets).
  4. No credential material: SSH/GPG/agent sockets and variables whose names
     denote secrets (API keys, tokens, passwords) never reach a probe.
  5. No repo-root litter: probes live in a throwaway workspace built by
     `isolated_probe_workspace()`, which symlinks the repository entries the
     probe's relative QML imports (and `Quickshell.shellDir`, which quickshell
     defines as the probe file's own directory) need to resolve.

Runtime probes must be started through `run_isolated_probe()` (or, for
non-quickshell helpers, `run_isolated_command()`); never call
`subprocess.run(["quickshell", ...])` directly from a test.

`tests/test_isolation_contract.py` enforces this contract and proves the
runtime effect; do not weaken it. It is a tripwire against accidental
regressions, not a security sandbox: probes still run as the user and a
deliberately hostile process could reach whatever the user can reach.
"""

import os
import re
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
    # X11 authorisation cookie: only useful with a live X server (DISPLAY
    # is gone) and must not be forwarded "just in case".
    "XAUTHORITY",
    "MIT-MAGIC-COOKIE-1-DISPLAY",
)

# Agent/broker sockets and display-manager handles: grants a probe access to
# the user's credentials or session manager. Never a legitimate probe input.
AGENT_BOUND_VARS = (
    "SSH_AUTH_SOCK",
    "SSH_AGENT_PID",
    "GPG_AGENT_INFO",
    "GNOME_KEYRING_CONTROL",
    "GNOME_KEYRING_PID",
    "KWALLETD_SOCKET",
    "KSMSERVER",
    "STARTUP_ID",
)

# Name-pattern sweep for credential material a developer's shell may carry
# (API keys, bearer tokens, passwords). Deliberately conservative: it never
# strips a bare PATH/HOME/LANG/QT_*/XDG_* variable.
SENSITIVE_NAME_PATTERNS = (
    re.compile(r"(?i)(API[_-]?KEY|SECRET|TOKEN|PASSWD|PASSWORD|CREDENTIAL|PRIVATE[_-]KEY)"),
    re.compile(r"(?i)^AWS_(SECRET|SESSION)_"),
)


def _is_sensitive(name):
    return any(p.search(name) for p in SENSITIVE_NAME_PATTERNS)


def isolated_probe_env(tmpdir, base_env=None):
    """Return an environment for probes that cannot reach the live session.

    `tmpdir` is a caller-owned temporary directory (e.g. from
    tempfile.TemporaryDirectory()) that receives all private XDG state.
    `base_env` defaults to os.environ; tests of this helper pass a synthetic
    environment containing live-session coordinates.
    """
    env = dict(os.environ if base_env is None else base_env)
    for var in SESSION_BOUND_VARS + AGENT_BOUND_VARS:
        env.pop(var, None)
    for var in [k for k in env if _is_sensitive(k)]:
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


# Entries a probe may reach through a repo-relative path:
#   - `import "./services"` (and sub-paths) — relative QML directory imports
#   - `Qt.resolvedUrl("config/...")` — ConfigService fallback lookups
#   - `Quickshell.shellDir + "/services/kwin/scripts/..."` — quickshell sets
#     shellDir to the *probe file's* directory, so scripts referenced from the
#     services tree must resolve inside the workspace too.
#   - `import "../../components"` / `"../../services"` from `modules/*` files —
#     the QML engine resolves relative URLs LEXICALLY (it does not canonicalize
#     symlinks), so every top-level entry a linked tree can escape into must
#     itself be linked, not just the ones the probe imports directly.
# The symlink farm keeps those probes byte-identical to their repo-root
# versions; only the probe .qml itself moves into the throwaway workspace.
DEFAULT_WORKSPACE_LINKS = ("services", "config", "components", "modules")


def isolated_probe_workspace(workspace, links=DEFAULT_WORKSPACE_LINKS):
    """Make `workspace` (a throwaway dir) able to resolve repo-relative imports.

    Symlinks the named repository entries into the workspace (never copies,
    never touches repository content) and returns the workspace path. A probe
    written inside it can use `import "./services"`,
    `Qt.resolvedUrl("config/...")` and `Quickshell.shellDir` exactly as when
    it lived in the repository root, while `Quickshell.shellDir` stays
    workspace-local so script paths resolve through the links.
    """
    os.makedirs(workspace, exist_ok=True)
    for name in links:
        src = os.path.join(REPO_DIR, name)
        dst = os.path.join(workspace, name)
        if not os.path.isdir(src):
            raise FileNotFoundError(f"repository entry missing for workspace link: {src}")
        if os.path.islink(dst) or os.path.exists(dst):
            continue
        os.symlink(src, dst)
    return workspace


def write_probe(workspace, content, name="_probe.qml"):
    """Write probe QML into a throwaway workspace and return its path.

    Keeps generated probe files out of the repository: cleanup is the
    workspace directory's own (tempfile), so a crashed run can never leave a
    `_test_*.qml` behind in the repo root or overwrite a tracked file.
    """
    os.makedirs(workspace, exist_ok=True)
    path = os.path.join(workspace, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path
