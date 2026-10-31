.pragma library

// Pure merge/validation for KWinEventBridge record batches (P0 #9 Intellihide).
//
// The compiled bridge already validated the envelope (trusted sender,
// generation, sequence); everything here is side-effect free so it can run
// under node in the regression tests. Records are validated strictly:
// malformed data is skipped, never merged, and truthy values never confirm
// window state (conservative obstruction semantics, see Intellihide.js).

var UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
var DESKTOP_ID_RE = /^[a-zA-Z0-9._-]+$/;

// KWin internalId prints as "{uuid}"; scanner ids may carry a "0_" prefix.
function cleanUuid(raw) {
    if (typeof raw !== "string") return "";
    var s = raw.replace(/^0_/, "").replace(/[{}]/g, "").trim().toLowerCase();
    return UUID_RE.test(s) ? s : "";
}

function desktopIds(raw) {
    if (!Array.isArray(raw)) return null;
    var out = [];
    for (var i = 0; i < raw.length; i++) {
        if (typeof raw[i] !== "string") return null;
        var id = raw[i].trim();
        if (!id || !DESKTOP_ID_RE.test(id)) return null;
        out.push(id);
    }
    return out;
}

function rectFields(raw) {
    var out = {};
    var keys = ["x", "y", "width", "height"];
    for (var i = 0; i < keys.length; i++) {
        var k = keys[i];
        if (typeof raw[k] !== "number" || !isFinite(raw[k])) return null;
        out[k] = Math.round(raw[k]);
    }
    return out;
}

// Returns a normalized internal record, or null when the record is invalid.
function validateWindowRecord(raw) {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
    var uuid = cleanUuid(raw.uuid);
    if (!uuid) return null;
    if (typeof raw.output !== "string") return null;
    var desks = desktopIds(raw.desktops);
    if (desks === null) return null;
    var rect = rectFields(raw);
    if (rect === null) return null;
    if (typeof raw.maximizeMode !== "number" || !isFinite(raw.maximizeMode)) return null;
    var bools = ["minimized", "maximized", "fullScreen", "keepAbove", "onAllDesktops", "specialWindow"];
    for (var i = 0; i < bools.length; i++) {
        if (typeof raw[bools[i]] !== "boolean") return null;
    }
    var caps = ["minimizable", "maximizable", "fullScreenable", "closeable", "moveable", "moveableAcrossScreens"];
    var capOut = {};
    for (var c = 0; c < caps.length; c++) {
        var key = caps[c];
        if (raw[key] === undefined) { capOut[key] = true; continue; }
        if (typeof raw[key] !== "boolean") return null;
        capOut[key] = raw[key];
    }
    return {
        uuid: uuid,
        output: raw.output.trim(),
        minimized: raw.minimized === true,
        maximizeMode: Math.round(raw.maximizeMode),
        fullScreen: raw.fullScreen === true,
        keepAbove: raw.keepAbove === true,
        onAllDesktops: raw.onAllDesktops === true,
        specialWindow: raw.specialWindow === true,
        desktops: desks,
        x: rect.x, y: rect.y, width: rect.width, height: rect.height,
        minimizable: capOut.minimizable,
        maximizable: capOut.maximizable,
        fullScreenable: capOut.fullScreenable,
        closeable: capOut.closeable,
        moveable: capOut.moveable,
        moveableAcrossScreens: capOut.moveableAcrossScreens
    };
}

// Same state shape as parseWindowOutputsJson() snapshot entries.
function toState(rec) {
    return {
        minimized: rec.minimized,
        minimizable: rec.minimizable,
        maximized: ((rec.maximizeMode & 3) === 3),
        maximizeMode: rec.maximizeMode,
        maximizable: rec.maximizable,
        fullScreen: rec.fullScreen,
        fullScreenable: rec.fullScreenable,
        keepAbove: rec.keepAbove,
        keepAboveable: !rec.specialWindow,
        closeable: rec.closeable,
        moveable: rec.moveable,
        moveableAcrossScreens: rec.moveableAcrossScreens,
        onAllDesktops: rec.onAllDesktops,
        desktops: rec.desktops,
        x: rec.x, y: rec.y, width: rec.width, height: rec.height
    };
}

function validDesktopId(raw) {
    if (typeof raw !== "string") return "";
    var id = raw.trim();
    return (id && DESKTOP_ID_RE.test(id)) ? id : "";
}

// Apply one parsed payload to (states, outputs). Mutates the maps; snapshot
// replaces them atomically. Returns true when the payload was applied.
function applyPayload(states, outputs, payload) {
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) return false;
    var type = payload.type;

    if (type === "snapshot") {
        if (!Array.isArray(payload.windows)) return false;
        var nextStates = {};
        var nextOutputs = {};
        for (var i = 0; i < payload.windows.length; i++) {
            var rec = validateWindowRecord(payload.windows[i]);
            if (!rec) return false; // atomic: one bad record rejects the snapshot
            nextStates[rec.uuid] = toState(rec);
            if (rec.output) nextOutputs[rec.uuid] = rec.output;
        }
        for (var sk in states) delete states[sk];
        for (var nk in nextStates) states[nk] = nextStates[nk];
        for (var ok in outputs) delete outputs[ok];
        for (var no in nextOutputs) outputs[no] = nextOutputs[no];
        return true;
    }

    if (type === "update") {
        var rec2 = validateWindowRecord(payload.window);
        if (!rec2) return false;
        states[rec2.uuid] = toState(rec2);
        if (rec2.output) outputs[rec2.uuid] = rec2.output;
        else delete outputs[rec2.uuid];
        return true;
    }

    if (type === "remove") {
        var uuid = cleanUuid(payload.uuid);
        if (!uuid) return false;
        delete states[uuid];
        delete outputs[uuid];
        return true;
    }

    return false;
}

// payloads: array of parsed payload objects (order preserved).
// Returns { ok, states, outputs, desktopId, changed, applied, skipped }.
// states/outputs are fresh maps; the caller assigns them for QML reactivity.
function applyBatch(states, outputs, payloads) {
    if (!payloads || !Array.isArray(payloads)) return { ok: false };

    var st = {};
    var srcStates = (states && typeof states === "object") ? states : {};
    for (var k in srcStates) st[k] = srcStates[k];
    var out = {};
    var srcOutputs = (outputs && typeof outputs === "object") ? outputs : {};
    for (var o in srcOutputs) out[o] = srcOutputs[o];

    var desktopId = "";
    var applied = 0;
    var skipped = 0;
    var changed = false;

    for (var i = 0; i < payloads.length; i++) {
        var payload = payloads[i];
        if (payload && payload.type === "desktop") {
            var desk = validDesktopId(payload.desktop);
            if (desk) { desktopId = desk; applied++; }
            else skipped++;
            continue;
        }
        if (applyPayload(st, out, payload)) {
            applied++;
            changed = true;
            if (payload.type === "snapshot") {
                var snapDesk = validDesktopId(payload.desktop);
                if (snapDesk) desktopId = snapDesk;
            }
        } else {
            skipped++;
        }
    }

    return {
        ok: true,
        states: st,
        outputs: out,
        desktopId: desktopId,
        changed: changed,
        applied: applied,
        skipped: skipped
    };
}

// True when the payload list changes window membership relative to the
// pre-batch states: a remove, a snapshot, or an update for a uuid that is
// not present yet. WindowService uses this to run one debounced scanner
// pass (titles/icons/app resolution) when the event bridge reports a
// window open/close, instead of idle 1 Hz polling.
function membershipChanged(states, payloads) {
    if (!payloads || !Array.isArray(payloads)) return false;
    var known = (states && typeof states === "object") ? states : {};
    for (var i = 0; i < payloads.length; i++) {
        var p = payloads[i];
        if (!p || typeof p !== "object") continue;
        if (p.type === "remove" || p.type === "snapshot") return true;
        if (p.type === "update" && p.window && typeof p.window.uuid === "string") {
            var uuid = cleanUuid(p.window.uuid);
            if (uuid && !known[uuid]) return true;
        }
    }
    return false;
}
