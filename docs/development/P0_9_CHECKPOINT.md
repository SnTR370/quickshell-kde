# P0 #9 Intellihide — WIP checkpoint (2026-10-29, PAUSED for public beta rush)

> **COMPLETED (2026-10-30).** Beta verification finished: all suites green,
> one real defect fixed (missing `import "../config"` in WindowService.qml)
> and three stale test assertions updated. Full results in
> [`P0_9_VERIFICATION_REPORT.md`](P0_9_VERIFICATION_REPORT.md), which
> supersedes `P0_9_INTELLIHIDE_BLOCKED.md` (removed; preserved in git
> history). This checkpoint document is kept for the KWin 6.8 findings and
> rig instructions below.

> **RESUMED & INTEGRATED (2026-10-29, later session).** The bridge is now
> wired into the shell exactly as planned in "Remaining tasks" below:
> `WindowService` loads `bridge/BridgeHost.qml` through a `Loader`
> (live KWin session + `ConfigService.dockIntellihide` only), merges
> `batchReceived` batches via `BridgeRecords.applyBatch` into
> `windowStates`/`windowOutputs`, forwards desktop records to the new
> `KWinService.applyExternalDesktop()`, clears state on `desynchronized`,
> and suspends snapshot-sync writes (`refreshWindowOutputs`, scanner
> pruning, in-flight snapshot applies) while `bridgeActive`. Missing plugin
> or bridge failure degrades to the old snapshot path. Tests:
> `tests/test_bridge_records.py` (node, 19 cases) and
> `tests/test_kwin_bridge_integration.py` (isolated `kwin_wayland --virtual`
> rig: lifecycle + live event merge + spoof rejection + orphan recovery —
> skips when tools/binaries are missing). Both green; see git history.
> Remaining release blockers: built `.so` artifacts still gitignored
> (design doc says ship them for ordinary users — decision needed);
> `tests/test_dock_keyboard.py::test_01_dock_window_contract` fails
> pre-existing on this branch (unrelated `|| keyboardNavActive` assertion
> against `modules/dock/Dock.qml`); full `quickshell`-probe suites
> (`test_dock_blitz`, `test_runtime_ux`) not run this session because they
> launch shells against the live desktop.

Branch `feat/dock-intellihide`. Development paused by user decision; this
checkpoint preserves all working code, rig files and findings. **Not merged,
not pushed, not beta-ready.** The compiled bridge is **not enabled anywhere**
in the shell: no QML file outside `services/kwin/bridge/` references
`KWinEventBridge`, `BridgeHost` or `BridgeRecords` (verified by grep). The
existing snapshot-based window-state path and the existing Intellihide config
toggle (`ConfigService.dockIntellihide`) are untouched and behave exactly as
before this work.

## What is implemented and verified (this session)

All of it inside an isolated rig (`kwin_wayland --virtual` + `dbus-run-session`
+ private `XDG_RUNTIME_DIR`/`XDG_CONFIG_HOME`; the live Plasma session was
never touched):

1. **Compiled QtDBus QML plugin** — `services/kwin/bridge/`
   (`kwinbridge.h/.cpp`, CMakeLists, `BridgeHost.qml`, generated `qmldir` +
   `kwineventbridge.qmltypes`; built `.so` files exist on disk but are
   gitignored).
   - `KWinEventBridge` QML element: registers a per-checkout session-bus name
     (`org.quickshell.kwineventbridge.<sha256-8-of-template-path>`), exports
     exactly one D-Bus method `record(QString)` at
     `/org/quickshell/kwinbridge` (interface pinned via
     `Q_CLASSINFO("D-Bus Interface", "org.quickshell.kwinbridge")`).
   - Sender validation through `QDBusContext` against the
     `QDBusServiceWatcher`-tracked owner of `org.kde.KWin`.
   - Envelope validation (version 1, generation, sequence; duplicates ignored,
     gaps/generation mismatch → `desynchronized` signal + script reload with
     exponential backoff capped at 5 s, healthy traffic resets it).
   - 0 ms single-shot flush timer → `batchReceived(QString)` (JSON array of
     payload strings); pending bound 4096, payload bound 2 MiB.
   - Script lifecycle via public `/Scripting` D-Bus only: unload-then-load
     (orphan cleanup by stable pluginName
     `quickshell-kwineventbridge-<hash>`), `run` on `/Scripting/Script<id>`.
   - KWin owner loss → `desynchronized("kwin-owner-lost")` + state flush;
     owner return → reload. Clean destruction unloads the script.
   - Generated script instance written 0600 into
     `$XDG_RUNTIME_DIR/quickshell-kwin-bridge/<pluginName>/bridge.js`.
   - Module loads via directory import (`import "file:.../services/kwin/bridge"`)
     AND via `Loader { source: ".../bridge/BridgeHost.qml" }` (implicit
     same-directory qmldir import) — both verified with a QQmlEngine harness.
     Plugin rpath is `$ORIGIN` only; both `libkwineventbridge.so` (backing)
     and `libkwineventbridgeplugin.so` (plugin) must sit side by side.
2. **Resident KWin script template** —
   `services/kwin/scripts/kwin-event-bridge.js` (placeholders `__BUS_NAME__`,
   `__GENERATION__`). Tracks normal windows: snapshot on load, per-window
   `frameGeometryChanged`/`minimizedChanged`/`desktopsChanged`/
   `outputChanged`/`fullScreenChanged`/`maximizedChanged`/`keepAboveChanged`/
   `interactiveMoveResizeStepped`, plus `windowAdded`/`windowRemoved`/
   `currentDesktopChanged`.
3. **Pure JS record merge/validation** — `services/kwin/BridgeRecords.js`
   (`applyBatch`/`validateWindowRecord`: strict booleans, finite geometry,
   UUID/desktop-id patterns, `{uuid}`-brace and `0_` normalization, atomic
   snapshot replace, update/remove/desktop records, capability defaults).
   Not yet wired into any QML.

### E2E evidence (`.rig/e2e.sh`, run 2026-10-29)

Inside the isolated session, with the committed plugin loaded by a `qml`
harness process: **9 payloads received in order** — snapshot, window-add
update, move update, resize update, minimize update, unminimize update,
fullscreen update, desktop-switch record, remove record; spoofed `record`
call from a non-KWin sender answered `error:sender`; clean harness exit
unloaded the script (`isScriptLoaded` false); SIGKILL left the orphan loaded
(true); a fresh harness start cleaned the orphan and unloaded again on exit.
Probe logs preserved in `/tmp/ih-e2e/logs/` (disposable) and `.rig/e2e.sh`
(reproducible). Note: the rig script itself exits non-zero (bash job-control
notification for the phase-B SIGKILL) — assert on the printed markers, not
the exit code, when converting to a python test.

## Critical KWin 6.8 findings (verified in rig, do not re-research)

- `callDBus` **requires a trailing function argument**: without one, string
  arguments fail to marshal ("Unregistered type QJSValue passed in
  arguments"). With one callback, string args marshal fine.
- `callDBus` error callbacks are **never invoked** on KWin 6.8 (reply
  callbacks fire on success). Receiver-death detection from the script is
  therefore impossible; staleness is handled bridge-side (generation
  mismatch + orphan cleanup), at the cost of bounded KWin log noise while a
  dead receiver still gets events.
- Directly `registerObject`-exported methods need
  `Q_CLASSINFO("D-Bus Interface", ...)` to be reachable under a chosen
  interface name (kdotool avoids this by calling with an empty interface).
- `workspace.currentDesktop` is a `VirtualDesktop` **object** (use `.id`);
  `window.internalId` stringifies as `{uuid}` **with braces**.
- KWin log capture in the rig needs `QT_FORCE_STDERR_LOGGING=1` (otherwise
  `print()` output from scripts is invisible).
- `QDBusConnection::sessionBus()` returns by value in Qt6.
- kdotool pattern reference: `callDBus(addr, "/", "", "result", msg.toString())`.

## Remaining tasks (exact restart point)

1. `WindowService.qml`: `Loader` for `bridge/BridgeHost.qml`, active only when
   `isLiveKWinSession && ConfigService.dockIntellihide`; call
   `item.enable(Quickshell.shellDir + "/services/kwin/scripts/kwin-event-bridge.js")`
   in `onLoaded`; connect `batchReceived` → `BridgeRecords.applyBatch` →
   assign `windowStates`/`windowOutputs` + `windowStateRevision++`, forward
   `desktopId` to `KWinService.applyExternalDesktop`; on `desynchronized`
   clear both maps (stale until next snapshot). Gate `refreshWindowOutputs()`
   and the `windowStates`/`windowOutputs` pruning inside
   `parseWindowsOutput()` on a `bridgeActive` property (bridge is the
   authoritative writer when active).
2. `KWinService.qml`: add `applyExternalDesktop(desktopId)` (set
   `currentDesktopId`, `updateActiveDesktopState()`, `refreshDesktops()`).
3. Tests: node-driven `BridgeRecords` suite (extend
   `tests/test_intellihide.py` or new `tests/test_bridge_records.py`: uuid
   normalization, strict validation rejects, atomic snapshot, update/remove/
   desktop, capability defaults); convert `.rig/e2e.sh` into
   `tests/test_kwin_bridge_integration.py` (skip when kwin_wayland/
   dbus-run-session/qdbus6/qml/kdotool or built `.so` missing; assert on
   markers, not exit code).
4. `qmllint` the touched QML (`-I services/kwin/bridge` for `BridgeHost.qml`).
5. Decide whether to commit the built `.so` artifacts (design doc says yes
   for ordinary users; current WIP gitignores them — revisit at resume).
6. Update `DEVELOPMENT.md`, replace `P0_9_INTELLIHIDE_BLOCKED.md` with a
   verification report, final review, commit, push to `feat/dock-intellihide`.

## Build instructions

```sh
cmake -S services/kwin/bridge -B /tmp/kwineventbridge-build -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/kwineventbridge-build -j4
cp /tmp/kwineventbridge-build/libkwineventbridgeplugin.so \
   /tmp/kwineventbridge-build/libkwineventbridge.so \
   /tmp/kwineventbridge-build/qmldir \
   /tmp/kwineventbridge-build/kwineventbridge.qmltypes \
   services/kwin/bridge/
```

Requires Qt6 (>= 6.6) Qml + DBus dev packages. The two `.so` files must be
copied together (plugin rpath is `$ORIGIN`).

## Rig scripts (`.rig/`, all reusable)

- `e2e.sh` — full 3-phase lifecycle + event E2E (see evidence above).
- `probe3.sh` — callDBus marshalling/callback probe against the real bridge.
- `probe2.sh` — script lifecycle + log-capture verification.
- `probe-session.sh` / `probe-inner.sh` / `kwin-diag.sh` — earlier probes
  from the previous session (kept for history).

## Safety state

No tracked file was modified before this checkpoint commit. The live Plasma
session, `~/.config/quickshell`, and user KWin configuration were never
touched. All runtime test state lives under `/tmp` (disposable). `.agents/`
(editor tooling, unrelated to this feature) is intentionally left untracked.
