# Colosseum Test Isolation — Wave 1 report (2026-11-07)

STATUS: DONE
BRANCH: `test/colosseum-isolation` (base `67abda2`)
SCOPE: test harness isolation only. No production/application QML, no installer changes.

## Flaw reproduced (source inspection — live session never contacted)

`tests/test_dock_blitz.py` (tests 09, 11, 12, 14–20), `test_dock_keyboard.py`
(runtime `setUpClass`), `test_dock_file_drop.py` and — found during the work —
`test_dock_magnification.py` launched quickshell probes with
`env = os.environ.copy()` + a bare `["quickshell", "-p", ...]` argv. Probes
inherit the full services tree; the inherited `WAYLAND_DISPLAY` and
`DBUS_SESSION_BUS_ADDRESS` let every probe attach to the developer's **live**
KWin session and session bus. Even the `QT_QPA_PLATFORM=offscreen` variants
(blitz 14–16, keyboard, file_drop, magnification) still connected to the
compositor because only Qt rendering was offscreen, not quickshell's own
Wayland/D-Bus connections. The flaw was verified against `git show HEAD` of
each file via the C2 regex in `tests/test_isolation_contract.py` (all four
files flagged at base, none flagged after the fix). No probe was ever run
against the real session on this host.

## Fix

New single source of truth: **`tests/qs_test_env.py`**

- `isolated_probe_env(tmpdir)` — strips `WAYLAND_DISPLAY`, `WAYLAND_SOCKET`,
  `DISPLAY`, `DBUS_SESSION_BUS_ADDRESS`, `DBUS_SYSTEM_BUS_ADDRESS`,
  `DBUS_STARTER_ADDRESS`, KDE session vars, systemd/journal vars; forces
  `QT_QPA_PLATFORM=offscreen`; points `XDG_RUNTIME_DIR` (mode 0700),
  `XDG_CONFIG_HOME`, `XDG_CACHE_HOME`, `XDG_DATA_HOME`, `XDG_STATE_HOME` and
  `HOME` inside the caller's temporary directory.
- `run_isolated_probe()` / `run_isolated_command()` — every probe/helper
  command is wrapped in `dbus-run-session --`, guaranteeing a throwaway
  session bus even if the ambient environment leaked.

This generalizes the pattern already proven in `test_milestone_3a.py`,
`test_theme_service.py` and `test_dock_monitor_profiles.py`.

All 12 quickshell launches in `test_dock_blitz.py`, both launches in
`test_12`/`test_14` reload probes, the three direct
`kwin-window-action.sh` rejection runs in `test_19`, and the single launches
in keyboard / file_drop / magnification now go through the harness. The
test_12 persistence assertion was **not** weakened: it now derives from
`env["XDG_CONFIG_HOME"]` instead of a hardcoded `tmpdir` layout. No assertion
was removed or skipped anywhere; behavior is unchanged.

## Isolation contract regression suite

`tests/test_isolation_contract.py` (new, 5 tests):

- **C1** — helper strips every session-bound var from a synthetic live
  environment *and* from the real host environment; private dirs confined to
  the temp root; runtime dir mode 0700.
- **C2** — static tripwire: no test source (tests/ + controlcenter) may build
  a raw `["quickshell", "-p"` argv; the sanctioned launcher must wrap
  `dbus-run-session`. This test fails against the pre-fix versions of all
  four refactored files.
- **C3** — runtime proof: an isolated probe runs to completion (exit 0) and
  itself observes empty `WAYLAND_DISPLAY`/`DISPLAY`, `offscreen` QPA, a
  private `DBUS_SESSION_BUS_ADDRESS` distinct from the live one, and
  `XDG_CONFIG_HOME` inside the temp dir. Its probe QML is written inside the
  temp dir, not the repo.

## Test outcomes (this host, live Plasma session running — none of these
runs could touch it, per C3's runtime proof)

- `test_isolation_contract + test_dock_blitz + test_dock_keyboard +
  test_dock_file_drop + test_dock_magnification`: **79/79 pass, 0 skip**, 11.4 s.
- Full isolation scan of `tests/` + `modules/controlcenter/`: every remaining
  quickshell launch (`dock_opacity`, `dock_stacks`, `dock_monitor_profiles`,
  `layout_presets`, `json_store`, `theme_service`, `milestone_3a`,
  `test_controlcenter`) already runs under `dbus-run-session` with
  `WAYLAND_DISPLAY` stripped and offscreen QPA.
- `test_dock_meta_shortcuts` deliberately runs a **nested isolated
  `kwin_wayland`** inside its own dbus session — KWin-requiring tests already
  follow the isolated-virtual-KWin path (requirement 6); unchanged.

No KWin-requiring test was found in the refactored suites; none needed a
virtual KWin. No test was skipped in any run above.

## Remaining risks (tracked, not fixed here)

1. **Env isolation ≠ security sandbox.** Probes run as the user; a malicious
   probe could still open `~` by absolute path. Only the VM layer (Colosseum
   goal) is a true boundary. The contract guarantees *no accidental* live
   session attach.
2. Sibling suites use their own inline isolation (compliant behavior, but not
   yet centralized on `qs_test_env`); several keep the real `HOME`. A future
   wave should migrate them; C2 will keep them honest on the argv rule.
3. Refactored suites still write probe QML into the repo root (pre-existing
   convention, removed in `finally`; a hard process kill can leave a stray
   `_test_*.qml`). Tree hygiene issue only, not a session risk.
4. qmllint was not re-run (no QML files changed).

COMMIT / PUSH: recorded in the commit that adds this file; pushed only to
`test/colosseum-isolation`, never merged to `main`.
