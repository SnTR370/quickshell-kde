.pragma library

// Pure Dock Intellihide logic (no QML/KWin deps; unit-testable under node).
// All rects are global logical compositor coordinates {x,y,width,height}
// (same space for KWin window geometry and Quickshell ShellScreen x/y/width/height).
// Window GEOMETRY overlap only; this is NOT true visual stacking/occlusion.
// Conservative: missing/invalid metadata never causes a hide.

function finiteRect(r) {
    return !!r && isFinite(r.x) && isFinite(r.y) && isFinite(r.width) && isFinite(r.height)
        && r.width > 0 && r.height > 0;
}

// Revealed (would-be) footprint of the dock surface, independent of any slide transform.
// A single-edge-anchored layer surface is centered along the cross axis.
function dockFootprint(screen, edge, surfW, surfH, offset) {
    if (!finiteRect(screen) || !(surfW > 0) || !(surfH > 0)) return null;
    var off = offset > 0 ? offset : 0;
    var w = Math.min(surfW, screen.width), h = Math.min(surfH, screen.height);
    if (edge === "top") return { x: screen.x + (screen.width - w) / 2, y: screen.y + off, width: w, height: h };
    if (edge === "left") return { x: screen.x + off, y: screen.y + (screen.height - h) / 2, width: w, height: h };
    if (edge === "right") return { x: screen.x + screen.width - off - w, y: screen.y + (screen.height - h) / 2, width: w, height: h };
    return { x: screen.x + (screen.width - w) / 2, y: screen.y + screen.height - off - h, width: w, height: h };
}

function intersects(a, b) {
    return a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;
}

function onCurrentDesktop(st, currentDesktopId) {
    if (st.onAllDesktops === true) return true;
    if (typeof currentDesktopId !== "string" || currentDesktopId.trim().length === 0) return false;
    var d = st.desktops;
    if (!Array.isArray(d) || d.length === 0) return false;
    return d.indexOf(currentDesktopId) !== -1;
}

// states: array of window states {minimized,onAllDesktops,desktops,x,y,width,height}
function isObstructed(footprint, states, currentDesktopId) {
    if (!finiteRect(footprint) || !Array.isArray(states)) return false;
    for (var i = 0; i < states.length; i++) {
        var st = states[i];
        if (!st || st.minimized) continue;
        if (!onCurrentDesktop(st, currentDesktopId)) continue;
        if (!finiteRect(st)) continue;
        if (intersects(footprint, st)) return true;
    }
    return false;
}

// Config: intellihide wins over legacy autoHide when both set.
function hideCapable(autoHide, intellihide) { return !!(autoHide || intellihide); }

// Reveal decision. interacting = hover/popup/drag/keyboard/edge-reveal.
function isRevealed(autoHide, intellihide, obstructed, interacting) {
    if (!hideCapable(autoHide, intellihide)) return true;
    if (interacting) return true;
    if (intellihide) return !obstructed;
    return false;
}
