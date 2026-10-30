.pragma library

// Pure DOCK-008 Meta+1..9 helpers (no QML/KWin deps; unit-testable under node).
//
// WindowService embeds the pinned dock applications into the resident KWin
// shortcut script (services/kwin/scripts/kwin-meta-shortcuts.js) whenever it
// is (re)loaded. The functions here derive, from ConfigService.dockPinned and
// ApplicationService metadata, the per-index match keys the script compares
// against KWin window resourceClass / resourceName / desktopFileName values.
//
// Match-key rules mirror the dock's own appId resolution (ApplicationService
// alias map + ConfigService.normalizeDockAppId ignore list):
//   - lowercase, ".desktop" suffix stripped
//   - ignored: empty/1-char, generic launchers (env, sh, flatpak, ...),
//     "window-" pseudo ids, "@@" scanner markers
//   - restricted to [a-z0-9._-] so the generated JSON is plain (no spaces,
//     slashes, quotes to escape) and safe for the sed substitution performed
//     by services/kwin/scripts/kwin-meta-shortcuts.sh

var MAX_SLOTS = 9;

var IGNORED_KEYS = [
    "env", "sh", "bash", "flatpak", "snap", "xdg-open", "gio", "gtk-launch",
    "electron", "application-x-executable"
];

var KEY_PATTERN = /^[a-z0-9._-]+$/;

function normalizeKey(raw) {
    var s = String(raw === undefined || raw === null ? "" : raw);
    return s.trim().toLowerCase().replace(/\.desktop$/, "");
}

function isIgnoredKey(key) {
    if (!key || key.length <= 1) return true;
    if (IGNORED_KEYS.indexOf(key) !== -1) return true;
    if (key.indexOf("window-") === 0 || key.indexOf("@@") === 0) return true;
    return !KEY_PATTERN.test(key);
}

// appId: raw pinned id string; app: ApplicationService app object
// ({ id, startupWMClass, execBinary, icon, aliases } shape) or null.
// Returns the ordered, deduplicated list of match keys for one dock slot.
function entryKeysForApp(appId, app) {
    var keys = [];
    var seen = {};
    function add(raw) {
        var key = normalizeKey(raw);
        if (!key || seen[key] || isIgnoredKey(key)) return;
        seen[key] = true;
        keys.push(key);
    }
    if (appId) add(appId);
    if (app) {
        if (app.id) add(app.id);
        if (app.startupWMClass) add(app.startupWMClass);
        if (app.execBinary) add(app.execBinary);
        if (app.icon) add(app.icon);
        if (app.aliases && app.aliases.length !== undefined) {
            for (var i = 0; i < app.aliases.length; i++) add(app.aliases[i]);
        }
    }
    return keys;
}

// pinnedList: ConfigService.dockPinned (array of app ids and, since DOCK-011,
// possible "stack:<id>" markers for dock stacks);
// resolveApp: function(rawId) -> app object or null (ApplicationService.getAppById).
// Returns at most MAX_SLOTS entries, one per pinned APPLICATION in order
// (stack markers are skipped: Meta+N activates the Nth app, not a stack);
// slots with no resolvable keys stay as empty arrays so dock indices remain
// stable.
function buildPinnedEntries(pinnedList, resolveApp) {
    if (!pinnedList || typeof pinnedList === "string" || pinnedList.length === undefined) {
        return [];
    }
    var out = [];
    for (var i = 0; i < pinnedList.length; i++) {
        var raw = pinnedList[i];
        if (typeof raw === "string" && raw.indexOf("stack:") === 0) continue;
        var app = (typeof resolveApp === "function" && raw) ? resolveApp(raw) : null;
        out.push(entryKeysForApp(raw, app));
        if (out.length >= MAX_SLOTS) break;
    }
    return out;
}

function buildPinnedJson(pinnedList, resolveApp) {
    return JSON.stringify(buildPinnedEntries(pinnedList, resolveApp));
}

// Reference implementation of the __PINNED_JSON__ substitution performed by
// kwin-meta-shortcuts.sh (sed). Returns "" when the template carries no
// placeholder (missing/broken template must never load silently).
function buildScriptContent(templateText, pinnedJson) {
    var template = String(templateText === undefined || templateText === null ? "" : templateText);
    if (template.indexOf("__PINNED_JSON__") === -1) return "";
    return template.replace("__PINNED_JSON__", String(pinnedJson || "[]"));
}
