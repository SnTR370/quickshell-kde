#!/usr/bin/env bash
# KWin 6 Wayland Native Window Action Helper for Quickshell
# Performs per-window actions by immutable KWin internalId UUID:
#   - activate <window_uuid>
#   - close <window_uuid>
#   - move-output <window_uuid> <output_name>

ACTION="$1"
TARGET_ID="$2"
TARGET_OUTPUT="$3"

[ -z "$ACTION" ] || [ -z "$TARGET_ID" ] && exit 0

CLEAN_ID=$(printf '%s' "$TARGET_ID" | sed 's/^0_//; s/[{}]//g' | tr '[:upper:]' '[:lower:]')
case "$CLEAN_ID" in
    ''|*[!0-9a-f-]*)
        exit 1
        ;;
esac
FORMATTED_ID="{$CLEAN_ID}"

run_kwin_js() {
    local js_code="$1"
    local tag="$2"
    if command -v kdotool >/dev/null 2>&1; then
        kdotool kwinscript --inline "$js_code" >/dev/null 2>&1 && return 0
    fi
    local runtime_dir="${XDG_RUNTIME_DIR:-/tmp}"
    local tmp_script="${runtime_dir}/kwin_${tag}_${CLEAN_ID}_$$.js"
    local plugin_name="qs_${tag}_${CLEAN_ID}_$$"
    printf '%s\n' "$js_code" > "$tmp_script"
    local script_id
    script_id=$(qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.loadScript "$tmp_script" "$plugin_name" 2>/dev/null || true)
    if [ -n "$script_id" ] && [ "$script_id" -ge 0 ] 2>/dev/null; then
        qdbus6 org.kde.KWin "/Scripting/Script${script_id}" org.kde.kwin.Script.run 2>/dev/null || true
        sleep 0.05
        qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.unloadScript "$plugin_name" 2>/dev/null || true
    fi
    rm -f "$tmp_script"
}

case "$ACTION" in
    activate)
        JS_CODE="var target = \"${FORMATTED_ID}\";
var wins = workspace.windowList();
for (var i = 0; i < wins.length; i++) {
    var w = wins[i];
    if (w.internalId.toString().toLowerCase() === target) {
        w.minimized = false;
        workspace.activeWindow = w;
        break;
    }
}"
        run_kwin_js "$JS_CODE" "activate" || qdbus6 org.kde.KWin /WindowsRunner org.kde.krunner1.Run "$TARGET_ID" "" >/dev/null 2>&1 || true
        ;;
    close)
        JS_CODE="var target = \"${FORMATTED_ID}\";
var wins = workspace.windowList();
for (var i = 0; i < wins.length; i++) {
    var w = wins[i];
    if (w.internalId.toString().toLowerCase() === target) {
        if (w.closeable) {
            w.closeWindow();
        }
        break;
    }
}"
        run_kwin_js "$JS_CODE" "close"
        ;;
    move-output)
        case "$TARGET_OUTPUT" in
            ''|*[!a-zA-Z0-9._-]*)
                exit 1
                ;;
        esac
        JS_CODE="var target = \"${FORMATTED_ID}\";
var outName = \"${TARGET_OUTPUT}\";
var targetScreen = null;
for (var s = 0; s < workspace.screens.length; s++) {
    if (workspace.screens[s].name === outName) {
        targetScreen = workspace.screens[s];
        break;
    }
}
if (targetScreen !== null) {
    var wins = workspace.windowList();
    for (var i = 0; i < wins.length; i++) {
        var w = wins[i];
        if (w.internalId.toString().toLowerCase() === target) {
            if (w.moveableAcrossScreens && w.output !== targetScreen) {
                workspace.sendClientToScreen(w, targetScreen);
            }
            break;
        }
    }
}"
        run_kwin_js "$JS_CODE" "move"
        ;;
    *)
        exit 1
        ;;
esac
