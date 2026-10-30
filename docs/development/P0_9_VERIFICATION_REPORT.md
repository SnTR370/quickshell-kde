# P0 #9 Intellihide — final beta verification report

Verified 2026-10-30, branch `feat/dock-intellihide`. Environment: KWin
6.8.0-1, Quickshell 0.3.2-1, qt6-declarative 6.12.0-1, kdotool 0.3.0,
cmake 4.4.4, Python 3.14, Node (for node-driven suites). This report
supersedes `P0_9_INTELLIHIDE_BLOCKED.md` (all its blockers are resolved by
the event bridge) and closes the checkpoint in `P0_9_CHECKPOINT.md`.

**Status: BETA READY** (see "Unverified live behavior" for the one honest
caveat: the bridge has not been exercised inside the developer's active
Plasma session — by design, all live-KWin verification ran in isolated
`kwin_wayland --virtual` rigs).

## Defects found and fixed during this verification

### 1. `WindowService.qml` referenced `ConfigService` without importing it (real defect)

`services/kwin/WindowService.qml` used `ConfigService` at three sites — the
bridge `Loader` gating (`active: root.isLiveKWinSession &&
ConfigService.dockIntellihide`) and the filter defaults inside
`_filterCtx()`/`getFilteredRunningAppIds()` — while only importing
`services/kwin` and `services/applications`, neither of which exports
`ConfigService`. Consequences (reproduced in an isolated rig):

- Every `ReferenceError` in the Loader binding left `Loader.active` at its
  default `true`, so **the bridge loaded even with Intellihide disabled**
  (with the plugin built it would install the resident KWin script for
  users who never enabled the feature).
- `cycleAppWindows(appId, reverse, screenName)` hard-passes `mode:
  undefined`, so **every dock wheel-cycle threw** and aborted mid-handler —
  the same failure mode that made three blitz runtime probes hang past
  their 6 s timeouts.

Fix: one line — `import "../config"` (the established pattern in
`ApplicationService.qml` / `NotificationService.qml`). After the fix the
previously hanging probes complete with fully correct cycling results, and
the bridge Loader correctly stays inactive while `dockIntellihide` is false
(verified: no bridge log lines with a fresh default config).

The import was introduced as a latent bug by P0 #8 (`getFilteredRunningAppIds`,
commit `e6f88f5`) and extended by P0 #9 (bridge gating, commit `e69df98`);
it went unnoticed because the full-shell probe suites had not been re-run
since P0 #7. A repo-wide audit found no other file referencing a singleton
without importing its directory.

### 2. Stale test assertions (semantics preserved, formatting/signature drift)

- `tests/test_dock_keyboard.py::test_01` pinned `|| keyboardNavActive\n` —
  the Intellihide restructure wrapped the `isRevealed` binding so the token
  is now followed by `)`. Updated to a formatting-tolerant assertion on the
  same contract.
- `tests/test_dock_blitz.py::test_10` pinned the pre-P0 #8 cycling signature
  `cycleAppWindows(appId, reverse)` and its call site. Updated to the
  current `(appId, reverse, screenName)` contract.
- `tests/test_runtime_ux.py::test_19` pinned the pre-Intellihide single-line
  `isRevealed` binding. Updated to assert the hover OR-chain feeds
  `Intellihide.isRevealed(...)`.

## Packaging

- Only sources, `qmldir` and `kwineventbridge.qmltypes` are committed; the
  `.so` binaries are gitignored (machine/Qt-build specific — shipping them
  would break on any other system). Build/install procedure, ABI
  requirements, availability check and fallback behavior are documented in
  `services/kwin/bridge/README.md`; the stale CMakeLists comment claiming
  binaries are committed was corrected.
- Clean-room build verified twice from `cmake -S services/kwin/bridge`:
  succeeds, plugin `.so` bit-identical across builds; backing `.so` differs
  only by embedded build paths. RUNPATH is `$ORIGIN`; both `.so` files must
  be installed side by side.
- Fallback verified for both failure classes (missing binary; present but
  unloadable/wrong-ABI binary): `Loader.Error`, warning logged, no crash,
  snapshot sync remains authoritative. Codified as
  `tests/test_bridge_fallback.py` (4 cases, permanent regression coverage).

## Regression results (all actual runs, no simulated results)

| Suite | Result | Environment |
|---|---|---|
| `tests.test_bridge_records` (19 cases) | PASS | node |
| `tests.test_bridge_fallback` (4 cases) | PASS | offscreen qml runtime |
| `tests.test_dock_keyboard` (13 cases) | PASS | offscreen quickshell |
| `tests.test_dock_window_filter` | PASS | node/static |
| `tests.test_intellihide` | PASS | node |
| `tests.test_milestone_3a` | PASS | static/offscreen (note: includes a 2 s full-shell startup smoke) |
| `tests.test_kwin_bridge_integration` (3-phase E2E) | PASS | self-isolated rig (private bus + `kwin_wayland --virtual`) |
| `tests.test_dock_blitz` (20 cases) | **PASS** (was 16/20: 1 stale assert, 3 hangs from defect 1) | isolated rig |
| `tests.test_runtime_ux` (24 cases) | **PASS** (was 23/24: 1 stale assert) | isolated rig |

`qmllint` clean on all touched QML (`WindowService.qml`, `KWinService.qml`,
`Dock.qml`, `BridgeHost.qml`).

Isolated rig for the full-shell suites: private `XDG_RUNTIME_DIR` /
`XDG_CONFIG_HOME`, `dbus-run-session`, nested `kwin_wayland --virtual`
(1280x800), one resident test window, `QT_QPA_PLATFORM=wayland` pointed at
the nested socket. The live Plasma session was never touched by blitz or
runtime_ux. (One pre-existing exception: `test_milestone_3a`'s startup smoke
briefly launches the full shell against the current session — inherited
behavior, flagged for future isolation.)

## Final review findings

- No new polling or background processes from P0 #9: the bridge C++ is
  fully event-driven (D-Bus method calls + `QDBusServiceWatcher`; only two
  single-shot timers — 0 ms flush batching and capped reload backoff). The
  resident KWin script is unloaded on clean shutdown; crash orphans are
  cleaned by the next start (verified in the E2E phases B/C).
- While the bridge is active it is the sole writer of
  `windowStates`/`windowOutputs`: snapshot spawns and scanner pruning are
  gated on `!bridgeActive` (also asserted statically by
  `test_bridge_fallback.py::test_04`).
- Bridge drop (config toggle, plugin failure, KWin restart) repopulates
  state through the snapshot path (`onBridgeActiveChanged`).

## Unverified live behavior

- The bridge has not been run inside the developer's active Plasma session
  (deliberately — safety constraint for this verification). Everything
  around it was verified in isolated rigs with a real `kwin_wayland` and a
  real session bus. First real-world activation of
  `dockIntellihide` on the live desktop remains a user-run smoke test.
- Multi-monitor Intellihide behavior on physical hardware (the rig is a
  single virtual output; output-change events are covered by unit tests and
  the E2E only single-output).

## Remaining known limitations (not beta blockers)

- KWin 6.8 `callDBus` error callbacks never fire; staleness is handled
  bridge-side (generation mismatch + orphan cleanup) at the cost of bounded
  KWin log noise while a dead receiver still gets events (documented in
  `P0_9_CHECKPOINT.md`).
- The rig scripts in `.rig/` remain for manual reproduction; the automated
  equivalent is `tests/test_kwin_bridge_integration.py`.
