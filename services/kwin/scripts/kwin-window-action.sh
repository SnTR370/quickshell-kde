#!/usr/bin/env bash
# KWin 6 Wayland Native Window Action Helper for Quickshell
# Performs per-window actions by immutable KWin internalId UUID:
#   - activate <window_uuid>
#   - close <window_uuid>
#   - minimize <window_uuid>
#   - unminimize <window_uuid>
#   - toggle-minimize <window_uuid>
#   - maximize <window_uuid>
#   - unmaximize <window_uuid>
#   - toggle-maximize <window_uuid>
#   - fullscreen <window_uuid> [true|false]
#   - toggle-fullscreen <window_uuid>
#   - keep-above <window_uuid> [true|false]
#   - toggle-keep-above <window_uuid>
#   - move-output <window_uuid> <output_name>
#   - move-desktop <window_uuid> <desktop_id_or_all>

ACTION="$1"
TARGET_ID="$2"
TARGET_ARG="$3"

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
    minimize)
        JS_CODE="var target = \"${FORMATTED_ID}\";
var wins = workspace.windowList();
for (var i = 0; i < wins.length; i++) {
    var w = wins[i];
    if (w.internalId.toString().toLowerCase() === target) {
        if (w.minimizable !== false && !w.minimized) {
            w.minimized = true;
        }
        break;
    }
}"
        run_kwin_js "$JS_CODE" "minimize"
        ;;
    unminimize)
        JS_CODE="var target = \"${FORMATTED_ID}\";
var wins = workspace.windowList();
for (var i = 0; i < wins.length; i++) {
    var w = wins[i];
    if (w.internalId.toString().toLowerCase() === target) {
        if (w.minimized) {
            w.minimized = false;
            workspace.activeWindow = w;
        }
        break;
    }
}"
        run_kwin_js "$JS_CODE" "unminimize"
        ;;
    toggle-minimize)
        JS_CODE="var target = \"${FORMATTED_ID}\";
var wins = workspace.windowList();
for (var i = 0; i < wins.length; i++) {
    var w = wins[i];
    if (w.internalId.toString().toLowerCase() === target) {
        if (w.minimized) {
            w.minimized = false;
            workspace.activeWindow = w;
        } else if (w.minimizable !== false) {
            w.minimized = true;
        }
        break;
    }
}"
        run_kwin_js "$JS_CODE" "toggle_min"
        ;;
    maximize)
        JS_CODE="var target = \"${FORMATTED_ID}\";
var wins = workspace.windowList();
for (var i = 0; i < wins.length; i++) {
    var w = wins[i];
    if (w.internalId.toString().toLowerCase() === target) {
        if (w.maximizable !== false) {
            w.setMaximize(true, true);
        }
        break;
    }
}"
        run_kwin_js "$JS_CODE" "maximize"
        ;;
    unmaximize)
        JS_CODE="var target = \"${FORMATTED_ID}\";
var wins = workspace.windowList();
for (var i = 0; i < wins.length; i++) {
    var w = wins[i];
    if (w.internalId.toString().toLowerCase() === target) {
        if (w.maximizable !== false) {
            w.setMaximize(false, false);
        }
        break;
    }
}"
        run_kwin_js "$JS_CODE" "unmaximize"
        ;;
    toggle-maximize)
        JS_CODE="var target = \"${FORMATTED_ID}\";
var wins = workspace.windowList();
for (var i = 0; i < wins.length; i++) {
    var w = wins[i];
    if (w.internalId.toString().toLowerCase() === target) {
        if (w.maximizable !== false) {
            var isMax = ((w.maximizeMode & 1) !== 0 && (w.maximizeMode & 2) !== 0);
            w.setMaximize(!isMax, !isMax);
        }
        break;
    }
}"
        run_kwin_js "$JS_CODE" "toggle_max"
        ;;
    fullscreen|toggle-fullscreen)
        FS_MODE="toggle"
        if [ "$ACTION" = "fullscreen" ]; then
            case "$TARGET_ARG" in
                true|1) FS_MODE="true" ;;
                false|0) FS_MODE="false" ;;
                '') FS_MODE="toggle" ;;
                *) exit 1 ;;
            esac
        fi
        JS_CODE="var target = \"${FORMATTED_ID}\";
var mode = \"${FS_MODE}\";
var wins = workspace.windowList();
for (var i = 0; i < wins.length; i++) {
    var w = wins[i];
    if (w.internalId.toString().toLowerCase() === target) {
        if (w.fullScreenable !== false) {
            if (mode === \"true\") {
                w.fullScreen = true;
            } else if (mode === \"false\") {
                w.fullScreen = false;
            } else {
                w.fullScreen = !w.fullScreen;
            }
        }
        break;
    }
}"
        run_kwin_js "$JS_CODE" "fullscreen"
        ;;
    keep-above|toggle-keep-above)
        KA_MODE="toggle"
        if [ "$ACTION" = "keep-above" ]; then
            case "$TARGET_ARG" in
                true|1) KA_MODE="true" ;;
                false|0) KA_MODE="false" ;;
                '') KA_MODE="toggle" ;;
                *) exit 1 ;;
            esac
        fi
        JS_CODE="var target = \"${FORMATTED_ID}\";
var mode = \"${KA_MODE}\";
var wins = workspace.windowList();
for (var i = 0; i < wins.length; i++) {
    var w = wins[i];
    if (w.internalId.toString().toLowerCase() === target) {
        if (!w.specialWindow) {
            if (mode === \"true\") {
                w.keepAbove = true;
            } else if (mode === \"false\") {
                w.keepAbove = false;
            } else {
                w.keepAbove = !w.keepAbove;
            }
        }
        break;
    }
}"
        run_kwin_js "$JS_CODE" "keep_above"
        ;;
    move-output)
        case "$TARGET_ARG" in
            ''|*[!a-zA-Z0-9._-]*)
                exit 1
                ;;
        esac
        JS_CODE="var target = \"${FORMATTED_ID}\";
var outName = \"${TARGET_ARG}\";
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
    move-desktop)
        case "$TARGET_ARG" in
            ''|*[!a-zA-Z0-9._-]*)
                exit 1
                ;;
        esac
        JS_CODE="var target = \"${FORMATTED_ID}\";
var deskTarget = \"${TARGET_ARG}\";
var wins = workspace.windowList();
for (var i = 0; i < wins.length; i++) {
    var w = wins[i];
    if (w.internalId.toString().toLowerCase() === target) {
        if (!w.specialWindow) {
            if (deskTarget === \"all\") {
                w.onAllDesktops = true;
            } else {
                var targetDesk = null;
                for (var d = 0; d < workspace.desktops.length; d++) {
                    var vd = workspace.desktops[d];
                    if (vd.id.toString() === deskTarget || String(vd.x11DesktopNumber) === deskTarget) {
                        targetDesk = vd;
                        break;
                    }
                }
                if (targetDesk !== null) {
                    w.onAllDesktops = false;
                    w.desktops = [targetDesk];
                }
            }
        }
        break;
    }
}"
        run_kwin_js "$JS_CODE" "move_desktop"
        ;;
    *)
        exit 1
        ;;
esac
