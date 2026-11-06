# Core Reliability & Regression Test Marathon — Execution Log

**Branch:** `test/core-reliability-gates`
**Base Commit:** `c4b3163` (= `origin/fix/post-audit-remediation` tip at marathon start)
**Session 1:** interrupted by an EVREN 503 during source/test inventory
(nothing persisted; inventory redone lean in session 2)
**Session 2:** 2026-11-06 → 2026-11-07 (EVREN classifier outages repeatedly
blocked Bash mid-session; test runs completed under Accept Edits)

Goal: isolated **behavioral** regression tests for foundational services.
Rules: never touch the live Plasma session; probes run offscreen under
`dbus-run-session` with private `XDG_RUNTIME_DIR`/`XDG_CONFIG_HOME`;
verify and document genuine production defects; commit test work only;
no merge to `main`.

## Source/Test Inventory (session 1+2, lean)

Foundational services and their existing coverage as of `c4b3163`:

| Area | Dedicated tests? |
|---|---|
| `services/kwin/bridge`, `BridgeRecords.js`, `Intellihide.js`, `MetaShortcuts.js`, `WindowFilter.js` | yes (`test_bridge_*`, `test_intellihide`, `test_dock_meta_shortcuts`, `test_dock_window_filter`, `test_kwin_bridge_integration`) |
| `services/config/DockStacks.js` / `LayoutPresets.js` / `MonitorProfiles.js` | yes (`test_dock_stacks`, `test_layout_presets`, `test_dock_monitor_profiles`) |
| `services/config/ConfigService.qml` | indirect (layout presets E2E, blitz, runtime UX) |
| `services/theme/ThemeService.qml` | yes (`test_theme_service`) |
| `services/applications` (`scan_apps.py`, `ApplicationService.qml`, `FileDrop.js`) | yes (blitz P0#2 tests, `test_dock_file_drop`) |
| `services/core/JsonStore.qml` | **none** → session 2 target |
| `services/core/ModuleRegistry.qml` | indirect (layout presets validation, `VALID_MODULES` catalog checks) |
| `services/core/Log.js` | none (trivial, low value) |
| `services/audio`, `battery`, `brightness`, `mpris`, `network`, `notifications` | partial/indirect (controlcenter module tests, notification badges) |

Additional session-2 inventory notes: `Log.js` is imported by 11 QML files
(all services) — a pure `.pragma library` module, only worth static contract
tests at most. `ModuleRegistry` has exactly one consumer
(`ConfigService.qml`); its logic is already exercised through the layout
preset validation tests, so dedicated coverage has low marginal value.
Hardware/session services (audio, battery, brightness, mpris, network) talk
to live session buses (PipeWire, UPower, etc.) — behavioral tests for them
belong in the "isolated compositor rig" tier (nested kwin_wayland /
private D-Bus with fakes), the same tier as `test_kwin_bridge_integration`.
Not attempted in session 2.

## Session 2 — 2026-11-06: JsonStore behavioral suite

**Scope:** `tests/test_json_store.py` — first direct coverage of
`services/core/JsonStore.qml`, the JSON persistence primitive under
ConfigService (x2 stores) and ThemeService.

- Static contracts: public API surface (signals/functions/properties),
  atomic write (tmp + `mv -f`, tmp cleanup on failure, `mkdir -p`),
  `.bak` backup gated on `hadParseError`, root-object restriction on
  load, qmllint.
- Isolated runtime E2E (one `quickshell -p` probe process per scenario,
  offscreen, private D-Bus/XDG dirs, temp store paths):
  - `load()`: valid JSON, fallback file, missing file, corrupt JSON,
    empty file, array root
  - `save()`: roundtrip incl. nested dir creation; undefined/function
    rejection; empty-path rejection; rapid-save coalescing (last write
    wins, both `savedValue` emissions); `load()` during in-flight write
    (deferred, re-reads persisted bytes); read superseded by save (no
    stale `loaded` event)
  - parse-error recovery: `.bak` preserves corrupt bytes, clean rewrite,
    clean reload; no `.bak` without prior parse error

### Verified production defect (documented, NOT fixed — test-only marathon)

**JsonStore save/load root-shape asymmetry.** `save(data)` runs
`JSON.stringify(data)` without validating the root shape, so it accepts
arrays (and scalars) and persists them. `load()` rejects exactly those
files (`Root JSON value must be an object`), resetting the store to
defaults on next start. A caller regression that saves an array would
therefore *silently lock the user out of their persisted config*. All
current in-repo callers save plain objects, so this is latent, not live.
Pinned by `test_save_array_roundtrip_documented_defect`. Fix direction:
mirror load()'s root-object check in `save()`.

### Verification evidence

- `python3 -m unittest tests.test_json_store -v` → **20 tests, 20 passed,
  0 failed** (5 static contracts + 15 isolated runtime scenarios), 5.2 s,
  2026-11-07. Run under Accept Edits after repeated EVREN auto-mode
  classifier outages blocked Bash during session 2.
- Isolation audit of the new suite (why it is safe to run):
  - probe imports only `QtQuick`, `Quickshell`, `./services/core`
    (JsonStore + pure-data ModuleRegistry singleton) — no ConfigService /
    KWinService singleton chain, therefore no `qdbus6` against live KWin;
  - JsonStore's only subprocesses are `cat`/`sh` against the temp store
    path (no D-Bus, no compositor interaction);
  - harness strips `WAYLAND_DISPLAY`/`DISPLAY`, forces
    `QT_QPA_PLATFORM=offscreen`, private `XDG_RUNTIME_DIR` +
    `XDG_CONFIG_HOME` temp dirs, wraps in `dbus-run-session`.

### Full regression run WITHHELD — test_dock_blitz.py isolation gap

The default `python3 -m unittest discover -s tests` regression was **not**
run in session 2. MiMo (session review) flagged an unresolved isolation gap
in `tests/test_dock_blitz.py`, confirmed by inspection:

- Its runtime probes (test_09, test_11, test_12, test_14..test_20) run
  `quickshell -p` with the **inherited environment**: `WAYLAND_DISPLAY` and
  the real session bus are never stripped, there is no `dbus-run-session`
  wrapper and no private `XDG_RUNTIME_DIR`.
- The probes import the full `./services` singleton tree, so
  `KWinService`/`WindowService` issue `qdbus6` against the **live KWin**
  even when `QT_QPA_PLATFORM=offscreen` is set (test_14+); test_09 does not
  even set offscreen.
- This contradicts the "every test is session-safe" claim in
  DEVELOPMENT.md's Test Suite Inventory (P1-3 remediation) — at least for
  the blitz runtime tier. Follow-up task for the next marathon session:
  bring the blitz runtime probes up to the private-D-Bus/offscreen/private-
  XDG standard used by `test_layout_presets`/`test_json_store`, or gate
  them behind an opt-in env var like the live-session tests.
