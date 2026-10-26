.pragma library

// Pure Dock window-filter logic (no QML/KWin deps; unit-testable under node).
//
// Modes: "all" (default) | "desktop" | "monitor" | "desktop-and-monitor".
// Conservative fallback: any UNKNOWN metadata means the window is INCLUDED
// (never hide a window because we failed to learn where it lives):
//   - current desktop unknown            -> desktop condition passes
//   - window state missing / no desktops -> desktop condition passes
//   - window on all desktops             -> desktop condition passes
//   - window output unknown/disconnected -> monitor condition passes
//   - Dock screen name empty             -> monitor condition passes

var MODES = ["all", "desktop", "monitor", "desktop-and-monitor"];

function normalizeMode(m) {
    return (typeof m === "string" && MODES.indexOf(m) !== -1) ? m : "all";
}

function matchesDesktop(state, currentDesktopId) {
    if (!currentDesktopId) return true;
    if (!state) return true;
    if (state.onAllDesktops) return true;
    var d = state.desktops;
    if (!Array.isArray(d) || d.length === 0) return true;
    return d.indexOf(currentDesktopId) !== -1;
}

function matchesMonitor(outputName, screenName) {
    if (!screenName) return true;
    if (!outputName) return true;
    return outputName === screenName;
}

// ctx: { mode, screenName, currentDesktopId, states: {cleanId: state},
//        cleanId: fn(id)->string, outputOf: fn(id)->string }
function windowVisible(win, ctx) {
    var mode = normalizeMode(ctx.mode);
    if (mode === "all") return true;
    var clean = ctx.cleanId(win.id);
    if (mode === "desktop" || mode === "desktop-and-monitor") {
        var st = ctx.states ? ctx.states[clean] : null;
        if (!matchesDesktop(st, ctx.currentDesktopId)) return false;
    }
    if (mode === "monitor" || mode === "desktop-and-monitor") {
        if (!matchesMonitor(ctx.outputOf(win.id), ctx.screenName)) return false;
    }
    return true;
}

function filterWindows(windows, ctx) {
    if (normalizeMode(ctx.mode) === "all") return windows;
    var out = [];
    for (var i = 0; i < windows.length; i++) {
        if (windowVisible(windows[i], ctx)) out.push(windows[i]);
    }
    return out;
}
