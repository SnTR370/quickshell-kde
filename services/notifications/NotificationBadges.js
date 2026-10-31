.pragma library

// Pure DOCK-009 notification-badge helpers (no QML/KWin deps; unit-testable
// under node).
//
// All state handled here derives from the shell's own freedesktop
// NotificationServer (Quickshell.Services.Notifications): every count,
// urgency flag and progress value is exact server state received over the
// native org.freedesktop.Notifications interface — never an estimate. This
// library only shapes that state and matches notifications to applications;
// the lifecycle wiring (tracked notifications, closed/hintsChanged signals,
// expire sweeper) lives in NotificationService.qml.
//
// Verified against the installed Quickshell 0.3.2 API (probe-evidenced):
//   Notification { id, tracked, appName, appIcon, summary, body, urgency,
//                  actions, transient, resident, desktopEntry, expireTimeout,
//                  hints (QVariantMap) }
//   closed(reason) reasons follow the freedesktop NotificationClosed codes:
//   1 = Expired, 2 = Dismissed, 3 = CloseRequested.

var URGENCY_CRITICAL = 2;   // freedesktop urgency level 2 ("critical")
var CLOSE_EXPIRED = 1;
var CLOSE_DISMISSED = 2;
var CLOSE_REQUESTED = 3;

// Generic freedesktop icon names that must never identify an application
// (an app whose desktop entry happens to use one would hijack unrelated
// notifications matched by icon).
var GENERIC_ICON_NAMES = [
    "dialog-information", "dialog-warning", "dialog-error", "dialog-question",
    "dialog-password", "dialog-ok", "dialog-cancel", "dialog-close",
    "preferences-system", "applications-all", "applications-other",
    "utilities-terminal", "text-x-generic", "image-x-generic",
    "audio-x-generic", "video-x-generic", "folder", "unknown"
];

// QVariant-marshalled arrays arrive as sequence objects for which
// Array.isArray() is false (see DockStacks.js). Convert anything array-like
// into a real JS array.
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

// Progress: the freedesktop "value" hint. The spec draft uses a 0..1 double
// while KDE clients send 0..100 percent — normalize both. Anything that is
// not a finite number yields null (no progress indicator; never guessed).
function normalizeProgress(hints) {
    if (!hints || typeof hints !== "object") return null;
    var raw = hints["value"];
    if (typeof raw !== "number" || !isFinite(raw)) return null;
    var v = raw > 1 ? raw / 100 : raw;
    if (v < 0) v = 0;
    if (v > 1) v = 1;
    return v;
}

// Plain snapshot of a server Notification for the active set. "now" is
// injected so node tests are deterministic. Keeps the toast/history field
// shape (summary, body, actions) and adds the badge fields (transient,
// expireTimeout, progress, desktopEntry).
function makeBadgeItem(n, nowMs) {
    var hints = (n && n.hints && typeof n.hints === "object") ? n.hints : null;
    return {
        id: n ? Number(n.id) : 0,
        raw: n ? n : null,
        appName: String((n && n.appName) || ""),
        appIcon: String((n && n.appIcon) || ""),
        desktopEntry: String((n && n.desktopEntry) || ""),
        summary: String((n && n.summary) || ""),
        body: String((n && n.body) || ""),
        urgency: Number((n && n.urgency) || 0),
        actions: (n && n.actions) ? n.actions : [],
        transient: !!(n && n.transient),
        expireTimeout: Number((n && n.expireTimeout) || 0),
        progress: normalizeProgress(hints),
        timestamp: Number(nowMs) || 0
    };
}

// Canonical dock key for a resolved app (same rule as
// DockStacks.buildDockEntries / ApplicationService.getAppById consumers).
function canonicalAppKey(app) {
    if (!app || !app.id) return "";
    return String(app.id).toLowerCase().replace(/\.desktop$/, "");
}

// Candidate identity strings for an app match, best first: the freedesktop
// desktop-entry hint, the notification icon name, then the (unreliable)
// sender display name. Absolute icon paths and generic dialog/folder icons
// are skipped — they cannot identify an application.
function matchCandidates(item) {
    var out = [];
    var de = String((item && item.desktopEntry) || "").trim().toLowerCase();
    if (de) out.push(de);
    var icon = String((item && item.appIcon) || "").trim().toLowerCase();
    if (icon && icon.indexOf("/") === -1 && GENERIC_ICON_NAMES.indexOf(icon.replace(/\.desktop$/, "")) === -1) {
        out.push(icon);
    }
    var name = String((item && item.appName) || "").trim().toLowerCase();
    if (name) out.push(name);
    return out;
}

// Resolve a notification to a canonical app key through the caller's
// resolver (ApplicationService.getAppById). Returns "" when unmatched —
// unmatched notifications never badge a dock icon (never guess).
function matchAppKey(item, resolveApp) {
    if (typeof resolveApp !== "function") return "";
    var cands = matchCandidates(item);
    for (var i = 0; i < cands.length; i++) {
        var app = resolveApp(cands[i]);
        if (app && app.id) return canonicalAppKey(app);
    }
    return "";
}

// Active-set upsert by notification id. Freedesktop replaces_id semantics:
// a replacement updates the existing entry in place — it never adds a
// second count. New notifications go to the front (newest-first order).
function upsertActive(list, item) {
    if (!item) return toArray(list);
    var next = toArray(list).slice();
    for (var i = 0; i < next.length; i++) {
        if (next[i] && next[i].id === item.id) {
            next[i] = item;
            return next;
        }
    }
    next.unshift(item);
    return next;
}

function removeActive(list, id) {
    var nid = Number(id);
    var next = [];
    var raw = toArray(list);
    for (var i = 0; i < raw.length; i++) {
        if (raw[i] && raw[i].id !== nid) next.push(raw[i]);
    }
    return next;
}

// Per-app badge state from the active set. Transient notifications never
// produce badges (freedesktop: transient = do not persist; the shell
// expires them once their toast is hidden). Progress keeps
// the most recently updated value among an app's active progress
// notifications (timestamp comparison, replacement-aware). Returns a plain
// map: canonical app key -> { count, critical, progress }.
function buildBadges(active, resolveApp) {
    var badges = {};
    var latest = {};
    var list = toArray(active);
    for (var i = 0; i < list.length; i++) {
        var item = list[i];
        if (!item || item.transient) continue;
        var key = matchAppKey(item, resolveApp);
        if (!key) continue;
        var b = badges[key];
        if (!b) {
            b = { count: 0, critical: false, progress: null };
            badges[key] = b;
        }
        b.count += 1;
        if (item.urgency === URGENCY_CRITICAL) b.critical = true;
        if (typeof item.progress === "number" &&
            (latest[key] === undefined || Number(item.timestamp) >= latest[key])) {
            latest[key] = Number(item.timestamp);
            b.progress = item.progress;
        }
    }
    return badges;
}

function badgeForApp(badges, appKey) {
    if (!badges || !appKey) return null;
    var b = badges[String(appKey)];
    return b ? b : null;
}

// Aggregate member badge state for an apps stack: summed count and OR'ed
// critical flag. Progress is deliberately NOT aggregated — one merged ring
// value for several applications would be arbitrary, so stacks show none.
function aggregateStackBadge(badges, appKeys) {
    var keys = toArray(appKeys);
    var agg = null;
    for (var i = 0; i < keys.length; i++) {
        var b = badgeForApp(badges, keys[i]);
        if (!b) continue;
        if (!agg) agg = { count: 0, critical: false, progress: null };
        agg.count += b.count;
        if (b.critical) agg.critical = true;
    }
    return agg;
}

// Ids of active notifications matched to one app (dismiss-on-attention).
function activeIdsForApp(active, appKey, resolveApp) {
    var out = [];
    if (!appKey) return out;
    var list = toArray(active);
    for (var i = 0; i < list.length; i++) {
        var item = list[i];
        if (!item || item.transient) continue;
        if (matchAppKey(item, resolveApp) === String(appKey)) out.push(item.id);
    }
    return out;
}

// Ids of active notifications whose client-supplied expireTimeout has
// elapsed. Only positive timeouts count: the freedesktop spec uses -1 for
// "never expire", and 0 (use server default) is this shell's documented
// "persist until attended" default.
function expiredIds(active, nowMs) {
    var out = [];
    var list = toArray(active);
    var now = Number(nowMs);
    for (var i = 0; i < list.length; i++) {
        var item = list[i];
        if (!item || !item.raw) continue;
        var t = Number(item.expireTimeout);
        if (!(t > 0)) continue;
        if (now - Number(item.timestamp) >= t) out.push(item.id);
    }
    return out;
}
