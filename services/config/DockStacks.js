.pragma library

// Pure DOCK-011 stack helpers (no QML/KWin deps; unit-testable under node).
//
// Stacks are dock entries that group applications ("apps") or expose a
// filesystem folder ("folder"). They live in ConfigService.dockStacks as
// plain objects:
//   { id, type: "apps"|"folder", title, icon?, path?, appIds: [...] }
// and are referenced from the pinned list (ConfigService.dockPinned) through
// marker strings "stack:<id>", so stacks interleave with pinned apps in the
// dock row and reuse the existing reorder / persistence machinery.
//
// Folder stacks never read the filesystem here: listing is done by the UI
// (Qt.labs.folderlistmodel, watched live by Qt) and opening by
// ApplicationService.openPaths (gio, argv array). This library only shapes
// configuration data.

var ID_PATTERN = /^[a-z0-9][a-z0-9._-]{0,63}$/;
var MAX_TITLE_LEN = 64;
var MAX_STACK_APPS = 24;
var STACK_TYPES = ["apps", "folder"];

// QVariant-marshaled arrays arrive as sequence objects for which
// Array.isArray() is false (see ConfigService._jsArray). Convert anything
// array-like (or scalar-wrapped) into a real JS array.
function toArray(value) {
    if (value === null || value === undefined) return [];
    if (Array.isArray(value)) return value;
    if (typeof value === "object" && typeof value.length === "number") {
        var arr = [];
        for (var i = 0; i < value.length; i++) arr.push(value[i]);
        return arr;
    }
    return [];
}

function isValidStackId(id) {
    return typeof id === "string" && ID_PATTERN.test(id);
}

function isStackEntry(raw) {
    if (typeof raw !== "string" || raw.indexOf("stack:") !== 0) return false;
    return isValidStackId(raw.slice(6));
}

function stackIdFromEntry(raw) {
    return isStackEntry(raw) ? raw.slice(6) : "";
}

function entryForStackId(id) {
    return isValidStackId(id) ? ("stack:" + id) : "";
}

// First free "st<N>" id (N >= 1) not present in existing stacks/ids.
function nextStackId(existing) {
    var taken = {};
    var list = toArray(existing);
    for (var i = 0; i < list.length; i++) {
        if (list[i] && list[i].id) taken[String(list[i].id)] = true;
    }
    var n = 1;
    while (taken["st" + n]) n++;
    return "st" + n;
}

function sanitizeTitle(title, fallback) {
    var t = String(title === undefined || title === null ? "" : title).trim();
    if (t.length === 0) t = String(fallback || "").trim();
    if (t.length === 0) return "";
    if (t.length > MAX_TITLE_LEN) t = t.slice(0, MAX_TITLE_LEN);
    return t;
}

// Folder paths must be absolute, single-line and free of ".." traversal.
// Returns the cleaned path or "" when invalid. Existence is deliberately
// NOT checked here (config must stay loadable across machines/snapshots);
// the folder popup handles a missing directory as a visible empty state.
function sanitizePath(path) {
    var p = String(path === undefined || path === null ? "" : path).trim();
    if (p.length === 0 || p.charAt(0) !== "/") return "";
    if (p.indexOf("\n") !== -1 || p.indexOf("\r") !== -1) return "";
    if (p.split("/").indexOf("..") !== -1) return "";
    // Collapse duplicate slashes (but keep the leading one).
    var parts = p.split("/");
    var clean = [];
    for (var i = 0; i < parts.length; i++) {
        if (parts[i].length > 0 || i === 0) clean.push(parts[i]);
    }
    p = clean.join("/") || "/";
    if (p.length > 4096) return "";
    return p;
}

// appIds: raw list; normalizeId: ConfigService.normalizeDockAppId-style
// function (required; keeps the ignore-list rules in one place). Dedupes
// case-insensitively and caps the member count (popup stays usable).
function sanitizeStackAppIds(list, normalizeId) {
    if (typeof normalizeId !== "function") return [];
    var out = [];
    var seen = {};
    var raw = toArray(list);
    for (var i = 0; i < raw.length; i++) {
        var norm = normalizeId(raw[i]);
        if (!norm) continue;
        var key = String(norm).toLowerCase();
        if (seen[key]) continue;
        seen[key] = true;
        out.push(norm);
        if (out.length >= MAX_STACK_APPS) break;
    }
    return out;
}

// Validate and normalize a list of stack objects. Invalid entries (bad id,
// unknown type, non-absolute folder path) are dropped; duplicate ids keep
// the first occurrence. Returns a NEW array of plain objects with real JS
// arrays inside (safe against QVariant marshaling).
function sanitizeStacks(list, normalizeId) {
    var raw = toArray(list);
    var out = [];
    var seenIds = {};
    for (var i = 0; i < raw.length; i++) {
        var s = raw[i];
        if (!s || typeof s !== "object") continue;
        var id = String(s.id === undefined || s.id === null ? "" : s.id).trim();
        if (!isValidStackId(id) || seenIds[id]) continue;
        var type = String(s.type === undefined || s.type === null ? "" : s.type).trim().toLowerCase();
        if (STACK_TYPES.indexOf(type) === -1) continue;
        var title = sanitizeTitle(s.title, type === "folder" ? "Folder" : "Stack");
        if (!title) continue;
        var stack = {
            id: id,
            type: type,
            title: title,
            appIds: []
        };
        var icon = String(s.icon === undefined || s.icon === null ? "" : s.icon).trim();
        if (icon.length > 0 && icon.length <= 128) stack.icon = icon;
        if (type === "folder") {
            var path = sanitizePath(s.path);
            if (!path) continue;
            stack.path = path;
        } else {
            stack.appIds = sanitizeStackAppIds(s.appIds, normalizeId);
        }
        seenIds[id] = true;
        out.push(stack);
    }
    return out;
}

function findStack(stacks, id) {
    if (!isValidStackId(id)) return null;
    var list = toArray(stacks);
    for (var i = 0; i < list.length; i++) {
        if (list[i] && list[i].id === id) return list[i];
    }
    return null;
}

// The merged, ordered dock entry model for the pinned section:
// [{ kind: "app", key, appId }, { kind: "stack", key, stack }].
// - app entries mirror ApplicationService.pinnedApps semantics: only ids
//   resolvable through resolveApp are kept, deduped by canonical app id,
//   and the RAW pinned id is preserved (resolvePinnedKey compatibility).
// - stack markers are kept only while the stack still exists, deduped by id.
function buildDockEntries(pinnedList, stacks, resolveApp) {
    var raw = toArray(pinnedList);
    var out = [];
    var seenCanon = {};
    var seenStacks = {};
    for (var i = 0; i < raw.length; i++) {
        var entry = raw[i];
        if (isStackEntry(entry)) {
            var sid = entry.slice(6);
            if (seenStacks[sid]) continue;
            var stack = findStack(stacks, sid);
            if (!stack) continue;
            seenStacks[sid] = true;
            out.push({ kind: "stack", key: entry, stack: stack });
            continue;
        }
        if (!entry) continue;
        var app = (typeof resolveApp === "function") ? resolveApp(entry) : null;
        if (!app) continue;
        var canon = String(app.id || entry).toLowerCase().replace(/\.desktop$/, "");
        if (canon.length > 0 && seenCanon[canon]) continue;
        if (canon.length > 0) seenCanon[canon] = true;
        out.push({ kind: "app", key: canon, appId: entry });
    }
    return out;
}

// Fallback icon for a stack (explicit icon wins).
function stackIcon(stack) {
    if (!stack) return "application-x-executable";
    if (stack.icon && String(stack.icon).length > 0) return String(stack.icon);
    return stack.type === "folder" ? "folder" : "applications-all";
}
