#!/usr/bin/env bash
# KWin Wayland Window Toggle Helper for Quickshell
# Toggles single-window applications:
# - Active => minimize
# - Minimized => restore + focus
# - Background => focus
# Uses native KWin scripting and D-Bus APIs. Matches canonical UUID only.

TARGET_ID="$1"
[ -z "$TARGET_ID" ] && exit 0

CLEAN_ID=$(printf '%s' "$TARGET_ID" | sed 's/^0_//; s/[{}]//g' | tr '[:upper:]' '[:lower:]')
case "$CLEAN_ID" in
    ''|*[!0-9a-f-]*)
        exit 1
        ;;
esac
FORMATTED_ID="{$CLEAN_ID}"

JS_CODE="var target = \"${CLEAN_ID}\";
var wins = workspace.windowList();
for (var i = 0; i < wins.length; i++) {
    var w = wins[i];
    var wid = w.internalId.toString().replace(/[{}]/g, \"\").toLowerCase();
    if (wid === target) {
        if (w.active && !w.minimized) {
            if (w.minimizable !== false) {
                w.minimized = true;
            }
        } else {
            w.minimized = false;
            workspace.activeWindow = w;
        }
        break;
    }
}"

if command -v kdotool >/dev/null 2>&1; then
    kdotool kwinscript --inline "$JS_CODE" >/dev/null 2>&1 && exit 0
fi

RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp}"
TMP_SCRIPT="${RUNTIME_DIR}/kwin_toggle_${CLEAN_ID}_$$.js"
PLUGIN_NAME="toggle_${CLEAN_ID}_$$"

printf '%s\n' "$JS_CODE" > "$TMP_SCRIPT"

SCRIPT_ID=$(qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.loadScript "$TMP_SCRIPT" "$PLUGIN_NAME" 2>/dev/null || true)
if [ -n "$SCRIPT_ID" ] && [ "$SCRIPT_ID" -ge 0 ] 2>/dev/null; then
    qdbus6 org.kde.KWin "/Scripting/Script${SCRIPT_ID}" org.kde.kwin.Script.run 2>/dev/null || true
    sleep 0.05
    qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.unloadScript "$PLUGIN_NAME" 2>/dev/null || true
else
    # Fallback to standard WindowsRunner activation
    qdbus6 org.kde.KWin /WindowsRunner org.kde.krunner1.Run "$TARGET_ID" "" 2>/dev/null || true
fi
rm -f "$TMP_SCRIPT"
