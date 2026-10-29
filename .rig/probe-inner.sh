#!/bin/bash
# Inner script: runs INSIDE dbus-run-session with an isolated environment.
# Env expected: TESTROOT
set -u
: "${TESTROOT:?}"
export XDG_RUNTIME_DIR="$TESTROOT/runtime"
export XDG_CONFIG_HOME="$TESTROOT/config"
export XDG_CURRENT_DESKTOP=KDE
export KDE_FULL_SESSION=true
unset JOURNAL_STREAM INVOCATION_ID
export QT_QPA_PLATFORM=wayland

kwin_wayland --virtual --width 1280 --height 800 --no-lockscreen \
    --no-global-shortcuts --no-kactivities --socket kwinih \
    >"$TESTROOT/kwin.log" 2>&1 &
KWINPID=$!
trap 'kill $KWINPID 2>/dev/null; pkill -P $KWINPID 2>/dev/null' EXIT

for i in $(seq 1 150); do [ -S "$XDG_RUNTIME_DIR/kwinih" ] && break; sleep 0.1; done
if [ ! -S "$XDG_RUNTIME_DIR/kwinih" ]; then echo "FAIL: kwin socket never appeared"; exit 1; fi
export WAYLAND_DISPLAY=kwinih

for i in $(seq 1 150); do qdbus6 org.kde.KWin /KWin org.kde.KWin.activeOutputName >/dev/null 2>&1 && break; sleep 0.1; done
echo "== kwin up; scripting interface =="
qdbus6 org.kde.KWin /Scripting 2>&1 | head -12

echo "== loadScript =="
ID=$(qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.loadScript "$TESTROOT/scripts/probe1.js" quickshell-probe 2>&1)
echo "loadScript returned: [$ID]"

echo "== script object introspect =="
qdbus6 "org.kde.KWin" "/Scripting/Script${ID}" 2>&1 | head -15

echo "== run script =="
qdbus6 "org.kde.KWin" "/Scripting/Script${ID}" org.kde.kwin.Script.run 2>&1
sleep 1

echo "== open a test window =="
cat > "$TESTROOT/scripts/testwin.qml" <<'WQML'
import QtQuick
import QtQuick.Window
Window {
    width: 400; height: 300; visible: true; title: "probe-win"
    Component.onCompleted: console.log("TESTWIN created")
    Timer { interval: 2500; running: true; onTriggered: Qt.exit(0) }
}
WQML
timeout 6 /usr/lib/qt6/bin/qml -platform wayland "$TESTROOT/scripts/testwin.qml" >"$TESTROOT/testwin.log" 2>&1
echo "testwin rc=$?"

sleep 1
echo "== unload script =="
qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.unloadScript quickshell-probe 2>&1
sleep 0.5
kill $KWINPID 2>/dev/null
wait 2>/dev/null

echo "== kwin log: PROBE lines =="
grep -a "PROBE" "$TESTROOT/kwin.log" || echo "NO PROBE OUTPUT"
echo "== kwin log tail =="
tail -5 "$TESTROOT/kwin.log"
