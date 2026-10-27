# P0 #9 event bridge: design only

## Feasibility and evidence

A bridge without another daemon or polling is architecturally feasible, but
the repository does not currently supply its transport adapter. This is not
an integration result; nothing was loaded into KWin or the live shell.

The official [KWin scripting API](https://develop.kde.org/docs/plasma/kwin/api/)
documents window geometry, minimization and desktop signals, workspace
add/remove signals, and asynchronous `callDBus`. It also warns that geometry
notifications can occur during resize or only at its end, depending on mode.
Installed KWin 6.8 headers corroborate the required window signals.

Repository IPC is `modules/dock/Dock.qml`'s per-screen focus/release
`IpcHandler`. This is [Quickshell instance IPC](https://quickshell.org/docs/v0.3.0/types/Quickshell.Io/IpcHandler/),
not a D-Bus service. It cannot directly receive `callDBus`. Installed
Quickshell.Io additionally offers [SocketServer](https://quickshell.org/docs/v0.3.0/types/Quickshell.Io/SocketServer/),
but the documented KWin JavaScript globals provide no Unix socket client.
The installed KDE QML D-Bus module exposes clients/watchers, not a service
export type. Neither existing IPC path alone closes this gap.

## Minimal architecture and lifecycle

Preferred: a small native QML module inside Quickshell exports a versioned
QtDBus ingest method. A resident KWin script sends records using `callDBus`
to its unique bus name/object path. [Qt supports object export/removal](https://doc.qt.io/qt-6/qdbusconnection.html).
No additional process is required; a compiled adapter is required.

1. Start receiver, then explicitly load/run only the owned script through
   `/Scripting`. Do not use the one-shot kdotool wrapper or persist KDE settings.
2. Connect workspace events, enumerate existing windows and connect their
   signals. Publish an authoritative snapshot, including current desktop.
3. Send full window records/removals with generation and sequence numbers.
   Allow one outstanding batch; merge pending changes by UUID and drain on
   acknowledgement, without a timer. On overflow/gap invalidate obstruction
   and reload for a fresh snapshot. Never retain absent membership.
4. Replace QML state atomically and advance its revision. Keep authoritative
   events separate from the delayed app scanner, which can discard new windows
   or overwrite newer state. Use the same confirmed desktop stream for decisions.
5. Disable/reload/shutdown invalidates state, unloads the owned script and
   unregisters the endpoint. Watch KWin owner loss/return to clear/reinitialize.
   After a shell crash, script checks receiver ownership on the next event and
   disconnects if absent. Quiet-session orphan handlers can remain until an
   event or restart; restart removes only positively identified owned orphans.

Use private runtime files and per-instance identity. Accept only session-bus
calls whose unique sender matches the current KWin owner, inspected through
[QDBusContext](https://doc.qt.io/qt-6/qdbuscontext.html). Bound payloads and queues;
validate generations, sequences, UUIDs, finite geometry and strict booleans.
Export no execution/forwarding methods. This does not protect against account
owner compromise.

## Alternative and overhead estimate

Alternative: a native module inside KWin exposes Unix socket transport to a
declarative script, feeding Quickshell `SocketServer`. No daemon or polling;
private mode-0700 runtime directory, peer-credential checks, bounded frames,
generation validation and disconnect invalidation are required. This puts
native code/failure risk and ABI maintenance into the compositor.

Arithmetic estimate, not benchmark: 60 changes/s at 256 bytes/record is about
15 KiB/s payload (120/s: 30 KiB/s), plus transport headers/replies. Receiver
ownership checks add one request/reply per active batch where needed. Both
options add zero periodic idle messages and zero per-event process launches;
setup is O(window count), updates O(changed windows). CPU, memory, latency and
actual event frequency remain unmeasured.

## Unverified gates

Prove module loading/reload lifetime, installed script load/run/unload behavior,
sender identity, error callbacks, acknowledgement/backpressure, orphan cleanup,
enumeration ordering, fractional/multi-output coordinates, desktop semantics
and restart recovery. Test external move/resize/minimize/open/close plus QML
reactivity in isolated KWin Wayland. Nothing was activated or integration-tested.

The desktop fix cannot establish freshness of cached true all-desktop flags or
membership lists. The earlier uncommitted BLOCKED report remains unchanged.
