# KWin event bridge (compiled QML plugin)

This directory contains the compiled Qt6 QML plugin behind the event-driven
Intellihide (P0 #9). `WindowService.qml` loads `BridgeHost.qml` (here) through
a `Loader` when running in a live KWin session with
`ConfigService.dockIntellihide` enabled; the plugin exports the
`KWinEventBridge` QML element that receives live window events from a resident
KWin script (`services/kwin/scripts/kwin-event-bridge.js`) over D-Bus.

## What is committed vs. built

| File | Committed | Notes |
|------|-----------|-------|
| `kwinbridge.h/.cpp`, `CMakeLists.txt` | yes | plugin sources |
| `BridgeHost.qml` | yes | Loader host used by WindowService |
| `qmldir`, `kwineventbridge.qmltypes` | yes | module registration (`optional plugin`) |
| `libkwineventbridgeplugin.so`, `libkwineventbridge.so` | **no** | built locally, see below |

The binaries are **not** committed: they are specific to the local Qt build
and CPU, and committing them would ship machine-specific artifacts that can
break on any other system. The `qmldir` registers the plugin as
`optional plugin kwineventbridgeplugin`, so a checkout without binaries is
still valid QML.

## Build requirements

- Linux, CMake >= 3.21, a C++17 compiler
- Qt6 >= 6.6 with the **Qml** and **DBus** modules and their development
  headers (e.g. `qt6-base-dev`, `qt6-declarative-dev` on Debian/Ubuntu,
  `qt6-base`/`qt6-declarative` on Arch)
- No KDE/Plasma libraries — the plugin only talks D-Bus to
  `org.kde.KWin` at runtime

## Build and install (into this checkout)

From the repository root:

```sh
cmake -S services/kwin/bridge -B /tmp/kwineventbridge-build -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/kwineventbridge-build -j4
cp /tmp/kwineventbridge-build/libkwineventbridgeplugin.so \
   /tmp/kwineventbridge-build/libkwineventbridge.so \
   services/kwin/bridge/
```

The two `.so` files **must be copied together** into this directory: the
plugin's runpath is `$ORIGIN`, so it loads its sibling backing library
`libkwineventbridge.so` from wherever the plugin itself lies.

## ABI requirements

- The plugin links `libQt6Qml.so.6`, `libQt6DBus.so.6`, `libQt6Core.so.6`
  (Qt 6 minor versions keep ABI compatibility within the Qt 6 series for
  these modules).
- The plugin must be built by the **same major Qt 6 line** the running
  Quickshell uses. A plugin built against a different Qt build (e.g. a
  distro Qt vs. a self-compiled Quickshell against another Qt) fails to load.

## Availability check and fallback

To check whether the plugin loads in your Quickshell's Qt (run from the
repository root; use your Qt 6 `qml` runtime — on Arch that is
`/usr/lib/qt6/bin/qml`, `/usr/bin/qml` may be the Qt 5 one):

```sh
cat >/tmp/bridge-check.qml <<EOF
import QtQuick
Item {
    Loader {
        source: "$(pwd)/services/kwin/bridge/BridgeHost.qml"
        onStatusChanged: {
            console.log("BRIDGE-CHECK:" + (status === Loader.Ready ? "READY" : "ERROR"));
            Qt.exit(status === Loader.Ready ? 0 : 3);
        }
    }
}
EOF
QT_FORCE_STDERR_LOGGING=1 qml -platform offscreen /tmp/bridge-check.qml
```

Exit code 0 with `BRIDGE-CHECK:READY` means the plugin loads; exit code 3
with `BRIDGE-CHECK:ERROR` (plus the Qt error message) means it does not.
This uses exactly the load path WindowService uses (`Loader` on
`BridgeHost.qml`, resolved through the same-directory `qmldir`), and is also
what `tests/test_bridge_fallback.py` asserts automatically.

At shell runtime the check is automatic: if the binaries are missing,
unloadable or ABI-incompatible, the `Loader` for `BridgeHost.qml` reports
`Loader.Error`, WindowService logs `KWin event bridge plugin unavailable;
keeping snapshot sync`, and the dock keeps using the pre-existing
snapshot-based sync path (`kdotool kwinscript` snapshots on desktop
changes). Nothing breaks — you only lose the event-driven responsiveness.
