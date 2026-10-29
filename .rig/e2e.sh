#!/bin/bash
# Isolated end-to-end test of the KWin event bridge (P0 #9 Intellihide).
#
# Inside a throwaway dbus session + kwin_wayland --virtual:
#   phase A: harness starts the bridge, a driven test window exercises
#            add/move/resize/minimize/unminimize/fullscreen/close, a second
#            desktop is created and switched to, and a spoofed record call
#            from a non-KWin sender must be rejected. Harness exits cleanly
#            -> owned script must be unloaded.
#   phase B: harness SIGKILLed after a snapshot -> orphan script stays loaded.
#   phase C: fresh harness start must clean the orphan, receive a fresh
#            snapshot, and unload again on clean exit.
#
# Never touches the live Plasma session: own XDG_RUNTIME_DIR/XDG_CONFIG_HOME,
# own bus, own kwin. All clients run under `timeout -k`.
set -u

REPO="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE="$REPO/services/kwin/scripts/kwin-event-bridge.js"
BRIDGE_DIR="$REPO/services/kwin/bridge"
TESTROOT=/tmp/ih-e2e
rm -rf "$TESTROOT"
mkdir -p "$TESTROOT/runtime" "$TESTROOT/config" "$TESTROOT/scripts" "$TESTROOT/logs"
chmod 700 "$TESTROOT/runtime"

PLUGIN_HASH=$(printf %s "$TEMPLATE" | sha256sum | cut -c1-8)
PLUGIN_NAME="quickshell-kwineventbridge-$PLUGIN_HASH"
BUS_NAME="org.quickshell.kwineventbridge.$PLUGIN_HASH"
export TESTROOT TEMPLATE BRIDGE_DIR PLUGIN_NAME BUS_NAME REPO

# --- driven test window ---
cat > "$TESTROOT/scripts/e2ewin.qml" <<'EOF'
import QtQuick
import QtQuick.Window
Window {
    id: win
    width: 400; height: 300; visible: true; title: "e2e-window"
    property int step: 0
    Component.onCompleted: { win.x = 100; win.y = 100; console.log("WIN-CREATED") }
    Timer {
        interval: 1500; repeat: true; running: true
        onTriggered: {
            step++;
            switch (step) {
                case 1: win.x = 50; win.y = 500; console.log("WIN-MOVE"); break;
                case 2: win.width = 900; console.log("WIN-RESIZE"); break;
                case 3: win.showMinimized(); console.log("WIN-MINIMIZE"); break;
                case 4: win.showNormal(); win.requestActivate(); console.log("WIN-RESTORE"); break;
                case 5: win.visibility = Window.FullScreen; console.log("WIN-FULLSCREEN"); break;
                case 6: console.log("WIN-CLOSE"); Qt.exit(0); break;
            }
        }
    }
}
EOF

export XDG_RUNTIME_DIR="$TESTROOT/runtime"
export XDG_CONFIG_HOME="$TESTROOT/config"
export XDG_CURRENT_DESKTOP=KDE
export KDE_FULL_SESSION=true
export QT_QPA_PLATFORM=wayland
export QT_FORCE_STDERR_LOGGING=1
unset JOURNAL_STREAM INVOCATION_ID

dbus-run-session -- bash -eu <<'INNER'
make_harness_qml() { # runtime_ms
    cat > "$TESTROOT/scripts/harness.qml" <<EOF
import QtQuick
import "file:$BRIDGE_DIR"

Item {
    KWinEventBridge {
        id: bridge
        onBatchReceived: jsonText => console.log("BATCH:" + jsonText)
        onDesynchronized: reason => console.log("DESYNC:" + reason)
        onActiveChanged: console.log("ACTIVE:" + bridge.active)
        onConnectedChanged: console.log("CONNECTED:" + bridge.connected)
    }
    Component.onCompleted: {
        console.log("HARNESS-START-RESULT:" + bridge.start("$TEMPLATE"));
    }
    Timer { interval: ${1:-12000}; running: true; onTriggered: { console.log("HARNESS-EXIT"); Qt.exit(0); } }
}
EOF
}

wait_log() { # file marker timeout
    for i in $(seq 1 "$3"); do
        grep -aq "$2" "$1" 2>/dev/null && return 0
        sleep 0.2
    done
    echo "E2E-FAIL: marker [$2] not found in $1 within $(( $3 / 5 ))s"
    return 1
}

run_harness() { # logfile runtime_ms
    make_harness_qml "$2"
    QT_QPA_PLATFORM=offscreen timeout -k 3 $(( $2 / 1000 + 8 )) \
        /usr/lib/qt6/bin/qml -platform offscreen "$TESTROOT/scripts/harness.qml" \
        > "$1" 2>&1 &
    HARN=$!
}

HARN=""
kwin_wayland --virtual --width 1280 --height 800 --no-lockscreen \
    --no-global-shortcuts --no-kactivities --socket kwine2e \
    >"$TESTROOT/logs/kwin.log" 2>&1 &
KWINPID=$!
trap 'kill $KWINPID ${HARN:-0} 2>/dev/null; pkill -P $KWINPID 2>/dev/null; true' EXIT

for i in $(seq 1 150); do [ -S "$XDG_RUNTIME_DIR/kwine2e" ] && break; sleep 0.1; done
[ -S "$XDG_RUNTIME_DIR/kwine2e" ] || { echo "E2E-FAIL: kwin socket never appeared"; exit 1; }
export WAYLAND_DISPLAY=kwine2e
for i in $(seq 1 150); do qdbus6 org.kde.KWin /KWin org.kde.KWin.activeOutputName >/dev/null 2>&1 && break; sleep 0.1; done
echo "E2E-STEP kwin-up"

echo "== phase A: bridge lifecycle + events =="
run_harness "$TESTROOT/logs/harnessA.log" 14000
wait_log "$TESTROOT/logs/harnessA.log" "HARNESS-START-RESULT:true" 100 || exit 1
sleep 0.6
echo "E2E-STEP harnessA-started"
echo "E2E-STEP scriptLoadedA=$(qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.isScriptLoaded "$PLUGIN_NAME")"

timeout -k 2 14 /usr/lib/qt6/bin/qml -platform wayland "$TESTROOT/scripts/e2ewin.qml" \
    >"$TESTROOT/logs/e2ewin.log" 2>&1 &
WINPID=$!

sleep 4.6   # window created, moved, resized, minimized
kdotool activate "$(kdotool search --name e2e-window | head -1)" 2>/dev/null || true
sleep 3.2   # restored, fullscreened, closed

# second desktop + switch
qdbus6 org.kde.KWin /VirtualDesktopManager org.kde.KWin.VirtualDesktopManager.createDesktop 1 e2e-second >/dev/null
qdbus6 org.kde.KWin /KWin org.kde.KWin.setCurrentDesktop 2 >/dev/null
DESK2=$(qdbus6 org.kde.KWin /VirtualDesktopManager org.kde.KWin.VirtualDesktopManager.current)
echo "E2E-DESK2:$DESK2"

# spoofed record call from a non-KWin sender must be rejected
SPOOF=$(qdbus6 "$BUS_NAME" /org/quickshell/kwinbridge record '{"v":1,"gen":1,"seq":1,"type":"desktop","desktop":"evil"}' 2>&1)
echo "E2E-SPOOF-REPLY:[$SPOOF]"

wait $WINPID 2>/dev/null || true
wait $HARN 2>/dev/null || true
echo "E2E-STEP harnessA-exited scriptLoadedAfterA=$(qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.isScriptLoaded "$PLUGIN_NAME")"

echo "== phase B: crash (SIGKILL) leaves an orphan =="
run_harness "$TESTROOT/logs/harnessB.log" 30000
wait_log "$TESTROOT/logs/harnessB.log" "HARNESS-START-RESULT:true" 100 || exit 1
sleep 1.0
kill -9 $HARN 2>/dev/null
sleep 0.5
echo "E2E-STEP orphanAfterCrash=$(qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.isScriptLoaded "$PLUGIN_NAME")"

echo "== phase C: restart recovery cleans the orphan =="
run_harness "$TESTROOT/logs/harnessC.log" 5000
wait_log "$TESTROOT/logs/harnessC.log" "HARNESS-START-RESULT:true" 100 || exit 1
sleep 1.5
wait $HARN 2>/dev/null || true
echo "E2E-STEP scriptLoadedAfterC=$(qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.isScriptLoaded "$PLUGIN_NAME")"

kill $KWINPID 2>/dev/null
wait $KWINPID 2>/dev/null || true
echo "E2E-DONE"
INNER
