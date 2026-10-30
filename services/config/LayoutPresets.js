.pragma library

// Pure layout-preset logic (no QML deps; unit-testable under node).
//
// A layout preset is a ready-to-use STARTING POINT for the two shell
// surfaces (Bar and Dock): surface geometry (edge, floating mode, offset,
// struts, sizes) and the Bar module slots. It only ever touches these
// layout keys — pinned applications, monitor selection, theme, opacity,
// blur, tray policies, notifications and dock window filtering are user
// preferences that a preset must preserve. Presets never restrict later
// customization.
//
// Lockout safety: the Quickshell Settings window is reachable from the
// Dock's built-in Settings button and from the Bar's Control Center. A
// layout that disables the Dock must therefore keep the Bar enabled with
// both the "launcher" and "controlcenter" modules placed in its slots.

var EDGES = ["top", "bottom", "left", "right"];

// Value clamps mirror the ConfigService setter validation.
var LIMITS = {
    edgeOffset: { min: 0, max: 64 },
    height: { min: 24, max: 120 },
    iconSize: { min: 20, max: 128 }
};

// Layout keys a preset is allowed to change. Everything else is preserved.
var BAR_KEYS = ["enabled", "floating", "edge", "edgeOffset", "reserveSpace",
                "height", "left", "center", "right"];
var DOCK_KEYS = ["enabled", "floating", "edge", "edgeOffset", "reserveSpace",
                 "iconSize", "autoHide", "intellihide"];
var SLOT_KEYS = ["left", "center", "right"];

var PRESETS = [
    {
        id: "everyday",
        name: "Everyday",
        icon: "preferences-desktop",
        description: "Balanced top Bar and bottom Dock with the full module set — the do-everything layout.",
        bar: {
            enabled: true, floating: true, edge: "top", edgeOffset: 8,
            reserveSpace: false, height: 32,
            left: ["launcher", "workspaces"],
            center: ["clock"],
            right: ["media", "tray", "network", "battery", "audio",
                    "brightness", "controlcenter", "power"]
        },
        dock: {
            enabled: true, floating: true, edge: "bottom", edgeOffset: 8,
            reserveSpace: false, iconSize: 44, autoHide: false, intellihide: false
        }
    },
    {
        id: "classic",
        name: "Classic",
        icon: "preferences-desktop-panel",
        description: "Traditional full-width bottom panel with reserved space, like a classic KDE or Windows taskbar. The Dock is turned off.",
        bar: {
            enabled: true, floating: false, edge: "bottom", edgeOffset: 0,
            reserveSpace: true, height: 38,
            left: ["launcher", "workspaces", "media"],
            center: [],
            right: ["clock", "tray", "network", "battery", "audio",
                    "brightness", "controlcenter", "power"]
        },
        dock: {
            enabled: false, floating: false, edge: "bottom", edgeOffset: 0,
            reserveSpace: false, iconSize: 40, autoHide: false, intellihide: false
        }
    },
    {
        id: "minimal",
        name: "Minimal",
        icon: "preferences-desktop-icons",
        description: "Compact Bar with essential modules plus a small auto-hiding Dock — maximum screen space.",
        bar: {
            enabled: true, floating: true, edge: "top", edgeOffset: 6,
            reserveSpace: false, height: 26,
            left: ["launcher"],
            center: ["clock"],
            right: ["audio", "controlcenter", "power"]
        },
        dock: {
            enabled: true, floating: true, edge: "bottom", edgeOffset: 6,
            reserveSpace: false, iconSize: 36, autoHide: true, intellihide: false
        }
    }
];

function getPreset(presetId) {
    if (typeof presetId !== "string") return null;
    for (var i = 0; i < PRESETS.length; i++) {
        if (PRESETS[i].id === presetId) return PRESETS[i];
    }
    return null;
}

function getPresetIds() {
    const ids = [];
    for (var i = 0; i < PRESETS.length; i++) ids.push(PRESETS[i].id);
    return ids;
}

// Keep only known module ids, preserving order, dropping duplicates.
function sanitizeSlots(slotArray, validModuleIds) {
    if (!Array.isArray(slotArray)) return [];
    const result = [];
    for (var i = 0; i < slotArray.length; i++) {
        const id = slotArray[i];
        if (typeof id === "string" && validModuleIds.indexOf(id) !== -1 &&
                result.indexOf(id) === -1) {
            result.push(id);
        }
    }
    return result;
}

// Materialize the concrete target layout of a preset against the current
// registry (unknown module ids are dropped, never fatal).
function buildTargetLayout(preset, validModuleIds) {
    if (!preset || !preset.bar || !preset.dock) return null;
    const bar = {};
    for (var i = 0; i < BAR_KEYS.length; i++) {
        const k = BAR_KEYS[i];
        bar[k] = SLOT_KEYS.indexOf(k) !== -1
            ? sanitizeSlots(preset.bar[k], validModuleIds)
            : preset.bar[k];
    }
    const dock = {};
    for (var j = 0; j < DOCK_KEYS.length; j++) {
        dock[DOCK_KEYS[j]] = preset.dock[DOCK_KEYS[j]];
    }
    return { bar: bar, dock: dock };
}

// Reject any layout that could brick the shell or lock the user out of
// Settings. Returns { valid: bool, reason: string }.
function validateLayout(layout, validModuleIds) {
    if (!layout || !layout.bar || !layout.dock) {
        return { valid: false, reason: "Layout must define bar and dock sections" };
    }
    const sections = [["bar", layout.bar, BAR_KEYS], ["dock", layout.dock, DOCK_KEYS]];
    for (var s = 0; s < sections.length; s++) {
        const name = sections[s][0], sec = sections[s][1], keys = sections[s][2];
        for (var i = 0; i < keys.length; i++) {
            const k = keys[i], v = sec[k];
            if (v === undefined || v === null) {
                return { valid: false, reason: name + "." + k + " is missing" };
            }
            if (SLOT_KEYS.indexOf(k) !== -1) {
                if (!Array.isArray(v)) {
                    return { valid: false, reason: name + "." + k + " must be an array" };
                }
                for (var m = 0; m < v.length; m++) {
                    if (typeof v[m] !== "string" || validModuleIds.indexOf(v[m]) === -1) {
                        return { valid: false, reason: "Unknown module '" + v[m] + "' in " + name + "." + k };
                    }
                }
                continue;
            }
            if (k === "edge") {
                if (EDGES.indexOf(v) === -1) {
                    return { valid: false, reason: "Invalid " + name + " edge '" + v + "'" };
                }
                continue;
            }
            if (typeof v === "boolean") continue; // enabled/floating/reserveSpace/autoHide/intellihide
            if (typeof v === "number" && Number.isFinite(v)) {
                const lim = LIMITS[k];
                if (lim && (v < lim.min || v > lim.max)) {
                    return { valid: false, reason: name + "." + k + " out of range: " + v };
                }
                continue;
            }
            return { valid: false, reason: name + "." + k + " has invalid type" };
        }
    }

    // No module may appear in more than one Bar slot.
    const seen = {};
    for (var c = 0; c < SLOT_KEYS.length; c++) {
        const slot = layout.bar[SLOT_KEYS[c]];
        for (var d = 0; d < slot.length; d++) {
            if (seen[slot[d]]) {
                return { valid: false, reason: "Module '" + slot[d] + "' appears in multiple Bar slots" };
            }
            seen[slot[d]] = true;
        }
    }

    // Surface lockout: at least one surface must stay enabled.
    if (!layout.bar.enabled && !layout.dock.enabled) {
        return { valid: false, reason: "Bar and Dock cannot both be disabled" };
    }
    // Settings/launcher lockout: without the Dock (its built-in buttons are
    // the fallback entry points) the Bar must keep both modules reachable.
    if (!layout.dock.enabled) {
        if (!layout.bar.enabled) {
            return { valid: false, reason: "Dock disabled requires the Bar to stay enabled" };
        }
        const allSlots = layout.bar.left.concat(layout.bar.center, layout.bar.right);
        if (allSlots.indexOf("launcher") === -1) {
            return { valid: false, reason: "Dock disabled requires the launcher module in the Bar" };
        }
        if (allSlots.indexOf("controlcenter") === -1) {
            return { valid: false, reason: "Dock disabled requires the control center module in the Bar" };
        }
    }
    return { valid: true, reason: "" };
}

function arraysEqual(a, b) {
    if (!Array.isArray(a) || !Array.isArray(b)) return false;
    if (a.length !== b.length) return false;
    for (var i = 0; i < a.length; i++) {
        if (a[i] !== b[i]) return false;
    }
    return true;
}

// Keys whose values differ between two layouts: [{ section, key, from, to }].
// Only layout keys are compared, so unrelated user settings can never leak
// into a preset diff.
function diffLayouts(current, target) {
    const changes = [];
    if (!current || !target) return changes;
    const sections = [["bar", BAR_KEYS], ["dock", DOCK_KEYS]];
    for (var s = 0; s < sections.length; s++) {
        const name = sections[s][0], keys = sections[s][1];
        const cur = current[name] || {}, tgt = target[name] || {};
        for (var i = 0; i < keys.length; i++) {
            const k = keys[i];
            const a = cur[k], b = tgt[k];
            if (Array.isArray(a) || Array.isArray(b)) {
                if (!arraysEqual(a, b)) {
                    changes.push({ section: name, key: k, from: a, to: b });
                }
            } else if (a !== b) {
                changes.push({ section: name, key: k, from: a, to: b });
            }
        }
    }
    return changes;
}

function formatValue(key, value, moduleNameMap) {
    if (Array.isArray(value)) {
        if (value.length === 0) return "None";
        const names = [];
        for (var i = 0; i < value.length; i++) {
            const id = value[i];
            names.push((moduleNameMap && moduleNameMap[id]) ? moduleNameMap[id] : id);
        }
        return names.join(" · ");
    }
    switch (key) {
        case "floating": return value ? "Floating island" : "Attached panel";
        case "edge": return String(value).charAt(0).toUpperCase() + String(value).slice(1);
        case "edgeOffset": return value + " px";
        case "height": return value + " px";
        case "iconSize": return value + " px";
        case "reserveSpace": return value ? "Reserved" : "Zero strut";
        default: return value ? "On" : "Off";
    }
}

var LABELS = {
    "bar.enabled": "Bar enabled",
    "bar.floating": "Bar surface mode",
    "bar.edge": "Bar screen edge",
    "bar.edgeOffset": "Bar edge offset",
    "bar.reserveSpace": "Bar screen space",
    "bar.height": "Bar thickness",
    "bar.left": "Bar left modules",
    "bar.center": "Bar center modules",
    "bar.right": "Bar right modules",
    "dock.enabled": "Dock enabled",
    "dock.floating": "Dock surface mode",
    "dock.edge": "Dock screen edge",
    "dock.edgeOffset": "Dock edge offset",
    "dock.reserveSpace": "Dock screen space",
    "dock.iconSize": "Dock icon size",
    "dock.autoHide": "Dock auto-hide",
    "dock.intellihide": "Dock intellihide"
};

// Human-readable preview of what a preset will change:
// [{ section, key, label, fromText, toText }] — ready for the Settings UI.
function describeChanges(current, target, moduleNameMap) {
    const raw = diffLayouts(current, target);
    const described = [];
    for (var i = 0; i < raw.length; i++) {
        const c = raw[i];
        described.push({
            section: c.section,
            key: c.key,
            label: LABELS[c.section + "." + c.key] || (c.section + "." + c.key),
            fromText: formatValue(c.key, c.from, moduleNameMap),
            toText: formatValue(c.key, c.to, moduleNameMap)
        });
    }
    return described;
}

// True when the current layout already equals the preset's target layout.
function matchesPreset(current, preset, validModuleIds) {
    const target = buildTargetLayout(preset, validModuleIds);
    if (!target) return false;
    return diffLayouts(current, target).length === 0;
}
