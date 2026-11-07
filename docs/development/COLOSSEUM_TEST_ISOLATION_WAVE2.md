# Colosseum Test Isolation — Wave 2 report (2026-11-08)

STATUS: DONE
BRANCH: `test/colosseum-isolation-wave2` (base `3c710d0`, wave-1 `aaee5ab` + evidence docs)
SCOPE: test infrastructure only. No production/application QML, services, launcher or installer changes.

## Mission A — centralized runtime isolation

Every offscreen quickshell probe in the eight target suites now runs through
`tests/qs_test_env.py` (wave 1's single source of truth). Before this wave
each suite built its own `dict(os.environ)` environment that popped only
`WAYLAND_DISPLAY`/`DISPLAY`; the probes therefore still wrote through the
developer's **real** `HOME`, `XDG_CACHE_HOME`, `XDG_DATA_HOME`, `XDG_STATE_HOME`
(anything under `~/.cache`, `~/.local/state`, `~/.local/share`) and could see
`XAUTHORITY`, `SSH_AUTH_SOCK`, `GPG_AGENT_INFO` and credential-shaped
variables. Now:

- `tests/test_dock_opacity.py`, `test_dock_stacks.py`,
  `test_dock_monitor_profiles.py`, `test_layout_presets.py`,
  `test_json_store.py`, `test_theme_service.py`,
  `test_dock_notification_badges.py` (found during this wave),
  `test_milestone_3a.py` (deleted its private duplicate harness) and
  `modules/controlcenter/test_controlcenter.py` use
  `isolated_probe_env()` + `run_isolated_probe()`.
- `test_milestone_3a.test_09` keeps its **genuine nested virtual KWin**
  (`kwin_wayland --virtual` inside its own `dbus-run-session`); only the
  environment construction moved to the harness (offscreen exception
  `QT_QPA_PLATFORM=wayland` against the rig socket, private HOME/XDG).
  No compositor integration test was replaced with an offscreen simulation.
- `test_kwin_bridge_integration.py` / `test_dock_meta_shortcuts.py` /
  `test_runtime_ux.py` rig tests already isolate correctly (re-exec under
  `dbus-run-session`, private runtime) and were deliberately left alone.
- `qs_test_env.isolated_probe_env()` additionally strips `XAUTHORITY`,
  SSH/GPG/keyring agent handles and variables whose *names* carry secrets
  (`*API_KEY`, `*SECRET*`, `*TOKEN*`, `*PASSWORD*`, AWS session vars …).
  `PATH`/`LANG`/`QT_*` survive so legitimate dependencies keep working.

## Mission B — probe workspace (no repo-root `_test_*.qml`)

New harness helpers: `isolated_probe_workspace()` (symlinks
`services/ config/ components/ modules/` into a throwaway dir) and
`write_probe()`. Probes are written inside `tempfile` roots; cleanup is the
temporary directory's own, so a crashed run can no longer litter the repo,
two concurrent runs can no longer fight over one fixed probe filename, and a
failing test cannot overwrite a tracked file.

Verified assumptions (empirical, offscreen): quickshell defines
`Quickshell.shellDir` as the **probe file's directory**, and the QML engine
resolves relative imports **lexically through symlinks**. Therefore the
workspace must link every top-level entry the linked trees can escape into
(`modules/*` does `import "../../components"`), which is why the default link
set is all four trees. QML probe sources are otherwise byte-identical.

Suites migrated to workspaces: all wave-2 targets **plus** wave-1 suites that
were still writing probes into the repo root (`test_dock_blitz.py` ×11
probe files, `test_dock_keyboard.py`, `test_dock_file_drop.py`,
`test_dock_magnification.py`, `test_dock_notification_badges.py`).
`C4` in the contract suite now fails if any `_test_*.qml` reappears in the
repository root. No fixture needed production changes; subprocesses
terminate before cleanup (blocking `subprocess.run` with timeouts; bash rigs
`kill`+`wait` their children).

## Mission C — stronger isolation contract

`tests/test_isolation_contract.py` grew from 5 to 9 tests:

- C2 is now an **AST-based scanner** instead of one literal regex. It flags:
  raw argv launches, `Popen`, variable-built argv lists, env-less launches,
  `os.system`/`os.popen` driver scripts, and scopes that mention a quickshell
  command without wiring `dbus-run-session`. Namespaced mentions
  (`/org/quickshell/kwinbridge`, `quickshell-kwineventbridge-<hash>`) and
  docstrings are not false-positived (covered by a positive-control test).
- New regression fixtures deliberately reintroduce each historically unsafe
  pattern as disposable synthetic sources; the scanner must flag all six.
- C1 additionally proves agent sockets (`SSH_AUTH_SOCK`, `GPG_AGENT_INFO`,
  keyring) and credential-named variables are stripped, that `PATH` survives,
  and that `HOME` no longer points at the developer's profile — synthetic and
  real-host variants.
- C3 runtime proof extends: the probe itself asserts empty `HOME`-leakage
  (`HOME` == tempdir) and empty `SSH_AUTH_SOCK` next to the existing
  compositor/bus checks.
- C4 proves the workspace resolves via symlinks only (never copies), is
  idempotent, keeps probes out of the repo and leaves repository content
  untouched.

Honesty note (kept in the module docstring): the scanner is a **tripwire**,
not a security proof — dynamic argv assembly from non-literal parts is out of
reach of static analysis; C3 covers the behavioral side.

## Verification (this host; live Plasma session running — none of these runs
could touch it, per C3's runtime proof)

| Run | Result |
|---|---|
| Wave-1 79-test set (baseline, pre-change) | 79/79 pass, 0 skip, 11.4 s |
| Wave-2 target suites (baseline, pre-change) | 110/110 pass, 0 skip, 104.7 s |
| Wave-1 set re-run (post-change) | **83/83 pass, 0 skip, 11.8 s** (79 originals + 4 new contract tests) |
| Full `unittest discover -s tests` (post-change) | **347 tests, OK, 4 skipped, 168.5 s** |

The 4 skips are pre-existing honest gates, verified by verbose reruns —
none introduced by this wave: `test_runtime_ux` live-brightness and
live-WindowsRunner tests (opt-in `QS_KDE_LIVE_SESSION_TESTS=1`),
`test_bridge_fallback` built-binary test and `test_kwin_bridge_integration`
whole class (bridge `.so` not built in this checkout; the static
bridge-failure contract tests still run and pass). No skipped test is
counted as passing anywhere above. After all runs: no `_test_*.qml` in the
repo root, no new `/tmp/qs-*` litter (temporary-directory cleanup verified).

qmllint: no QML files changed; suites that embed qmllint checks
(milestone 3A, controlcenter, json_store, presets, stacks, badges, …) all
pass unchanged, which re-lints the touched trees' consumers.

## Remaining risks / incomplete coverage

1. **Timeout kill path:** `subprocess.run(timeout=...)` kills the direct
   child on timeout; a `quickshell` under `dbus-run-session` could in
   principle orphan for the timeout path only (the deterministic paths all
   reap via `kill`/`wait`). Pre-existing in wave 1; unchanged behavior.
2. **Env isolation ≠ security sandbox** (carried from wave 1): probes run as
   the user and could still open `~` by absolute path; only the VM layer is a
   true boundary.
3. `test_kwin_bridge_integration.py` launches its virtual KWin with
   `env=os.environ` *inside* its private `dbus-run-session` (bus is private,
   socket is private), but not a stripped HOME. Left untouched deliberately:
   it is the genuine-compositor reference rig; a wave-3 candidate to route
   through `isolated_probe_env`.
4. `test_runtime_ux.py` live-session MPRIS/KWin enumeration remains opt-in
   via `QS_KDE_LIVE_SESSION_TESTS=1` (skipped by default; honest skip).
5. Scanner limitations are listed in Mission C above.

COMMIT / PUSH: `75f690d`, pushed to `test/colosseum-isolation-wave2`.
Never merged to `main`.
