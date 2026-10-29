/*
 * Quickshell KWin event bridge — resident KWin script (TEMPLATE).
 *
 * The compiled KWinEventBridge QML element inside the Quickshell process
 * copies this file, substitutes __BUS_NAME__ / __GENERATION__ and loads the
 * result through the public org.kde.KWin /Scripting D-Bus interface
 * (loadScript + /Scripting/Script<id> run). It is never installed into the
 * user's KWin script configuration.
 *
 * The script forwards authoritative normal-window state to the bridge:
 *   - "snapshot" on load: every existing window plus the current desktop
 *   - "update"  on windowAdded and any tracked window state change
 *     (geometry, minimize, desktops, output, fullscreen, maximize,
 *     keep-above, interactive move/resize)
 *   - "remove"  on windowRemoved
 *   - "desktop" on currentDesktopChanged
 * Payload envelope: { v: 1, gen: <generation>, seq: <counter>, type: ... }.
 *
 * If the receiver disappears (Quickshell crash), the first failed delivery
 * disconnects every handler so the script goes quiet until the bridge
 * unloads it and loads a fresh generation.
 */
(function () {
    "use strict";

    var BUS_NAME = "__BUS_NAME__";
    var OBJECT_PATH = "/org/quickshell/kwinbridge";
    var INTERFACE = "org.quickshell.kwinbridge";
    var GENERATION = __GENERATION__;
    var PROTOCOL_VERSION = 1;

    var seq = 0;
    var dead = false;
    var tracked = {};      // internalId -> window
    var connections = [];  // [signal, handler]

    function connectSignal(signal, handler) {
        if (!signal || typeof signal.connect !== "function") return;
        signal.connect(handler);
        connections.push([signal, handler]);
    }

    function send(record) {
        if (dead) return;
        record.v = PROTOCOL_VERSION;
        record.gen = GENERATION;
        record.seq = ++seq;
        // KWin 6.8 marshalling notes (verified in the isolated rig):
        //  - a trailing function argument is required, otherwise string
        //    arguments fail to marshal ("Unregistered type QJSValue")
        //  - error callbacks are never invoked, so a vanished receiver cannot
        //    be detected from here. Staleness is prevented by the bridge:
        //    generation mismatch on restart and orphan cleanup on next start.
        try {
            callDBus(BUS_NAME, OBJECT_PATH, INTERFACE, "record", JSON.stringify(record),
                function () {});
        } catch (e) {
            dead = true; // e.g. API unavailable: stop spamming
        }
    }

    // KWin 6 exposes workspace.currentDesktop as a VirtualDesktop object with
    // an .id; older versions used a plain integer. Handle both.
    function currentDesktopId() {
        try {
            var cd = workspace.currentDesktop;
            if (cd && cd.id !== undefined) return String(cd.id);
            if (cd !== null && cd !== undefined) return String(cd);
        } catch (e) {}
        return "";
    }

    function desktopIds(w) {
        var ids = [];
        try {
            var raw = w.desktops;
            if (raw && raw.length) {
                for (var i = 0; i < raw.length; i++) {
                    var d = raw[i];
                    var id = (d && d.id !== undefined) ? String(d.id)
                            : (d !== null && d !== undefined ? String(d) : "");
                    if (id) ids.push(id);
                }
            }
        } catch (e) {}
        return ids;
    }

    function windowRecord(w) {
        var x = 0, y = 0, width = 0, height = 0;
        try {
            x = Math.round(Number(w.x) || 0);
            y = Math.round(Number(w.y) || 0);
            width = Math.round(Number(w.width) || 0);
            height = Math.round(Number(w.height) || 0);
        } catch (e) {}
        var mode = 0;
        try { mode = Number(w.maximizeMode) || 0; } catch (e) {}
        var output = "";
        try { if (w.output && w.output.name) output = String(w.output.name); } catch (e) {}
        return {
            uuid: String(w.internalId),
            output: output,
            minimized: !!w.minimized,
            maximizeMode: mode,
            maximized: ((mode & 3) === 3),
            fullScreen: !!w.fullScreen,
            keepAbove: !!w.keepAbove,
            onAllDesktops: !!w.onAllDesktops,
            specialWindow: !!w.specialWindow,
            minimizable: w.minimizable !== false,
            maximizable: w.maximizable !== false,
            fullScreenable: w.fullScreenable !== false,
            closeable: w.closeable !== false,
            moveable: w.moveable !== false,
            moveableAcrossScreens: w.moveableAcrossScreens !== false,
            desktops: desktopIds(w),
            x: x, y: y, width: width, height: height
        };
    }

    function sendUpdate(w) {
        if (dead || !w) return;
        var uuid = null;
        try { uuid = String(w.internalId); } catch (e) { return; }
        if (!uuid || tracked[uuid] !== w) return;
        send({ type: "update", window: windowRecord(w) });
    }

    function watchWindow(w) {
        if (dead || !w) return false;
        var uuid = null;
        try {
            if (!w.normalWindow || w.deleted) return false;
            uuid = String(w.internalId);
        } catch (e) { return false; }
        if (!uuid || tracked[uuid]) return false;
        tracked[uuid] = w;
        connectSignal(w.frameGeometryChanged, function () { sendUpdate(w); });
        connectSignal(w.minimizedChanged, function () { sendUpdate(w); });
        connectSignal(w.desktopsChanged, function () { sendUpdate(w); });
        connectSignal(w.outputChanged, function () { sendUpdate(w); });
        connectSignal(w.fullScreenChanged, function () { sendUpdate(w); });
        connectSignal(w.maximizedChanged, function () { sendUpdate(w); });
        connectSignal(w.keepAboveChanged, function () { sendUpdate(w); });
        connectSignal(w.interactiveMoveResizeStepped, function () { sendUpdate(w); });
        return true;
    }

    connectSignal(workspace.windowAdded, function (w) {
        if (dead || !w) return;
        if (watchWindow(w)) sendUpdate(w);
    });

    connectSignal(workspace.windowRemoved, function (w) {
        if (dead || !w) return;
        var uuid = null;
        try { uuid = String(w.internalId); } catch (e) {}
        if (!uuid || !tracked[uuid]) return;
        delete tracked[uuid];
        send({ type: "remove", uuid: uuid });
    });

    connectSignal(workspace.currentDesktopChanged, function () {
        if (dead) return;
        send({ type: "desktop", desktop: currentDesktopId() });
    });

    // Initial authoritative snapshot of existing normal windows.
    var existing = [];
    try { existing = workspace.windowList() || []; } catch (e) { existing = []; }
    var records = [];
    for (var i = 0; i < existing.length; i++) {
        var w = existing[i];
        if (!w) continue;
        if (watchWindow(w)) records.push(windowRecord(w));
    }
    send({ type: "snapshot", desktop: currentDesktopId(), windows: records });
})();
