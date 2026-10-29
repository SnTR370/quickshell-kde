#!/bin/bash
set -u
TESTROOT=/tmp/ih-rig
rm -rf "$TESTROOT"; mkdir -p "$TESTROOT/runtime"; chmod 700 "$TESTROOT/runtime"
dbus-run-session -- bash -c '
set -u
export XDG_RUNTIME_DIR="'"$TESTROOT"'/runtime"
unset JOURNAL_STREAM INVOCATION_ID
export QT_LOGGING_RULES="kwin_*.debug=true;*.debug=false"
kwin_wayland --virtual --width 1280 --height 800 --no-lockscreen --no-global-shortcuts --no-kactivities --socket kwinih >"'"$TESTROOT"'/kwin.log" 2>&1 &
KWINPID=$!
for i in $(seq 1 20); do
  sleep 0.5
  SOCK="$(ls -1 "$XDG_RUNTIME_DIR" 2>/dev/null | tr "\n" " ")"
  echo "t=$((i*5))00ms runtime=[$SOCK]"
done
echo "--- kwin alive?"; kill -0 $KWINPID && echo yes || echo no
echo "--- sockets on system mentioning kwinih:"; ss -x 2>/dev/null | grep -i kwinih || echo none
kill $KWINPID 2>/dev/null; sleep 1
echo "--- kwin.log first 60 lines:"
head -60 '"$TESTROOT"'/kwin.log
echo "--- kwin.log size: $(wc -c < '"$TESTROOT"'/kwin.log)"
'
