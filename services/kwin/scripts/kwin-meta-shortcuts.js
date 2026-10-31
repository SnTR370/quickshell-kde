/*
 * Quickshell KWin Meta+1..9 dock shortcuts — resident KWin script (TEMPLATE).
 *
 * Loaded (never installed into the user's KWin script configuration) by
 * services/kwin/scripts/kwin-meta-shortcuts.sh on behalf of WindowService
 * when ConfigService.dockMetaShortcuts is enabled. KWin is the only Wayland
 * component that can own global shortcuts, so this script registers
 * Meta+1..9 through KWin's scripting API and activates or cycles the Nth
 * PINNED dock application's windows natively.
 *
 * The pinned list is embedded at load time into the PINNED constant below
 * (the placeholder token on that line is substituted by the loader): a JSON
 * array holding one entry per dock position (max 9); each entry is the array
 * of lowercase match keys (desktop-file id, resourceClass / resourceName
 * values, StartupWMClass, exec binary, icon — the same alias rules the dock
 * uses for its running indicators) of the pinned application at that index.
 * Entries may be empty (unresolvable app): their shortcut is still
 * registered so dock positions stay stable, but does nothing.
 *
 * Trigger behavior mirrors the DockItem click / wheel behavior as closely
 * as KWin's API allows:
 *   - no matching window            -> nothing (KWin scripts cannot launch
 *                                      applications; documented limitation)
 *   - active window belongs to app  -> minimize it (click "toggle")
 *   - otherwise                     -> cycle to the window after the last
 *                                      one this script activated (click
 *                                      "chooser" becomes cycling)
 *
 * Lifecycle: KWin drops transiently loaded scripts on restart (and on
 * kwin --replace). WindowService's bounded health check
 * (metaShortcutsHealthTimer) detects the loss and reloads this script
 * through services/kwin/scripts/kwin-meta-shortcuts.sh.
 */
(function () {
    "use strict";

    var PINNED = __PINNED_JSON__;
    var PREFIX = "quickshell-dock-meta-";
    var registered = [];
    var lastActivated = {}; // dock index -> internalId last activated by us

    function norm(value) {
        var s = "";
        try { s = String(value || ""); } catch (e) { return ""; }
        return s.toLowerCase().replace(/\.desktop$/, "");
    }

    function windowMatches(w, entry) {
        if (!w || !entry || entry.length === 0) return false;
        var keys = [norm(w.resourceClass), norm(w.resourceName), norm(w.desktopFileName)];
        for (var k = 0; k < keys.length; k++) {
            if (keys[k] && entry.indexOf(keys[k]) !== -1) return true;
        }
        return false;
    }

    function windowsForIndex(idx) {
        var entry = PINNED[idx];
        if (!entry || entry.length === 0) return [];
        var all = [];
        try { all = workspace.windowList() || []; } catch (e) { return []; }
        var out = [];
        for (var i = 0; i < all.length; i++) {
            var w = all[i];
            if (!w) continue;
            try {
                if (!w.normalWindow || w.deleted) continue;
            } catch (e) { continue; }
            if (windowMatches(w, entry)) out.push(w);
        }
        return out;
    }

    function trigger(idx) {
        var wins = windowsForIndex(idx);
        if (wins.length === 0) return;
        var active = null;
        try { active = workspace.activeWindow; } catch (e) {}
        if (active && windowMatches(active, PINNED[idx])) {
            if (active.minimizable !== false) {
                try { active.minimized = true; } catch (e) {}
            }
            return;
        }
        var start = 0;
        var last = lastActivated[idx];
        if (last) {
            for (var i = 0; i < wins.length; i++) {
                if (String(wins[i].internalId) === last) {
                    start = (i + 1) % wins.length;
                    break;
                }
            }
        }
        var target = wins[start];
        if (!last) {
            // Fresh cycle: prefer a non-minimized window.
            for (var j = 0; j < wins.length; j++) {
                var cand = wins[(start + j) % wins.length];
                if (!cand.minimized) { target = cand; break; }
            }
        }
        if (!target) return;
        try {
            target.minimized = false;
            workspace.activeWindow = target;
            lastActivated[idx] = String(target.internalId);
        } catch (e) {}
    }

    var slots = Math.min(9, PINNED.length);
    for (var n = 1; n <= slots; n++) {
        (function (idx) {
            var ok = false;
            try {
                ok = registerShortcut(PREFIX + (idx + 1),
                    "Quickshell Dock: Pinned Application " + (idx + 1),
                    "Meta+" + (idx + 1),
                    function () { trigger(idx); });
            } catch (e) {
                ok = false;
            }
            registered.push(ok ? 1 : 0);
        })(n - 1);
    }
    console.log("quickshell-dock-meta-shortcuts loaded slots=" + slots +
        " registered=" + registered.join(","));
})();
