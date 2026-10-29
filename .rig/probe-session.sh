#!/bin/bash
# Outer: fresh isolated dirs + fresh dbus session, then run probe-inner.sh.
set -u
TESTROOT=/tmp/ih-rig
rm -rf "$TESTROOT"
mkdir -p "$TESTROOT/runtime" "$TESTROOT/config" "$TESTROOT/scripts"
chmod 700 "$TESTROOT/runtime"

RIGDIR="$(cd "$(dirname "$0")" && pwd)"

cat > "$TESTROOT/scripts/probe1.js" <<'EOF'
print("PROBE hello");
print("PROBE currentDesktop typeof=" + typeof workspace.currentDesktop);
print("PROBE currentDesktop=" + workspace.currentDesktop);
try { print("PROBE currentDesktopId=" + workspace.currentDesktopId); } catch (e) { print("PROBE currentDesktopId ERR " + e); }
try { print("PROBE currentDesktop.toString=" + workspace.currentDesktop.toString()); } catch (e) { print("PROBE toString ERR " + e); }
try { print("PROBE desktops=" + JSON.stringify(workspace.desktops.map(function(d){ return d ? (d.id + "/" + d.name) : String(d); }))); } catch (e) { print("PROBE desktops ERR " + e); }
print("PROBE windowList n=" + workspace.windowList().length);
var wins = workspace.windowList();
for (var i = 0; i < wins.length; i++) {
  var w = wins[i];
  print("PROBE win internalId=" + w.internalId + " normalWindow=" + w.normalWindow + " output=" + (w.output ? w.output.name : "none"));
}
workspace.windowAdded.connect(function(w) { print("PROBE windowAdded " + w.internalId); });
workspace.windowRemoved.connect(function(w) { print("PROBE windowRemoved " + w.internalId); });
try {
  workspace.currentDesktopChanged.connect(function(a, b) { print("PROBE currentDesktopChanged args=" + a + "," + b + " cur=" + workspace.currentDesktop); });
} catch (e) { print("PROBE connect ERR " + e); }
print("PROBE done-initial");
EOF

TESTROOT="$TESTROOT" dbus-run-session -- bash "$RIGDIR/probe-inner.sh"
