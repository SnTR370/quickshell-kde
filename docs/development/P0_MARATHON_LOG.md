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
