.pragma library

// Pure DOCK-012 per-monitor dock profile helpers (no QML/KWin deps;
// unit-testable under node).
//
// A monitor profile is a set of overrides for the per-screen dock layout
// and appearance keys, keyed by output name (e.g. "DP-1", "HDMI-A-0"):
//   ConfigService.dockMonitorProfiles = {
//     "DP-1":     { edge: "left", iconSize: 32 },
//     "HDMI-A-0": { autoHide: true }
//   }
// The global dock settings remain the defaults; a missing or invalid
// override always falls back to the global value. Pinned applications,
// stacks, monitor selection, magnification, hide/reveal delays and the
// window filter stay global by design: Meta+1..9 shortcuts (DOCK-008) and
// the "stack:<id>" markers (DOCK-011) address one merged dock row, which
// per-monitor pinned lists could not keep coherent.
//
// Sanitization mirrors the global clamping rules in ConfigService
// (setDockEdgeOffset / setDockIconSize / ...) so a stored profile can never
// push a value outside the range the global setter accepts. Existence of
// the output is deliberately NOT checked here: profiles must survive
// hotplug (a stored override re-applies when the output returns) and stay
// loadable across machines and config snapshots.

var SCREEN_NAME_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;
var MAX_PROFILES = 16;
var EDGES = ["top", "bottom", "left", "right"];

// The dock keys a monitor profile may override. Everything else stays
// global (see the block comment above).
var OVERRIDABLE_KEYS = ["edge", "floating", "edgeOffset", "iconSize", "autoHide", "intellihide"];

function isValidScreenName(name) {
    return typeof name === "string" && SCREEN_NAME_PATTERN.test(name);
}

function clampInt(value, min, max) {
    if (typeof value !== "number" || !isFinite(value)) return undefined;
    return Math.max(min, Math.min(max, Math.trunc(value)));
}

// Validate and normalize one override value. Returns the sanitized value,
// or undefined when the key is not overridable / the value is invalid
// (invalid overrides are dropped, never coerced to a default).
function sanitizeValue(key, value) {
    if (key === "edge") {
        var e = String(value === undefined || value === null ? "" : value).trim().toLowerCase();
        return EDGES.indexOf(e) !== -1 ? e : undefined;
    }
    if (key === "floating" || key === "autoHide" || key === "intellihide") {
        return typeof value === "boolean" ? value : undefined;
    }
    if (key === "edgeOffset") return clampInt(value, 0, 64);
    if (key === "iconSize") return clampInt(value, 20, 128);
    return undefined;
}

// Sanitize one screen's override set. Returns a plain object with only
// valid overridable keys, or null when nothing usable remains.
function sanitizeOverrides(raw) {
    if (!raw || typeof raw !== "object") return null;
    var out = null;
    for (var k in raw) {
        if (OVERRIDABLE_KEYS.indexOf(k) === -1) continue;
        var v = sanitizeValue(k, raw[k]);
        if (v === undefined) continue;
        if (!out) out = {};
        out[k] = v;
    }
    return out;
}

function countProfiles(profiles) {
    var n = 0;
    for (var k in profiles) n++;
    return n;
}

// Shallow copy with each profile's overrides re-sanitized (defensive
// against QVariant-marshaled objects arriving through signal hops).
function copyProfiles(profiles) {
    var out = {};
    if (!profiles || typeof profiles !== "object") return out;
    for (var name in profiles) {
        var clean = sanitizeOverrides(profiles[name]);
        if (clean) out[name] = clean;
    }
    return out;
}

// Validate and normalize the whole profiles map. Invalid screen names and
// profiles without any usable override are dropped; duplicate keys cannot
// occur in a JSON object (last write wins by construction). The count is
// capped so a corrupted file cannot grow the map unboundedly.
function sanitizeProfiles(raw) {
    if (!raw || typeof raw !== "object") return {};
    var out = {};
    var count = 0;
    for (var name in raw) {
        if (count >= MAX_PROFILES) break;
        var n = String(name === undefined || name === null ? "" : name).trim();
        if (!isValidScreenName(n)) continue;
        var ov = sanitizeOverrides(raw[name]);
        if (!ov) continue;
        out[n] = ov;
        count++;
    }
    return out;
}

// A screen's stored overrides (re-sanitized), or null when the screen has
// no profile. Never mutates the input.
function getProfile(profiles, screenName) {
    if (!profiles || typeof profiles !== "object" || !isValidScreenName(screenName)) return null;
    return sanitizeOverrides(profiles[screenName]);
}

// Effective value for one key: the screen's override when present and
// valid, otherwise the global value.
function resolveKey(profiles, screenName, key, globalValue) {
    var p = getProfile(profiles, screenName);
    if (!p) return globalValue;
    var v = sanitizeValue(key, p[key]);
    return (v === undefined) ? globalValue : v;
}

// Merged effective profile for one screen: every overridable key resolved
// against the globals object ({ edge, floating, edgeOffset, iconSize,
// autoHide, intellihide }).
function effectiveProfile(profiles, screenName, globals) {
    var g = (globals && typeof globals === "object") ? globals : {};
    var out = {};
    for (var i = 0; i < OVERRIDABLE_KEYS.length; i++) {
        var k = OVERRIDABLE_KEYS[i];
        out[k] = resolveKey(profiles, screenName, k, g[k]);
    }
    return out;
}

// Pure setter: a NEW profiles object with one override applied. Invalid
// screen name or value leaves the profiles unchanged; the input object is
// never mutated (QVariant-signal gotcha: callers reassign the result).
function setOverride(profiles, screenName, key, value) {
    var base = copyProfiles(profiles);
    if (!isValidScreenName(screenName)) return base;
    var v = sanitizeValue(key, value);
    if (v === undefined) return base;
    if (!base[screenName] && countProfiles(base) >= MAX_PROFILES) return base;
    var ov = {};
    if (base[screenName]) {
        for (var k in base[screenName]) ov[k] = base[screenName][k];
    }
    ov[key] = v;
    base[screenName] = ov;
    return base;
}

// Pure removal of one override key (drops the whole profile when it
// becomes empty).
function clearOverride(profiles, screenName, key) {
    var base = copyProfiles(profiles);
    if (!isValidScreenName(screenName) || !base[screenName]) return base;
    var ov = {};
    for (var k in base[screenName]) {
        if (k !== key) ov[k] = base[screenName][k];
    }
    if (countProfiles(ov) === 0) {
        delete base[screenName];
    } else {
        base[screenName] = ov;
    }
    return base;
}

// Pure removal of a screen's whole profile.
function clearProfile(profiles, screenName) {
    var base = copyProfiles(profiles);
    if (isValidScreenName(screenName) && base[screenName] !== undefined) {
        delete base[screenName];
    }
    return base;
}

// True when any stored profile sets `key` to `value` (e.g. intellihide on
// for one output while the global toggle is off — window tracking must
// then stay active).
function anyProfileKey(profiles, key, value) {
    if (!profiles || typeof profiles !== "object") return false;
    for (var name in profiles) {
        var clean = sanitizeOverrides(profiles[name]);
        if (clean && clean[key] === value) return true;
    }
    return false;
}
