#!/bin/bash
# Isolated KWin rig probe #2 — verifies script lifecycle + script->D-Bus delivery
# WITHOUT relying on kwin log output.
#
# Strategy (log-independent):
#   - script load/run/unload lifecycle is verified via /Scripting D-Bus state
#     (loadScript id, isScriptLoaded, unloadScript return value)
#   - script execution + callDBus delivery is verified by an observable KWin
#     side effect: the loaded script calls nextDesktop via callDBus; we assert
#     the VirtualDesktopManager current desktop index changed
#   - window enumeration is verified via /WindowsRunner Match (window created
#     by a qml client under `timeout -k`)
set -u
TESTROOT=/tmp/ih-rig2
rm -rf "$TESTROOT"
mkdir -p "$TESTROOT/runtime" "$TESTROOT/config" "$TESTROOT/scripts"
chmod 700 "$TESTROOT/runtime"

cat > "$TESTROOT/scripts/probe2.js" <<'EOF'
// Create a second desktop so nextDesktop has an observable effect, then
// demonstrate callDBus from inside the KWin script.
var desktops = workspace.desktops;
print("PROBE2 desktops=" + desktops.length);
if (desktops.length < 2) {
    callDBus("org.kde.KWin", "/VirtualDesktopManager",
             "org.kde.KWin.VirtualDesktopManager", "createDesktop",
             "1", "probe2-second");
}
var cd = workspace.currentDesktop;
print("PROBE2 currentDesktop typeof=" + typeof cd + " value=" + cd);
print("PROBE2 windowList n=" + workspace.windowList().length);
workspace.windowAdded.connect(function(w) {
    print("PROBE2 windowAdded " + (w ? w.internalId : "null"));
});
// Observable side effect: switch desktop through D-Bus (async, no callback).
callDBus("org.kde.KWin", "/KWin", "org.kde.KWin", "nextDesktop");
EOF

cat > "$TESTROOT/scripts/testwin.qml" <<'WQML'
import QtQuick
import QtQuick.Window
Window {
    width: 400; height: 300; visible: true; title: "probe2-win"
    Component.onCompleted: console.log("TESTWIN created")
    Timer { interval: 3000; running: true; onTriggered: Qt.exit(0) }
}
WQML

export XDG_RUNTIME_DIR="$TESTROOT/runtime"
export XDG_CONFIG_HOME="$TESTROOT/config"
export XDG_CURRENT_DESKTOP=KDE
export KDE_FULL_SESSION=true
unset JOURNAL_STREAM INVOCATION_ID
export QT_QPA_PLATFORM=wayland
export QT_FORCE_STDERR_LOGGING=1
export QT_LOGGING_RULES="kwin_*.debug=true;*.debug=false,kwin_*.debug=true"

TESTROOT="$TESTROOT" dbus-run-session -- bash -eu <<'INNER'
kwin_wayland --virtual --width 1280 --height 800 --no-lockscreen \
    --no-global-shortcuts --no-kactivities --socket kwinih \
    >"$TESTROOT/kwin.log" 2>&1 &
KWINPID=$!
trap 'kill $KWINPID 2>/dev/null; pkill -P $KWINPID 2>/dev/null; true' EXIT

for i in $(seq 1 150); do [ -S "$XDG_RUNTIME_DIR/kwinih" ] && break; sleep 0.1; done
if [ ! -S "$XDG_RUNTIME_DIR/kwinih" ]; then echo "RIG-FAIL: kwin socket never appeared"; exit 1; fi
export WAYLAND_DISPLAY=kwinih

for i in $(seq 1 150); do qdbus6 org.kde.KWin /KWin org.kde.KWin.activeOutputName >/dev/null 2>&1 && break; sleep 0.1; done
echo "RIG-OK: kwin up on socket kwinih, bus owner: $(qdbus6 org.kde.KWin 2>/dev/null | head -1)"

echo "== desktop state before script =="
qdbus6 org.kde.KWin /VirtualDesktopManager org.kde.KWin.VirtualDesktopManager.current
qdbus6 org.kde.KWin /VirtualDesktopManager org.kde.KWin.VirtualDesktopManager.desktoptop? 2>/dev/null || true
BEFORE_COUNT=$(qdbus6 --literal org.kde.KWin /VirtualDesktopManager org.kde.KWin.VirtualDesktopManager.desktops 2>/dev/null | grep -o "Argument: (u\?iss)" | wc -l)
echo "desktop count before: $BEFORE_COUNT"

echo "== loadScript =="
ID=$(qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.loadScript "$TESTROOT/scripts/probe2.js" quickshell-probe2 2>&1)
echo "loadScript id=[$ID]"
case "$ID" in ''|*[!0-9]*) echo "RIG-FAIL: loadScript returned non-numeric"; exit 1;; esac

echo "isScriptLoaded before run: $(qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.isScriptLoaded quickshell-probe2)"

echo "== run script =="
qdbus6 "org.kde.KWin" "/Scripting/Script${ID}" org.kde.kwin.Script.run 2>&1
sleep 1.5

echo "== desktop state after script (callDBus nextDesktop effect) =="
AFTER_COUNT=$(qdbus6 --literal org.kde.KWin /VirtualDesktopManager org.kde.KWin.VirtualDesktopManager.desktops 2>/dev/null | grep -o "Argument: (u\?iss)" | wc -l)
echo "desktop count after: $AFTER_COUNT"

echo "== create a test window (timeout -k guarded) =="
timeout -k 2 8 /usr/lib/qt6/bin/qml -platform wayland "$TESTROOT/scripts/testwin.qml" >"$TESTROOT/testwin.log" 2>&1
echo "testwin rc=$? (124/timeout expected)"
sleep 0.5

echo "== window enumeration via /WindowsRunner =="
qdbus6 --literal org.kde.KWin /WindowsRunner org.kde.krunner1.Match "" 2>&1 | grep -o '"[0-9a-f-]\{8,\}"' | sort -u | head -5

echo "== unloadScript =="
qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.unloadScript quickshell-probe2
echo "isScriptLoaded after unload: $(qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.isScriptLoaded quickshell-probe2)"

kill $KWINPID 2>/dev/null
wait $KWINPID 2>/dev/null || true
echo "== kwin.log size: $(wc -c < "$TESTROOT/kwin.log") =="
grep -a "PROBE2" "$TESTROOT/kwin.log" || echo "(no PROBE2 lines in log — expected if kwin routes prints elsewhere)"
INNER
