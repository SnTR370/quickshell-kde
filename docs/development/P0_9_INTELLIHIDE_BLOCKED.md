# P0 #9 Intellihide verification: BLOCKED

Verified on 2026-10-27, branch `feat/dock-intellihide`, checkpoint
`4874962`. No implementation fix, commit, or push was made.

Installed versions: KWin 6.8.0-1, Quickshell 0.3.2-1,
qt6-declarative 6.12.0-1, kdotool 0.3.0.

## Confirmed correctness blockers

- `WindowService.outputsSyncProc` obtains a one-shot KWin state snapshot.
  Its only callers are startup and the local action reconciliation timer
  (plus the public refresh wrapper). The existing 1000 ms scanner does not
  refresh geometry/state. External moves, resizes and minimization therefore
  leave cached geometry/state unchanged. External opens do not populate that
  snapshot; closes depend on the existing scanner's later pruning.
- `parseWindowOutputsJson` copies previous states and retains previous desktop
  metadata when a new item omits it. It has no freshness/confirmation marker
  for Intellihide. Missing entries in a snapshot can also remain cached until
  scanner pruning.
- Executing the actual `Intellihide.js` in Node confirms that overlapping
  windows with missing desktops, empty desktops, or an unknown current
  desktop all return `true` for obstruction. Each should return `false` under
  the requested conservative policy. Previously cached desktop membership is
  indistinguishable from current membership at this decision point.
- No Intellihide regression tests existed at the checkpoint. The existing
  filter tests intentionally use permissive desktop semantics for app listing;
  they do not validate obstruction correctness.

## Geometry notification investigation

Read-only introspection of the installed KWin `/KWin` and `/Scripting`
interfaces confirms no exported window geometry/state change signals.
`/KWin` exports `reloadConfig` and `showingDesktopChanged`, neither sufficient
for geometry synchronization. `getWindowInfo` is a query, not a subscription.

Installed `/usr/include/kwin/window.h` does declare `frameGeometryChanged`,
`desktopsChanged`, and `minimizedChanged`; `workspace.h` declares
`windowAdded` and `windowRemoved`. These are internal QObject signals usable
by a resident KWin script, not the public D-Bus notifications above.

The installed Quickshell toplevel `.qmltypes` expose state/screen changes but
no window position or size. Installed kdotool's embedded script template calls
its private D-Bus `finished` callback after execution; its executable contains
the corresponding unloadScript path. The existing one-shot command is not
a persistent event subscription. Merely connecting KWin signals inside that
command would not establish a supported transport/lifecycle into Quickshell.

No reliable event transport was established within this task's no-daemon,
no-continuous-subprocess-polling constraints. This does not prove an in-process
adapter is impossible. The next prerequisite is a verified event bridge with
snapshot ordering, disconnect/reconnect handling and cleanup, tested in an
isolated KWin session. Do not claim geometry synchronization by refreshing only
on active-window changes or local actions.

Adding the snapshot query to the existing 1000 ms timer would repeatedly launch
kdotool and load/run/unload KWin scripts, with up to a timer interval of stale
geometry plus execution time. Faster polling increases compositor/process
overhead and still permits stale positive obstruction. No such fallback was
implemented or benchmarked.

## Verification and limits

- `python3 -m unittest discover -s tests -p test_dock_window_filter.py -v`:
  27 passed. These are existing JS/static filter tests, not Intellihide or
  compositor integration evidence.
- Actual Intellihide Node probes: three conservative desktop cases reproduced
  incorrect positive obstruction. A fourth probe showed previously supplied
  membership is accepted; it cannot itself prove that membership is stale.
- `qmllint -I /usr/lib/qt6/qml services/kwin/WindowService.qml
  services/kwin/KWinService.qml modules/dock/Dock.qml`: passed without output.
- No reactive QML integration test or isolated KWin/Wayland test was completed.
  No `shell.qml` execution, KWin script loading, configuration change, package
  installation, or compositor restart was performed.
- Existing hover, focus, popup, drag, autohide and multi-monitor behavior was
  not modified and was not physically verified.

Implementation remains WIP. Findings are intentionally uncommitted because
verification has not passed the task's geometry correctness gate.
