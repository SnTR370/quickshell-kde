#!/bin/bash
# Probe KWin 6.8 callDBus marshalling/callback behavior against the real bridge.
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE="$REPO/services/kwin/scripts/kwin-event-bridge.js"
BRIDGE_DIR="$REPO/services/kwin/bridge"
TESTROOT=/tmp/ih-probe3
rm -rf "$TESTROOT"; mkdir -p "$TESTROOT/runtime" "$TESTROOT/config" "$TESTROOT/scripts" "$TESTROOT/logs"
chmod 700 "$TESTROOT/runtime"

cat > "$TESTROOT/scripts/harness.qml" <<EOF
import QtQuick
import "file:$BRIDGE_DIR"
Item {
    KWinEventBridge {
        id: bridge
        onBatchReceived: jsonText => console.log("BATCH:" + jsonText)
        onDesynchronized: reason => console.log("DESYNC:" + reason)
    }
    Component.onCompleted: console.log("HARNESS-START-RESULT:" + bridge.start("$TEMPLATE"))
    Timer { interval: 20000; running: true; onTriggered: Qt.exit(0) }
}
EOF

# probe: 1) no-callback send to real bridge
#         2) one-callback send to dead service
#         3) two-callback send to dead service
#         4) one-callback send to real bridge
cat > "$TESTROOT/scripts/probe3.js" <<'EOF'
print("PROBE3 start");
var BUS = "__BUS__";
var PAYLOAD = JSON.stringify({v:1,gen:999999,seq:1,type:"desktop",desktop:"probe3-marker"});
// 1: no callback, real bridge (gen mismatch is fine - we only test delivery)
try { callDBus(BUS, "/org/quickshell/kwinbridge", "org.quickshell.kwinbridge", "record", PAYLOAD); print("PROBE3 sent-nocallback"); } catch (e) { print("PROBE3 nocallback ERR " + e); }
// 2: one callback, dead service
try { callDBus("org.dead.service", "/", "", "foo", "x", function () { print("PROBE3 one-cb SUCCESS-cb"); }); print("PROBE3 sent-onecb"); } catch (e) { print("PROBE3 onecb ERR " + e); }
// 3: two callbacks, dead service
try { callDBus("org.dead.service", "/", "", "foo", "x", function () { print("PROBE3 two-cb SUCCESS-cb"); }, function (e) { print("PROBE3 two-cb ERROR-cb " + e); }); print("PROBE3 sent-twocb"); } catch (e) { print("PROBE3 twocb ERR " + e); }
// 4: one callback, real bridge
try { callDBus(BUS, "/org/quickshell/kwinbridge", "org.quickshell.kwinbridge", "record", PAYLOAD, function () { print("PROBE3 realbridge SUCCESS-cb"); }); print("PROBE3 sent-realcb"); } catch (e) { print("PROBE3 realcb ERR " + e); }
print("PROBE3 done");
EOF

PLUGIN_HASH=$(printf %s "$TEMPLATE" | sha256sum | cut -c1-8)
BUS_NAME="org.quickshell.kwineventbridge.$PLUGIN_HASH"
sed -i "s/__BUS__/$BUS_NAME/" "$TESTROOT/scripts/probe3.js"
export TESTROOT
export XDG_RUNTIME_DIR="$TESTROOT/runtime" XDG_CONFIG_HOME="$TESTROOT/config"
export XDG_CURRENT_DESKTOP=KDE KDE_FULL_SESSION=true QT_QPA_PLATFORM=wayland QT_FORCE_STDERR_LOGGING=1
unset JOURNAL_STREAM INVOCATION_ID

TESTROOT="$TESTROOT" BUS_NAME="$BUS_NAME" dbus-run-session -- bash -eu <<'INNER'
kwin_wayland --virtual --width 1280 --height 800 --no-lockscreen --no-global-shortcuts --no-kactivities --socket kwinp3 >"$TESTROOT/logs/kwin.log" 2>&1 &
KWINPID=$!
trap 'kill $KWINPID 2>/dev/null; pkill -P $KWINPID 2>/dev/null; true' EXIT
for i in $(seq 1 150); do [ -S "$XDG_RUNTIME_DIR/kwinp3" ] && break; sleep 0.1; done
export WAYLAND_DISPLAY=kwinp3
for i in $(seq 1 150); do qdbus6 org.kde.KWin /KWin org.kde.KWin.activeOutputName >/dev/null 2>&1 && break; sleep 0.1; done

QT_QPA_PLATFORM=offscreen timeout -k 3 20 /usr/lib/qt6/bin/qml -platform offscreen "$TESTROOT/scripts/harness.qml" >"$TESTROOT/logs/harness.log" 2>&1 &
HARN=$!
for i in $(seq 1 100); do grep -aq "HARNESS-START-RESULT:true" "$TESTROOT/logs/harness.log" 2>/dev/null && break; sleep 0.2; done
sleep 0.5

ID=$(qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.loadScript "$TESTROOT/scripts/probe3.js" probe3)
qdbus6 "org.kde.KWin" "/Scripting/Script${ID}" org.kde.kwin.Script.run
sleep 3
kill $HARN 2>/dev/null
wait $HARN 2>/dev/null || true
echo "=== PROBE3 prints from kwin.log:"
grep -a "PROBE3" "$TESTROOT/logs/kwin.log" || echo "(none)"
echo "=== harness batches:"
grep -a "BATCH:\|DESYNC" "$TESTROOT/logs/harness.log" || echo "(none)"
kill $KWINPID 2>/dev/null; wait $KWINPID 2>/dev/null || true
INNER
