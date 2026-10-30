#!/usr/bin/env bash
# KWin 6 resident-script loader for the Quickshell Dock Meta+1..9 shortcuts
# (DOCK-008). Invoked by WindowService with argument arrays only:
#   - render <pinned-json> <out-file>  write the generated script (no KWin calls)
#   - load <pinned-json> <plugin-name> render into a private runtime dir,
#                                      unload any orphan/script under the same
#                                      stable plugin name, loadScript + run
#   - unload <plugin-name>             unloadScript + remove the runtime file
#
# The pinned JSON is produced by services/kwin/MetaShortcuts.js and is
# guaranteed to contain only [a-zA-Z0-9._-] plus JSON structure characters;
# it is defensively re-validated here because it is substituted into the
# script template with sed.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="$SCRIPT_DIR/kwin-meta-shortcuts.js"

ACTION="${1:-}"

fail() {
    echo "kwin-meta-shortcuts: $*" >&2
    exit 1
}

[ -f "$TEMPLATE" ] || fail "template missing: $TEMPLATE"

# Allowed characters: JSON structure ([ ] " ,) plus the safe key charset
# enforced by MetaShortcuts.js ([a-zA-Z0-9._-]). Everything else is rejected.
# (Validated with tr, not a grep character class: GNU grep's bracket-class
# parsing of "]"/"[", members proved unreliable across grep builds.)
validate_json() {
    [ -n "$1" ] || fail "pinned JSON is empty"
    local leftover
    leftover="$(printf '%s' "$1" | tr -d 'a-zA-Z0-9._",[]-')"
    [ -z "$leftover" ] || fail "pinned JSON contains unsafe characters"
}

validate_plugin_name() {
    [ -n "$1" ] || fail "invalid plugin name"
    local leftover
    leftover="$(printf '%s' "$1" | tr -d 'a-zA-Z0-9._-')"
    [ -z "$leftover" ] || fail "invalid plugin name"
}

render_to() { # <pinned-json> <out-file>
    validate_json "$1"
    local out_dir
    out_dir="$(dirname "$2")"
    mkdir -p "$out_dir" || fail "cannot create $out_dir"
    chmod 700 "$out_dir" 2>/dev/null || true
    sed "s|__PINNED_JSON__|$1|" "$TEMPLATE" > "$2" || fail "render failed"
    if grep -q "__PINNED_JSON__" "$2"; then
        fail "template placeholder not substituted"
    fi
    return 0
}

case "$ACTION" in
    render)
        [ $# -eq 3 ] || fail "usage: render <pinned-json> <out-file>"
        render_to "$2" "$3"
        ;;
    load)
        [ $# -eq 3 ] || fail "usage: load <pinned-json> <plugin-name>"
        validate_plugin_name "$3"
        RUNTIME_BASE="${XDG_RUNTIME_DIR:-/tmp}/quickshell-kwin-meta-shortcuts"
        SCRIPT_PATH="$RUNTIME_BASE/$3.js"
        render_to "$2" "$SCRIPT_PATH"
        # Orphan cleanup (crashed shell) + own previous generation, mirroring
        # the KWin event bridge lifecycle discipline.
        qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.unloadScript "$3" >/dev/null 2>&1 || true
        SCRIPT_ID="$(qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.loadScript "$SCRIPT_PATH" "$3" 2>/dev/null)" || SCRIPT_ID=""
        if [ -n "$SCRIPT_ID" ] && [ "$SCRIPT_ID" -ge 0 ] 2>/dev/null; then
            qdbus6 org.kde.KWin "/Scripting/Script${SCRIPT_ID}" org.kde.kwin.Script.run >/dev/null 2>&1 \
                || fail "script loaded but failed to run"
            exit 0
        fi
        fail "KWin loadScript failed (id: ${SCRIPT_ID:-none})"
        ;;
    unload)
        [ $# -eq 2 ] || fail "usage: unload <plugin-name>"
        validate_plugin_name "$2"
        qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.unloadScript "$2" >/dev/null 2>&1 || true
        rm -f "${XDG_RUNTIME_DIR:-/tmp}/quickshell-kwin-meta-shortcuts/$2.js"
        exit 0
        ;;
    *)
        fail "unknown action: ${ACTION:-<none>}"
        ;;
esac
