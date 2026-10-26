# Public Beta P0 Marathon Execution Log

## Phase 0 — Baseline and Environment

- **Branch:** `feat/public-beta-p0-marathon`
- **Base Commit:** `b786eb6d8350a3e6774339b663a6cd02b46c39e4` (`origin/feat/dock-state-reliability`)
- **Environment & Tooling:**
  - Quickshell `0.3.2` (`/usr/bin/quickshell`)
  - KWin Wayland `6.8.0` (`/usr/bin/kwin_wayland`, headers at `/usr/include/kwin/`)
  - Qt / QtTest `6.12.0` (`/usr/lib/qt6/bin/qmltestrunner`, `/usr/bin/qmllint`)
  - `qdbus6`, `kdotool v0.3.0`, `python3`
- **Baseline Test Suite Results:**
  - `tests/test_dock_blitz.py`: 18 passed in 5.159s
  - `tests/test_milestone_3a.py`: 14 passed in 4.819s
  - `tests/test_runtime_ux.py`: 24 passed in 2.768s
  - `modules/controlcenter/test_controlcenter.py`: 9 passed in 0.475s
  - `tests/tst_dock_autohide.qml` (`qmltestrunner`): 3 passed in 0.606s
  - `qmllint` across all repository `.qml` files: 0 errors
  - **Total Baseline Tests:** 68 passed, 0 failed
- **Baseline Isolated Runtime & Memory Metrics:**
  - Service initialization (`Component.onCompleted` in isolated `quickshell -p` probe): `143.5 ms` (total process wall time `374.4 ms`)
  - Peak RSS (`VmHWM` / `VmRSS`): `159,324 kB` (~155.6 MB)

---

## Phase 1 — P0 #5: KWin Native Window Actions

- **Changed Components:**
  - `services/kwin/scripts/kwin-window-action.sh`
  - `services/kwin/WindowService.qml`
  - `modules/dock/DockMenu.qml`
  - `modules/dock/WindowChooserPopup.qml`
  - `tests/test_dock_blitz.py`
- **Implemented Functionality:**
  - Extended KWin 6 scripting helper (`kwin-window-action.sh`) with UUID-validated actions: `minimize`, `unminimize`, `toggle-minimize`, `maximize`, `unmaximize`, `toggle-maximize`, `fullscreen`, `toggle-fullscreen`, `keep-above`, `toggle-keep-above`, `move-output`, and `move-desktop` (including `"all"` for sticky/on-all-desktops).
  - Extended `WindowService` with non-optimistic dispatch and KWin state reconciliation (`windowStates`, `getWindowState`, `getWindowCapabilities`, `canMinimizeWindow`, `canMaximizeWindow`, `canFullScreenWindow`, `canKeepAboveWindow`, `canCloseWindow`, `getTargetDesktopsForWindow`, `toggleMinimizeWindow`, `toggleMaximizeWindow`, `toggleFullScreenWindow`, `toggleKeepAboveWindow`, `moveWindowToDesktop`).
  - Preserved restoration capability when a window is already minimized even if `minimizable` is reported false.
  - Added compact per-window state controls and virtual desktop move targets in `DockMenu.qml` and capability-gated close button in `WindowChooserPopup.qml`.
- **Verified Results:**
  - `qmllint` on all modified QML files: 0 errors.
  - `TestDockBlitz.test_19_runtime_kwin_native_window_actions_and_capabilities` and `TestMilestone3A.test_13_kwin_window_actions`: passed.
  - Full Python unittest suite (57 tests in `tests/` + 9 in `modules/controlcenter/`): 66 passed, 0 failed.
- **Remaining Risks:**
  - Physical multi-monitor and live KWin compositor window transitions are verified via isolated QML runtime probes and script dry-runs; physical desktop window manipulation was intentionally not executed against the developer's active session.

---

## Phase 2 — P0 #6: XDG Desktop Quick Actions

- **Changed Components:**
  - `services/applications/scan_apps.py`
  - `services/applications/ApplicationService.qml`
  - `modules/dock/DockMenu.qml`
  - `tests/fixtures/applications/org.mozilla.firefox.desktop`
  - `tests/fixtures/applications/org.kde.dolphin.desktop`
  - `tests/fixtures/applications/org.example.hidden.desktop`
  - `tests/test_dock_blitz.py`
- **Implemented Functionality:**
  - Implemented Freedesktop Desktop Entry quick action parsing (`Actions=...` and `[Desktop Action <id>]`) in `scan_apps.py` preserving declared ordering, deduplicating repeated action IDs, respecting localized `Name[locale]=` keys, filtering `OnlyShowIn`/`NotShowIn`, excluding missing/invalid/undeclared action groups, and safely tokenizing `Exec=` arguments (`execArgs`) without shell evaluation.
  - Strictly isolated action binaries, icons, and names from application identity aliases (`generate_aliases` and `ApplicationService.rebuildAliasMap`).
  - Added duplicate scanner process protection (`scanProc.scanPending`) and `getAppActions` / `launchAppAction` in `ApplicationService.qml`.
  - Exposed application quick actions in `DockMenu.qml`, prioritizing desktop-defined `"New Window"` actions when running while preserving normal application launching and apps without quick actions.
- **Verified Results:**
  - `qmllint` on all modified QML files: 0 errors.
  - `TestDockBlitz.test_20_xdg_desktop_quick_actions_fixtures_and_runtime`: passed.
  - Full Python unittest suite (58 tests in `tests/` + 9 in `modules/controlcenter/`): 67 passed, 0 failed.
- **Remaining Risks:**
  - None identified; field codes without file/URL context (`%f`, `%F`, `%u`, `%U`) are stripped per Freedesktop spec for context-menu invocation.

---

## Phase 3 — P0 #7: Keyboard Accessibility

- **Changed Components:**
  - `modules/dock/DockKeyboardNav.qml` (new), `modules/dock/qmldir`
  - `modules/dock/Dock.qml`, `modules/dock/DockItem.qml`, `modules/dock/DockMenu.qml`, `modules/dock/WindowChooserPopup.qml`, `modules/dock/DockSeparator.qml`
  - `components/IconButton.qml`, `components/AnchoredPopup.qml`
  - `tests/test_dock_keyboard.py` (new)
- **Implemented Functionality:**
  - Deterministic focus order (launcher, pinned, unpinned running, settings); separators/hidden/disabled items skipped.
  - Horizontal: Left/Right (wrapping). Vertical: Up/Down (wrapping). Home/End. Tab/Shift+Tab walk the Dock and hand focus back at either end (no trap).
  - Enter/Space = left click; Menu / Shift+F10 = context menu; Escape closes popup (focus stays on the item), a second Escape leaves the Dock.
  - Popups (xdg_popup, no keyboard grab) are driven by the focused DockItem, which forwards keys to `AnchoredPopup.handleKeyEvent`: Up/Down/Left/Right/Tab/Shift+Tab/Home/End move over *enabled* actions, Enter/Space activate, Escape closes. Focus ring on the current action.
  - Accessible roles/names: Dock items and buttons (Button), popup (PopupMenu), every menu/chooser action (MenuItem), separators ignored. Visible focus ring on Dock items and buttons.
  - Mouse, drag & drop, wheel cycling and middle click are unchanged (click logic only extracted into `activateItem` / `toggleContextMenu` / `launchNewInstance`).
- **How keyboard entry is reached (local only):**
  - `qs ipc call dock focus` (first screen; other screens: `dock-<screen name>`) and `qs ipc call dock release`. Bind it to a key yourself if wanted; this change does **not** register or edit any KDE global shortcut.
  - `WlrLayershell.keyboardFocus` is `None` by default and becomes `OnDemand` only while `keyboardNavActive`. The Dock never requests focus on its own, and releases it on Escape, Tab past either end, Dock hide, or when the compositor activates another window.
  - The Dock stays revealed while keyboard-active and re-arms the autohide timer on release.
- **Verification layers:**
  - STATIC: source contracts (`tests/test_dock_keyboard.py::TestDockKeyboardStatic`).
  - OFFSCREEN (simulated QtTest key/mouse events, isolated `XDG_CONFIG_HOME`, `WindowService` overrides): real DockItem/IconButton/DockKeyboardNav/DockMenu/WindowChooserPopup. The harness window only mirrors the thin Dock window API because `PanelWindow` has no offscreen backend.
  - PHYSICAL Wayland: **not verified**. Whether KWin grants `OnDemand` keyboard focus to the Dock surface on request, and screen-reader output, were not tested on a real session.
- **Performance:** no timers/processes/polling added. Focus lists and popup action lists are computed only on key presses; one small non-visual `DockKeyboardNav` per Dock window.

## P0 #8 — Dock desktop & monitor window filtering
- **Status:** DONE (logic verified in isolation; physical multi-monitor Wayland NOT verified).
- **Modes** (`dock.windowFilter`, default `all`, invalid -> `all`, no write if unchanged): `all`, `desktop`, `monitor`, `desktop-and-monitor`. Selector in Settings > Dock ("Dock Window Filter"); Dock monitor visibility settings untouched.
- **Design:** pure logic in `services/kwin/WindowFilter.js`; `WindowService.getFilteredWindowsForApp` / `getFilteredRunningAppIds` are read-only selectors. `windows`, `runningAppIds`, `windowStates` are never replaced by a filtered subset. Match by UUID (`cleanWindowId`); desktops from `windowStates` vs `KWinService.currentDesktopId`; output from `getWindowOutput` compared to the Dock surface's own `screen.name` (not `dockMonitors`).
- **Unknown metadata => window INCLUDED** (unknown current desktop, missing state, empty desktop list, unknown/disconnected output, empty screen name). On-all-desktops windows pass every desktop filter.
- **Semantics:** pinned launchers always shown; unpinned running icons only if >=1 window in the view; indicator, window count, chooser, context menu and wheel cycling all use the filtered view. Activating an app that runs globally but has 0 windows in the view does nothing (no duplicate launch); "New window" actions still launch explicitly.
- **Tests:** `tests/test_dock_window_filter.py` (node-executed pure logic + static contracts, 17 tests). Passing: also `test_dock_keyboard.TestDockKeyboardStatic`, `test_milestone_3a` (qmllint only).
- **Skipped as unsafe:** `test_dock_keyboard.TestDockKeyboardRuntime` (quickshell probe; services run `qdbus6` against the live KWin even under offscreen) and any `quickshell -p shell.qml`. `tst_dock_autohide.qml` fails to import under qmltestrunner (pre-existing, unrelated).
- **Performance:** no timers/processes added; selectors are evaluated in bindings only when windows/states/desktop/config change, O(windows) per item and early-return for `all`.
