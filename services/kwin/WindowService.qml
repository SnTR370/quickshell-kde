pragma Singleton
import "WindowFilter.js" as WindowFilter
import "BridgeRecords.js" as BridgeRecords
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import "../applications"
import "../config"
import "../core/Log.js" as Log
import "."

Singleton {
    id: root

    property var windows: []
    property var runningAppIds: []
    property int windowCount: 0
    property string activeWindowId: ""

    signal windowsUpdated()

    // Watch desktop changes from KWinService to refresh window state
    Connections {
        target: KWinService
        function onDesktopChanged() {
            root.refreshWindows();
        }
        function onDesktopsUpdated() {
            root.refreshWindows();
        }
        function onActiveWindowChanged(windowId) {
            if (root.outputsOverride === null) {
                root.handleActiveWindowOutput(windowId);
            }
        }
    }

    // Refresh window resolution when application scanner finishes
    Connections {
        target: ApplicationService
        function onApplicationsChanged() {
            ApplicationService.rebuildAliasMap();
            if (root.lastScannerRawText && root.lastScannerRawText.length > 0) {
                root.parseWindowsOutput(root.lastScannerRawText);
            }
            root.refreshWindows();
        }
    }

    property var metadataCache: ({})
    property var metaRetries: ({})
    property var latestRunnerWids: null
    property var inFlightWids: []
    property string lastScannerRawText: ""

    // Process to query open windows directly from /WindowsRunner (fast, 1 process)
    Process {
        id: windowScanner
        command: ["qdbus6", "--literal", "org.kde.KWin", "/WindowsRunner", "org.kde.krunner1.Match", ""]
        property string buf: ""
        property bool scanPending: false
        stdout: SplitParser {
            onRead: data => { windowScanner.buf += data; }
        }
        onExited: exitCode => {
            const raw = windowScanner.buf;
            windowScanner.buf = "";
            if (exitCode === 0 && raw.length > 0 && root.outputsOverride === null) {
                root.handleScannerOutput(raw);
            }
            if (windowScanner.scanPending && exitCode === 0 && KWinService.isKWin && root.outputsOverride === null) {
                windowScanner.scanPending = false;
                windowScanner.running = true;
            } else {
                windowScanner.scanPending = false;
            }
        }
    }

    // Process to query KWin getWindowInfo metadata ONLY for newly discovered windows
    Process {
        id: metaProc
        property string buf: ""
        stdout: SplitParser {
            onRead: data => { metaProc.buf += data; }
        }
        onExited: exitCode => {
            const raw = metaProc.buf;
            metaProc.buf = "";
            if (raw.length > 0) {
                root.parseMetaOutput(raw);
            } else if (root.inFlightWids && root.inFlightWids.length > 0) {
                // Empty output or process failure: count failure for in-flight windows
                let updated = false;
                for (let i = 0; i < root.inFlightWids.length; i++) {
                    const wid = root.inFlightWids[i];
                    if (!wid || !root.isWindowStillActive(wid)) continue;
                    const retries = (root.metaRetries[wid] || 0) + 1;
                    root.metaRetries[wid] = retries;
                    if (retries >= 3) {
                        root.metadataCache[wid] = {
                            desktopFile: "",
                            resourceClass: "",
                            resourceName: ""
                        };
                        updated = true;
                    }
                }
                if (updated && root.lastScannerRawText.length > 0) {
                    root.parseWindowsOutput(root.lastScannerRawText);
                }
            }
            root.inFlightWids = [];
            if (exitCode === 0 && root.outputsOverride === null && root.latestRunnerWids) {
                const activeKeys = Object.keys(root.latestRunnerWids);
                const newlyUncached = [];
                for (let i = 0; i < activeKeys.length; i++) {
                    const k = activeKeys[i];
                    if (!root.metadataCache[k] && !root.metaRetries[k]) {
                        newlyUncached.push(k);
                    }
                }
                if (newlyUncached.length > 0) {
                    root.queryNewWindowMetadata(newlyUncached);
                }
            }
        }
    }

    function isWindowStillActive(wid) {
        if (!wid) return false;
        if (root.latestRunnerWids) {
            return !!root.latestRunnerWids[wid];
        }
        for (let i = 0; i < root.windows.length; i++) {
            if (root.windows[i] && root.windows[i].id === wid) return true;
        }
        return false;
    }

    function handleScannerOutput(text) {
        // Extract authoritative active window UUIDs from runner output
        const re = /\[Argument:\s*\(sssida\{sv\}\)\s*"([^"]*)"/g;
        let m;
        const activeWids = {};
        const uncached = [];
        while ((m = re.exec(text)) !== null) {
            const wid = m[1];
            if (!wid) continue;
            activeWids[wid] = true;
            if (!root.metadataCache[wid]) {
                uncached.push(wid);
            }
        }
        root.latestRunnerWids = activeWids;

        root.parseWindowsOutput(text);

        // Fetch metadata for new windows only (on controlled ticks, not tight loops)
        if (uncached.length > 0 && !metaProc.running) {
            root.queryNewWindowMetadata(uncached);
        }
    }

    function queryNewWindowMetadata(wids) {
        if (!wids || wids.length === 0) return;
        root.inFlightWids = wids.slice();
        const script = "for wid in \"$@\"; do " +
            "uuid=\"${wid#0_}\"; " +
            "if info=$(qdbus6 org.kde.KWin /KWin org.kde.KWin.getWindowInfo \"$uuid\" 2>/dev/null) && [ -n \"$info\" ]; then " +
            "df=\"\"; rc=\"\"; rn=\"\"; " +
            "while IFS= read -r line; do " +
            "case \"$line\" in " +
            "desktopFile:*) df=\"${line#desktopFile: }\" ;; " +
            "resourceClass:*) rc=\"${line#resourceClass: }\" ;; " +
            "resourceName:*) rn=\"${line#resourceName: }\" ;; " +
            "esac; " +
            "done <<EOF\n$info\nEOF\n" +
            "printf \"===KWIN_META:%s\\t%s\\t%s\\t%s===\\n\" \"$wid\" \"$df\" \"$rc\" \"$rn\"; " +
            "else " +
            "printf \"===KWIN_META_FAIL:%s===\\n\" \"$wid\"; " +
            "fi; " +
            "done";
        metaProc.buf = "";
        metaProc.command = ["sh", "-c", script, "--"].concat(wids);
        metaProc.running = true;
    }

    function parseMetaOutput(text) {
        if (!text) return;
        let updated = false;
        const handledWids = {};

        // Parse successful metadata queries
        const metaRe = /===KWIN_META:([^\t\r\n]*)\t([^\t\r\n]*)\t([^\t\r\n]*)\t([^\t\r\n]*)===/g;
        let m;
        while ((m = metaRe.exec(text)) !== null) {
            const mWid = m[1];
            if (!mWid) continue;
            handledWids[mWid] = true;
            if (!root.isWindowStillActive(mWid)) continue; // Discard closed windows
            root.metadataCache[mWid] = {
                desktopFile: (m[2] || "").trim(),
                resourceClass: (m[3] || "").trim(),
                resourceName: (m[4] || "").trim()
            };
            delete root.metaRetries[mWid];
            updated = true;
        }

        // Parse failed metadata queries
        const failRe = /===KWIN_META_FAIL:([^=\r\n]*)===/g;
        let fm;
        while ((fm = failRe.exec(text)) !== null) {
            const fWid = fm[1];
            if (!fWid) continue;
            handledWids[fWid] = true;
            if (!root.isWindowStillActive(fWid)) continue;
            const retries = (root.metaRetries[fWid] || 0) + 1;
            root.metaRetries[fWid] = retries;
            if (retries >= 3) {
                // Permanently cache empty metadata after 3 failed attempts to prevent infinite polling
                root.metadataCache[fWid] = {
                    desktopFile: "",
                    resourceClass: "",
                    resourceName: ""
                };
                updated = true;
            }
        }

        if (root.inFlightWids && root.inFlightWids.length > 0) {
            for (let i = 0; i < root.inFlightWids.length; i++) {
                const wid = root.inFlightWids[i];
                if (!wid || handledWids[wid] || !root.isWindowStillActive(wid)) continue;
                const retries = (root.metaRetries[wid] || 0) + 1;
                root.metaRetries[wid] = retries;
                if (retries >= 3) {
                    root.metadataCache[wid] = {
                        desktopFile: "",
                        resourceClass: "",
                        resourceName: ""
                    };
                    updated = true;
                }
            }
        }

        if (updated && root.lastScannerRawText.length > 0) {
            root.parseWindowsOutput(root.lastScannerRawText);
        }
    }

    function handleActiveWindowOutput(rawText) {
        const trimmed = String(rawText || "").trim();
        if (!trimmed || trimmed === "null") {
            if (root.activeWindowId !== "") {
                root.activeWindowId = "";
            }
            return "";
        }
        const wid = root.cleanWindowId(trimmed);
        if (!wid || !root.isValidWindowUuid(wid)) {
            if (root.activeWindowId !== "") {
                root.activeWindowId = "";
            }
            return "";
        }
        if (root.windows && root.windows.length > 0 && !root.findWindowById(wid)) {
            if (root.activeWindowId !== "") {
                root.activeWindowId = "";
            }
            return "";
        }
        if (root.activeWindowId !== wid) {
            root.activeWindowId = wid;
        }
        return wid;
    }

    // Process to query active window from KWin via kdotool
    Process {
        id: activeWindowProc
        command: ["kdotool", "getactivewindow"]
        property string buf: ""
        stdout: SplitParser {
            onRead: data => { activeWindowProc.buf += data; }
        }
        onExited: exitCode => {
            const raw = activeWindowProc.buf;
            activeWindowProc.buf = "";
            if (exitCode === 0 && root.outputsOverride === null) {
                root.handleActiveWindowOutput(raw);
            }
        }
    }

    // Periodic sync timer for external window changes (KWin fallback)
    Timer {
        id: syncTimer
        interval: 1000
        repeat: true
        running: KWinService.isKWin && root.outputsOverride === null
        onTriggered: {
            root.refreshWindows();
            root.refreshActiveWindow();
        }
    }

    // Prompt reconciliation timer after user-initiated activate/toggle/close/move actions
    Timer {
        id: actionReconcileTimer
        interval: 180
        repeat: false
        onTriggered: {
            root.refreshWindows();
            root.refreshActiveWindow();
            root.refreshWindowOutputs();
        }
    }

    function refreshActiveWindow() {
        if (!KWinService.isKWin || root.outputsOverride !== null) return;
        if (!activeWindowProc.running) {
            activeWindowProc.buf = "";
            activeWindowProc.running = true;
        }
    }

    function refreshWindows() {
        if (!KWinService.isKWin || root.outputsOverride !== null) return;
        if (windowScanner.running) {
            windowScanner.scanPending = true;
            return;
        }
        windowScanner.scanPending = false;
        windowScanner.buf = "";
        windowScanner.running = true;
    }

    function parseWindowsOutput(text, metaOverride) {
        if (!text) return;
        root.lastScannerRawText = text;
        const metaRe = /===KWIN_META:([^\t\r\n]*)\t([^\t\r\n]*)\t([^\t\r\n]*)\t([^\t\r\n]*)===/g;
        let metaMatch;
        while ((metaMatch = metaRe.exec(text)) !== null) {
            const mWid = metaMatch[1];
            if (mWid) {
                root.metadataCache[mWid] = {
                    desktopFile: (metaMatch[2] || "").trim(),
                    resourceClass: (metaMatch[3] || "").trim(),
                    resourceName: (metaMatch[4] || "").trim()
                };
            }
        }
        if (metaOverride && typeof metaOverride === "object") {
            const keys = Object.keys(metaOverride);
            for (let k = 0; k < keys.length; k++) {
                const kw = keys[k];
                root.metadataCache[kw] = metaOverride[kw];
            }
        }

        const re = /\[Argument:\s*\(sssida\{sv\}\)\s*"([^"]*)",\s*"((?:[^"\\]|\\.)*)",\s*"([^"]*)"/g;
        let match;
        const list = [];
        const seenIds = {};
        const activeCleanWids = {};
        const appIdsSet = {};
        const appIdsList = [];
        const prevWindows = root.windows ? root.windows.slice() : [];

        while ((match = re.exec(text)) !== null) {
            const wid = match[1];
            if (!wid || seenIds[wid]) continue;
            seenIds[wid] = true;
            activeCleanWids[root.cleanWindowId(wid)] = true;

            const title = match[2].replace(/\\"/g, '"');
            const icon = match[3];
            const meta = root.metadataCache[wid] || {};
            const desktopFile = (meta.desktopFile || "").trim();
            const resourceClass = (meta.resourceClass || "").trim();
            const resourceName = (meta.resourceName || "").trim();

            if (!title && !icon && !desktopFile && !resourceClass && !resourceName) continue;

            const app = ApplicationService.findAppByTitleOrIcon(title, icon, desktopFile, resourceClass, resourceName);
            const rawMetaClass = (desktopFile || resourceClass || resourceName).toLowerCase().replace(/\.desktop$/, "");
            const validMetaClass = (!ApplicationService.isIgnoredAlias(rawMetaClass)) ? rawMetaClass : "";
            const resolvedAppId = app
                ? app.id
                : (validMetaClass.length > 0
                    ? ("window-" + validMetaClass)
                    : (icon && icon.length > 0 ? icon : ("window-" + wid)));
            const resolvedName = app
                ? app.name
                : (validMetaClass.length > 0 ? (desktopFile || resourceClass || resourceName) : (icon || "Window"));
            const resolvedIcon = app
                ? app.icon
                : (icon && icon.length > 0 ? icon : "application-x-executable");

            const winObj = {
                id: wid,
                title: title,
                icon: resolvedIcon,
                rawIcon: icon,
                desktopFile: desktopFile,
                resourceClass: resourceClass,
                resourceName: resourceName,
                appId: resolvedAppId,
                appName: resolvedName,
                app: app
            };

            list.push(winObj);

            // Never treat dynamic window titles as application identities
            if (resolvedAppId && !appIdsSet[resolvedAppId]) {
                appIdsSet[resolvedAppId] = true;
                appIdsList.push(resolvedAppId);
            }
        }

        root.latestRunnerWids = seenIds;
        root.windows = list;
        root.windowCount = list.length;
        root.runningAppIds = appIdsList;

        if (root.activeWindowId && !activeCleanWids[root.activeWindowId]) {
            root.activeWindowId = "";
        }

        // Prune closed windows from cache, retry tracker, and output map before emitting windowsUpdated
        const cachedKeys = Object.keys(root.metadataCache);
        for (let i = 0; i < cachedKeys.length; i++) {
            const k = cachedKeys[i];
            if (!seenIds[k]) {
                delete root.metadataCache[k];
                delete root.metaRetries[k];
            }
        }
        const retryKeys = Object.keys(root.metaRetries);
        for (let i = 0; i < retryKeys.length; i++) {
            const rk = retryKeys[i];
            if (!seenIds[rk]) {
                delete root.metaRetries[rk];
            }
        }

        // The KWin event bridge is the authoritative writer of
        // windowStates/windowOutputs while it is healthy; scanner-driven
        // pruning would race live bridge events, so it is suspended.
        if (!root.bridgeActive) {
            const outKeys = Object.keys(root.windowOutputs || {});
            let outPruned = false;
            const nextOuts = {};
            for (let i = 0; i < outKeys.length; i++) {
                const ok = outKeys[i];
                if (activeCleanWids[ok]) {
                    nextOuts[ok] = root.windowOutputs[ok];
                } else {
                    outPruned = true;
                }
            }
            if (outPruned) {
                root.windowOutputs = nextOuts;
            }

            const stateKeys = Object.keys(root.windowStates || {});
            let statePruned = false;
            const nextStates = {};
            for (let i = 0; i < stateKeys.length; i++) {
                const sk = stateKeys[i];
                if (activeCleanWids[sk]) {
                    nextStates[sk] = root.windowStates[sk];
                } else {
                    statePruned = true;
                }
            }
            if (statePruned) {
                root.windowStates = nextStates;
            }
        }
        root.windowStateRevision += 1;

        // Reconcile window cycling state across window open/close and late app resolution
        const rawCycleKeys = Object.keys(root.appCycleIndices || {});
        const rawWidKeys = Object.keys(root.appCycleWindowIds || {});
        for (let i = 0; i < rawWidKeys.length; i++) {
            if (rawCycleKeys.indexOf(rawWidKeys[i]) === -1) {
                rawCycleKeys.push(rawWidKeys[i]);
            }
        }
        for (let c = 0; c < rawCycleKeys.length; c++) {
            const oldKey = rawCycleKeys[c];
            let ck = oldKey;
            if (oldKey.indexOf("window-") === 0) {
                const stripped = oldKey.substring(7);
                const resolvedCanon = root.normalizeCycleAppKey(stripped);
                if (resolvedCanon && resolvedCanon !== oldKey && root.isAppRunning(resolvedCanon)) {
                    if (root.appCycleIndices[resolvedCanon] === undefined && root.appCycleIndices[oldKey] !== undefined) {
                        root.appCycleIndices[resolvedCanon] = root.appCycleIndices[oldKey];
                    }
                    if (root.appCycleWindowIds[resolvedCanon] === undefined && root.appCycleWindowIds[oldKey] !== undefined) {
                        root.appCycleWindowIds[resolvedCanon] = root.appCycleWindowIds[oldKey];
                    }
                    delete root.appCycleIndices[oldKey];
                    delete root.appCycleWindowIds[oldKey];
                    ck = resolvedCanon;
                }
            }
            if (!root.isAppRunning(ck)) {
                delete root.appCycleIndices[ck];
                delete root.appCycleWindowIds[ck];
                continue;
            }
            const newWins = root.getWindowsForApp(ck);
            const lastWid = root.appCycleWindowIds[ck] || "";
            if (!lastWid) continue;
            let stillIdx = -1;
            for (let nw = 0; nw < newWins.length; nw++) {
                if (root.cleanWindowId(newWins[nw].id) === lastWid) {
                    stillIdx = nw;
                    break;
                }
            }
            if (stillIdx !== -1) {
                root.appCycleIndices[ck] = stillIdx;
            } else {
                // lastWid disappeared; locate its successor in prevWindows among surviving newWins
                const appObj = ApplicationService.getAppById(ck);
                const targetId = appObj ? appObj.id.toLowerCase().replace(/\.desktop$/, "") : String(ck).toLowerCase().replace(/\.desktop$/, "");
                const aliases = appObj && appObj.aliases ? appObj.aliases : [targetId];
                const prevAppWins = [];
                let prevLastIdx = -1;
                for (let pw = 0; pw < prevWindows.length; pw++) {
                    const pWin = prevWindows[pw];
                    if (root.matchesAppWindow(pWin, appObj, ck, targetId, aliases)) {
                        if (root.cleanWindowId(pWin.id) === lastWid) {
                            prevLastIdx = prevAppWins.length;
                        }
                        prevAppWins.push(pWin);
                    }
                }
                delete root.appCycleWindowIds[ck];
                if (prevLastIdx !== -1 && prevAppWins.length > 1) {
                    let mappedSuccessorIdx = 0;
                    for (let step = 1; step < prevAppWins.length; step++) {
                        const candClean = root.cleanWindowId(prevAppWins[(prevLastIdx + step) % prevAppWins.length].id);
                        let foundNewIdx = -1;
                        for (let nw = 0; nw < newWins.length; nw++) {
                            if (root.cleanWindowId(newWins[nw].id) === candClean) {
                                foundNewIdx = nw;
                                break;
                            }
                        }
                        if (foundNewIdx !== -1) {
                            mappedSuccessorIdx = foundNewIdx;
                            break;
                        }
                    }
                    root.appCycleIndices[ck] = mappedSuccessorIdx;
                }
            }
        }

        root.windowsUpdated();
    }

    function matchesAppWindow(w, app, appId, targetId, aliases) {
        if (!w) return false;
        if (w.app && app) {
            const wCanon = (w.app.id || "").toLowerCase().replace(/\.desktop$/, "");
            return wCanon.length > 0 && wCanon === targetId;
        }
        if (w.app && !app) {
            return false;
        }
        const wAppId = (w.appId || "").toLowerCase().replace(/\.desktop$/, "");
        const wIcon = (w.rawIcon || w.icon || "").toLowerCase().replace(/\.desktop$/, "");
        const wDesktop = (w.desktopFile || "").toLowerCase().replace(/\.desktop$/, "");
        const wClass = (w.resourceClass || "").toLowerCase().replace(/\.desktop$/, "");
        const wResName = (w.resourceName || "").toLowerCase().replace(/\.desktop$/, "");
        if (wAppId === targetId || w.appId === (app ? app.id : appId)) return true;
        if (wDesktop.length > 0 && (wDesktop === targetId || aliases.indexOf(wDesktop) !== -1)) return true;
        if (wClass.length > 0 && (wClass === targetId || aliases.indexOf(wClass) !== -1)) return true;
        if (wResName.length > 0 && (wResName === targetId || aliases.indexOf(wResName) !== -1)) return true;
        if (aliases.indexOf(wAppId) !== -1) return true;
        if (!wDesktop && !wClass && !wResName && wIcon.length > 0 && wIcon !== "application-x-executable" && aliases.indexOf(wIcon) !== -1) return true;
        return false;
    }

    function isAppRunning(appId) {
        if (!appId || !root.windows || root.windows.length === 0) return false;
        const app = ApplicationService.getAppById(appId);
        const targetId = app ? app.id.toLowerCase().replace(/\.desktop$/, "") : String(appId).toLowerCase().replace(/\.desktop$/, "");
        const aliases = app && app.aliases ? app.aliases : [targetId];

        for (let i = 0; i < root.windows.length; i++) {
            if (matchesAppWindow(root.windows[i], app, appId, targetId, aliases)) {
                return true;
            }
        }
        return false;
    }

    function getWindowsForApp(appId) {
        if (!appId || !root.windows || root.windows.length === 0) return [];
        const app = ApplicationService.getAppById(appId);
        const targetId = app ? app.id.toLowerCase().replace(/\.desktop$/, "") : String(appId).toLowerCase().replace(/\.desktop$/, "");
        const aliases = app && app.aliases ? app.aliases : [targetId];
        const result = [];

        for (let i = 0; i < root.windows.length; i++) {
            const w = root.windows[i];
            if (matchesAppWindow(w, app, appId, targetId, aliases)) {
                result.push(w);
            }
        }
        return result;
    }

    function cleanWindowId(wid) {
        if (!wid) return "";
        return String(wid).replace(/^0_/, "").replace(/[{}]/g, "").toLowerCase();
    }

    function isValidWindowUuid(wid) {
        const clean = cleanWindowId(wid);
        return clean.length > 0 && /^[0-9a-f-]+$/.test(clean);
    }

    property var outputsOverride: null
    property var desktopsOverride: null
    property var windowOutputs: ({})
    property var windowStates: ({})
    property int windowStateRevision: 0
    property var lastExecutedAction: null

    onOutputsOverrideChanged: {
        root.windowStateRevision += 1;
    }
    onDesktopsOverrideChanged: {
        root.windowStateRevision += 1;
    }

    readonly property bool isLiveKWinSession: KWinService.isKWin && root.outputsOverride === null && root.desktopsOverride === null

    readonly property var availableOutputs: {
        if (root.outputsOverride !== null && Array.isArray(root.outputsOverride)) {
            const custom = [];
            for (let i = 0; i < root.outputsOverride.length; i++) {
                const name = String(root.outputsOverride[i] || "").trim();
                if (name.length > 0 && /^[a-zA-Z0-9._-]+$/.test(name) && custom.indexOf(name) === -1) {
                    custom.push(name);
                }
            }
            return custom;
        }
        const screens = Quickshell.screens || [];
        const res = [];
        for (let i = 0; i < screens.length; i++) {
            const s = screens[i];
            const name = (s && s.name) ? String(s.name).trim() : "";
            if (name.length > 0 && /^[a-zA-Z0-9._-]+$/.test(name) && res.indexOf(name) === -1) {
                res.push(name);
            }
        }
        return res;
    }

    readonly property var availableDesktops: {
        if (root.desktopsOverride !== null && Array.isArray(root.desktopsOverride)) {
            const custom = [];
            const seen = {};
            for (let i = 0; i < root.desktopsOverride.length; i++) {
                const entry = root.desktopsOverride[i];
                const id = (typeof entry === "object" && entry !== null)
                    ? String(entry.id || "").trim()
                    : String(entry || "").trim();
                const name = (typeof entry === "object" && entry !== null && entry.name)
                    ? String(entry.name).trim()
                    : ("Desktop " + (i + 1));
                const idx = (typeof entry === "object" && entry !== null && entry.index !== undefined)
                    ? Number(entry.index)
                    : i;
                if (id.length > 0 && /^[a-zA-Z0-9._-]+$/.test(id) && !seen[id]) {
                    seen[id] = true;
                    custom.push({ id: id, name: name, index: idx });
                }
            }
            return custom;
        }
        const kdesks = KWinService.desktops || [];
        const res = [];
        const seenK = {};
        for (let i = 0; i < kdesks.length; i++) {
            const d = kdesks[i];
            const id = (d && d.id) ? String(d.id).trim() : "";
            const name = (d && d.name) ? String(d.name).trim() : ("Desktop " + (i + 1));
            const idx = (d && d.index !== undefined) ? Number(d.index) : i;
            if (id.length > 0 && /^[a-zA-Z0-9._-]+$/.test(id) && !seenK[id]) {
                seenK[id] = true;
                res.push({ id: id, name: name, index: idx });
            }
        }
        return res;
    }

    function parseWindowOutputsJson(jsonText) {
        if (!jsonText) return false;
        try {
            const parsed = JSON.parse(String(jsonText).trim());
            if (Array.isArray(parsed)) {
                const hasAnyOutput = parsed.some(item => item && item.output !== undefined);
                const nextOuts = hasAnyOutput ? {} : Object.assign({}, root.windowOutputs || {});
                const nextStates = Object.assign({}, root.windowStates || {});
                for (let i = 0; i < parsed.length; i++) {
                    const item = parsed[i];
                    if (!item || !item.id) continue;
                    const clean = root.cleanWindowId(item.id);
                    if (!clean || !root.isValidWindowUuid(clean)) continue;
                    if (root.windows && root.windows.length > 0 && !root.findWindowById(clean)) {
                        continue;
                    }
                    if (item.output !== undefined) {
                        const outStr = String(item.output || "").trim();
                        if (outStr.length > 0) {
                            nextOuts[clean] = outStr;
                        } else {
                            delete nextOuts[clean];
                        }
                    }
                    const prev = nextStates[clean] || {};
                    const st = {
                        minimized: item.minimized !== undefined ? Boolean(item.minimized) : (prev.minimized !== undefined ? Boolean(prev.minimized) : false),
                        minimizable: item.minimizable !== undefined ? Boolean(item.minimizable) : (prev.minimizable !== undefined ? Boolean(prev.minimizable) : true),
                        maximized: item.maximized !== undefined
                            ? Boolean(item.maximized)
                            : (item.maximizeMode !== undefined
                                ? ((Number(item.maximizeMode) & 3) === 3)
                                : (prev.maximized !== undefined ? Boolean(prev.maximized) : false)),
                        maximizeMode: item.maximizeMode !== undefined
                            ? Number(item.maximizeMode)
                            : (item.maximized !== undefined
                                ? (item.maximized ? 3 : 0)
                                : (prev.maximizeMode !== undefined ? Number(prev.maximizeMode) : 0)),
                        maximizable: item.maximizable !== undefined ? Boolean(item.maximizable) : (prev.maximizable !== undefined ? Boolean(prev.maximizable) : true),
                        fullScreen: item.fullScreen !== undefined ? Boolean(item.fullScreen) : (prev.fullScreen !== undefined ? Boolean(prev.fullScreen) : false),
                        fullScreenable: item.fullScreenable !== undefined ? Boolean(item.fullScreenable) : (prev.fullScreenable !== undefined ? Boolean(prev.fullScreenable) : true),
                        keepAbove: item.keepAbove !== undefined ? Boolean(item.keepAbove) : (prev.keepAbove !== undefined ? Boolean(prev.keepAbove) : false),
                        keepAboveable: item.keepAboveable !== undefined ? Boolean(item.keepAboveable) : (prev.keepAboveable !== undefined ? Boolean(prev.keepAboveable) : true),
                        closeable: item.closeable !== undefined ? Boolean(item.closeable) : (prev.closeable !== undefined ? Boolean(prev.closeable) : true),
                        moveable: item.moveable !== undefined ? Boolean(item.moveable) : (prev.moveable !== undefined ? Boolean(prev.moveable) : true),
                        moveableAcrossScreens: item.moveableAcrossScreens !== undefined ? Boolean(item.moveableAcrossScreens) : (prev.moveableAcrossScreens !== undefined ? Boolean(prev.moveableAcrossScreens) : true),
                        onAllDesktops: item.onAllDesktops !== undefined ? Boolean(item.onAllDesktops) : (prev.onAllDesktops !== undefined ? Boolean(prev.onAllDesktops) : false),
                        desktops: Array.isArray(item.desktops)
                            ? item.desktops.map(d => String(d || "").trim()).filter(d => d.length > 0 && /^[a-zA-Z0-9._-]+$/.test(d))
                            : (Array.isArray(prev.desktops) ? prev.desktops.slice() : []),
                        x: item.x !== undefined ? Number(item.x) : (prev.x !== undefined ? Number(prev.x) : 0),
                        y: item.y !== undefined ? Number(item.y) : (prev.y !== undefined ? Number(prev.y) : 0),
                        width: item.width !== undefined ? Number(item.width) : (prev.width !== undefined ? Number(prev.width) : 0),
                        height: item.height !== undefined ? Number(item.height) : (prev.height !== undefined ? Number(prev.height) : 0)
                    };
                    nextStates[clean] = st;
                }
                root.windowOutputs = nextOuts;
                root.windowStates = nextStates;
                root.windowStateRevision += 1;
                return true;
            }
        } catch (e) {
            Log.warn("WindowService", "Failed to parse window outputs: " + e);
        }
        return false;
    }

    function parseWindowStatesJson(jsonText) {
        return root.parseWindowOutputsJson(jsonText);
    }

    Process {
        id: outputsSyncProc
        property string buf: ""
        command: [
            "kdotool", "kwinscript", "--inline",
            "const wins = workspace.windowList().filter(w => w.normalWindow && !w.deleted).map(w => ({ id: w.internalId.toString(), output: w.output ? w.output.name : '', minimized: !!w.minimized, minimizable: w.minimizable !== false, maximized: ((w.maximizeMode & 3) === 3), maximizeMode: Number(w.maximizeMode || 0), maximizable: w.maximizable !== false, fullScreen: !!w.fullScreen, fullScreenable: w.fullScreenable !== false, keepAbove: !!w.keepAbove, keepAboveable: !w.specialWindow, closeable: w.closeable !== false, moveable: w.moveable !== false, moveableAcrossScreens: w.moveableAcrossScreens !== false, onAllDesktops: !!w.onAllDesktops, desktops: (w.desktops || []).map(d => d.id ? d.id.toString() : ''), x: Math.round(w.x || 0), y: Math.round(w.y || 0), width: Math.round(w.width || 0), height: Math.round(w.height || 0) })); output_result(JSON.stringify(wins));"
        ]
        stdout: SplitParser {
            onRead: data => { outputsSyncProc.buf += data; }
        }
        onExited: exitCode => {
            // Ignore a snapshot that completed while the event bridge took
            // over: bridge records are authoritative and must not be raced.
            if (exitCode === 0 && !root.bridgeActive && outputsSyncProc.buf.trim().length > 0) {
                root.parseWindowOutputsJson(outputsSyncProc.buf);
            }
            outputsSyncProc.buf = "";
        }
    }

    function refreshWindowOutputs() {
        if (!root.isLiveKWinSession || root.bridgeActive) return;
        if (!outputsSyncProc.running) {
            outputsSyncProc.buf = "";
            outputsSyncProc.running = true;
        }
    }

    function refreshWindowStates() {
        root.refreshWindowOutputs();
    }

    // ---- KWin event bridge (authoritative state when healthy) ----
    // Loaded only for a live KWin session with Intellihide enabled. If the
    // compiled plugin is missing or its Qt/ABI does not match, the Loader
    // stays in error state and the snapshot-based sync path above remains
    // the authoritative writer (graceful degradation).
    Loader {
        id: bridgeLoader
        active: root.isLiveKWinSession && ConfigService.dockIntellihide
        source: "bridge/BridgeHost.qml"
        onLoaded: {
            if (!item.enable(Quickshell.shellDir + "/services/kwin/scripts/kwin-event-bridge.js")) {
                Log.warn("WindowService", "KWin event bridge failed to start; keeping snapshot sync");
            }
        }
        onStatusChanged: {
            if (status === Loader.Error) {
                Log.warn("WindowService", "KWin event bridge plugin unavailable; keeping snapshot sync");
            }
        }
    }

    Connections {
        target: bridgeLoader.item
        function onBatchReceived(jsonArray) {
            root.handleBridgeBatch(jsonArray);
        }
        function onDesynchronized(reason) {
            Log.warn("WindowService", "KWin event bridge desynchronized: " + reason);
            // Cached state is stale until the bridge's next snapshot arrives.
            root.windowStates = {};
            root.windowOutputs = {};
            root.windowStateRevision += 1;
        }
    }

    // The bridge is authoritative for windowStates/windowOutputs while it is
    // started and connected to the KWin owner. Anything else (bridge off,
    // plugin failed to load, KWin gone) falls back to snapshot sync.
    readonly property bool bridgeActive: bridgeLoader.item !== null
        && bridgeLoader.item.active && bridgeLoader.item.connected

    onBridgeActiveChanged: {
        if (!root.bridgeActive && root.isLiveKWinSession) {
            // Bridge stopped (config toggle, plugin failure, KWin restart):
            // repopulate window state through the snapshot path.
            root.refreshWindowOutputs();
        }
    }

    function handleBridgeBatch(jsonArray) {
        let payloads;
        try {
            payloads = JSON.parse(jsonArray);
        } catch (e) {
            Log.warn("WindowService", "Failed to parse bridge batch: " + e);
            return;
        }
        if (!Array.isArray(payloads)) return;
        const res = BridgeRecords.applyBatch(root.windowStates, root.windowOutputs, payloads);
        if (!res.ok) return;
        root.windowStates = res.states;
        root.windowOutputs = res.outputs;
        if (res.changed) {
            root.windowStateRevision += 1;
        }
        if (res.desktopId) {
            KWinService.applyExternalDesktop(res.desktopId);
        }
    }

    function isValidOutputName(outputName) {
        if (!outputName || typeof outputName !== "string") return false;
        const trimmed = outputName.trim();
        if (!/^[a-zA-Z0-9._-]+$/.test(trimmed)) return false;
        return root.availableOutputs.indexOf(trimmed) !== -1;
    }

    function isValidDesktopTarget(desktopId) {
        if (!desktopId || typeof desktopId !== "string") return false;
        const trimmed = desktopId.trim();
        if (!/^[a-zA-Z0-9._-]+$/.test(trimmed)) return false;
        if (trimmed === "all") return root.availableDesktops.length > 1;
        const desks = root.availableDesktops || [];
        for (let i = 0; i < desks.length; i++) {
            if (desks[i] && desks[i].id === trimmed) return true;
        }
        return false;
    }

    function findWindowById(windowId) {
        const clean = cleanWindowId(windowId);
        if (!clean || !root.windows) return null;
        for (let i = 0; i < root.windows.length; i++) {
            const w = root.windows[i];
            if (w && cleanWindowId(w.id) === clean) {
                return w;
            }
        }
        return null;
    }

    function getWindowState(windowId) {
        void(root.windowStateRevision);
        const win = findWindowById(windowId);
        if (!win) return null;
        const clean = cleanWindowId(win.id);
        const st = (root.windowStates && root.windowStates[clean]) ? root.windowStates[clean] : {};
        return {
            id: win.id,
            cleanId: clean,
            minimized: Boolean(st.minimized),
            minimizable: st.minimizable !== undefined ? Boolean(st.minimizable) : true,
            maximized: Boolean(st.maximized),
            maximizeMode: st.maximizeMode !== undefined ? Number(st.maximizeMode) : (st.maximized ? 3 : 0),
            maximizable: st.maximizable !== undefined ? Boolean(st.maximizable) : true,
            fullScreen: Boolean(st.fullScreen),
            fullScreenable: st.fullScreenable !== undefined ? Boolean(st.fullScreenable) : true,
            keepAbove: Boolean(st.keepAbove),
            keepAboveable: st.keepAboveable !== undefined ? Boolean(st.keepAboveable) : true,
            closeable: st.closeable !== undefined ? Boolean(st.closeable) : true,
            moveable: st.moveable !== undefined ? Boolean(st.moveable) : true,
            moveableAcrossScreens: st.moveableAcrossScreens !== undefined ? Boolean(st.moveableAcrossScreens) : true,
            onAllDesktops: Boolean(st.onAllDesktops),
            desktops: Array.isArray(st.desktops) ? st.desktops.slice() : [],
            output: root.getWindowOutput(win.id),
            x: st.x !== undefined ? Number(st.x) : 0,
            y: st.y !== undefined ? Number(st.y) : 0,
            width: st.width !== undefined ? Number(st.width) : 0,
            height: st.height !== undefined ? Number(st.height) : 0
        };
    }

    function getWindowDesktops(windowId) {
        const st = getWindowState(windowId);
        if (!st) return [];
        if (st.onAllDesktops) return ["all"];
        return st.desktops;
    }

    function canActivateWindow(windowId) {
        void(root.windowStateRevision);
        return isValidWindowUuid(windowId) && findWindowById(windowId) !== null;
    }

    function canCloseWindow(windowId) {
        const st = getWindowState(windowId);
        return st !== null && st.closeable !== false;
    }

    function canMinimizeWindow(windowId) {
        const st = getWindowState(windowId);
        if (!st) return false;
        return st.minimized || st.minimizable !== false;
    }

    function canMaximizeWindow(windowId) {
        const st = getWindowState(windowId);
        return st !== null && st.maximizable !== false;
    }

    function canFullScreenWindow(windowId) {
        const st = getWindowState(windowId);
        return st !== null && st.fullScreenable !== false;
    }

    function canKeepAboveWindow(windowId) {
        const st = getWindowState(windowId);
        return st !== null && st.keepAboveable !== false;
    }

    function getWindowOutput(windowId) {
        void(root.windowStateRevision);
        const clean = cleanWindowId(windowId);
        if (!clean) return "";
        if (root.windowOutputs && root.windowOutputs[clean]) {
            const mapped = root.windowOutputs[clean];
            if (root.availableOutputs.indexOf(mapped) !== -1) {
                return mapped;
            }
        }
        if (root.availableOutputs.length === 1) {
            return root.availableOutputs[0];
        }
        return "";
    }

    function getTargetOutputsForWindow(windowId) {
        const st = getWindowState(windowId);
        if (!st || !st.moveableAcrossScreens) return [];
        const outs = root.availableOutputs || [];
        if (outs.length <= 1) return [];
        const curOut = getWindowOutput(st.id);
        const targets = [];
        for (let i = 0; i < outs.length; i++) {
            if (!curOut || outs[i] !== curOut) {
                targets.push(outs[i]);
            }
        }
        return targets;
    }

    function getTargetDesktopsForWindow(windowId) {
        const st = getWindowState(windowId);
        if (!st) return [];
        const desks = root.availableDesktops || [];
        if (desks.length <= 1) return [];
        const curDesks = st.desktops || [];
        const isSingleDesk = !st.onAllDesktops && curDesks.length === 1;
        const targets = [];
        for (let i = 0; i < desks.length; i++) {
            const d = desks[i];
            if (!d || !d.id) continue;
            if (!isSingleDesk || curDesks[0] !== d.id) {
                targets.push(d);
            }
        }
        return targets;
    }

    function getWindowCapabilities(windowId) {
        const st = getWindowState(windowId);
        if (!st) {
            return {
                valid: false,
                activate: false,
                minimize: false,
                maximize: false,
                fullscreen: false,
                keepAbove: false,
                close: false,
                moveToOutput: false,
                moveToDesktop: false
            };
        }
        return {
            valid: true,
            activate: true,
            minimize: canMinimizeWindow(windowId),
            maximize: canMaximizeWindow(windowId),
            fullscreen: canFullScreenWindow(windowId),
            keepAbove: canKeepAboveWindow(windowId),
            close: canCloseWindow(windowId),
            moveToOutput: getTargetOutputsForWindow(windowId).length > 0,
            moveToDesktop: getTargetDesktopsForWindow(windowId).length > 0
        };
    }


    // ---- Dock window filtering (selectors only; never mutates root.windows) ----
    // mode/screenName default to the configured mode and no specific screen.
    function _filterCtx(mode, screenName, desktopId) {
        void(root.windowStateRevision);
        return {
            mode: mode === undefined ? ConfigService.dockWindowFilter : mode,
            screenName: screenName || "",
            currentDesktopId: desktopId === undefined ? KWinService.currentDesktopId : desktopId,
            states: root.windowStates,
            cleanId: root.cleanWindowId,
            outputOf: root.getWindowOutput
        };
    }

    function getFilteredWindowsForApp(appId, mode, screenName, desktopId) {
        const wins = getWindowsForApp(appId);
        return WindowFilter.filterWindows(wins, _filterCtx(mode, screenName, desktopId));
    }

    // Running app ids that have at least one window visible in the filtered view.
    function getFilteredRunningAppIds(mode, screenName, desktopId) {
        const ids = root.runningAppIds || [];
        if (WindowFilter.normalizeMode(mode === undefined ? ConfigService.dockWindowFilter : mode) === "all") return ids;
        const res = [];
        for (let i = 0; i < ids.length; i++) {
            if (getFilteredWindowsForApp(ids[i], mode, screenName, desktopId).length > 0) res.push(ids[i]);
        }
        return res;
    }

    function getActiveWindowForApp(appId) {
        const wins = getWindowsForApp(appId);
        if (wins.length === 0 || !root.activeWindowId) return null;
        const curActive = root.activeWindowId;
        for (let i = 0; i < wins.length; i++) {
            if (cleanWindowId(wins[i].id) === curActive) {
                return wins[i];
            }
        }
        return null;
    }

    function pickActivation(appId, filtered) {
        return WindowFilter.pickActivation(filtered, getWindowsForApp(appId), root.activeWindowId, cleanWindowId);
    }

    property var appCycleIndices: ({})
    property var appCycleWindowIds: ({})

    function normalizeCycleAppKey(appId) {
        if (!appId) return "";
        const app = ApplicationService.getAppById(appId);
        const raw = (app && app.id) ? String(app.id) : String(appId);
        return raw.trim().toLowerCase().replace(/\.desktop$/, "");
    }

    function activateWindow(windowId) {
        if (!isValidWindowUuid(windowId)) return false;
        const win = findWindowById(windowId);
        if (!win) return false;
        const clean = cleanWindowId(win.id);
        Log.info("WindowService", "Activating window: " + win.id);
        root.activeWindowId = clean;
        if (win.appId) {
            const normKey = normalizeCycleAppKey(win.appId);
            const appWins = getWindowsForApp(win.appId);
            for (let i = 0; i < appWins.length; i++) {
                if (cleanWindowId(appWins[i].id) === clean) {
                    root.appCycleIndices[normKey] = i;
                    root.appCycleWindowIds[normKey] = clean;
                    break;
                }
            }
        }
        root.lastExecutedAction = { action: "activate", windowId: win.id, cleanId: clean };
        if (root.isLiveKWinSession) {
            Quickshell.execDetached(["qdbus6", "org.kde.KWin", "/WindowsRunner", "org.kde.krunner1.Run", win.id, ""]);
            actionReconcileTimer.restart();
        }
        return true;
    }

    function closeWindow(windowId) {
        if (!isValidWindowUuid(windowId)) return false;
        const win = findWindowById(windowId);
        if (!win) return false;
        const st = getWindowState(win.id);
        if (!st || !st.closeable) return false;
        const clean = cleanWindowId(win.id);
        Log.info("WindowService", "Requesting graceful close for window: " + win.id);
        root.lastExecutedAction = { action: "close", windowId: win.id, cleanId: clean };

        // Do NOT optimistically remove the window from local state; wait for KWin enumeration to confirm closure
        if (root.isLiveKWinSession) {
            const scriptPath = Quickshell.shellDir + "/services/kwin/scripts/kwin-window-action.sh";
            Quickshell.execDetached([scriptPath, "close", win.id]);
            actionReconcileTimer.restart();
        }
        return true;
    }

    function setWindowMinimized(windowId, minimized) {
        if (!isValidWindowUuid(windowId)) return false;
        const win = findWindowById(windowId);
        if (!win) return false;
        const st = getWindowState(win.id);
        if (!st) return false;
        const targetMin = (minimized !== undefined) ? Boolean(minimized) : !st.minimized;
        if (st.minimized === targetMin) return false;
        if (targetMin && !st.minimizable) return false;

        const clean = cleanWindowId(win.id);
        const actName = targetMin ? "minimize" : "unminimize";
        Log.info("WindowService", "Requesting " + actName + " for window: " + win.id);
        root.lastExecutedAction = { action: actName, windowId: win.id, cleanId: clean, targetMinimized: targetMin };

        // Do NOT optimistically mutate windowStates; wait for KWin reconciliation to confirm
        if (root.isLiveKWinSession) {
            const scriptPath = Quickshell.shellDir + "/services/kwin/scripts/kwin-window-action.sh";
            Quickshell.execDetached([scriptPath, actName, win.id]);
            actionReconcileTimer.restart();
        }
        return true;
    }

    function toggleMinimizeWindow(windowId) {
        return setWindowMinimized(windowId, undefined);
    }

    function setWindowMaximized(windowId, maximized) {
        if (!isValidWindowUuid(windowId)) return false;
        const win = findWindowById(windowId);
        if (!win) return false;
        const st = getWindowState(win.id);
        if (!st || !st.maximizable) return false;
        const targetMax = (maximized !== undefined) ? Boolean(maximized) : !st.maximized;
        if (st.maximized === targetMax) return false;

        const clean = cleanWindowId(win.id);
        const actName = targetMax ? "maximize" : "unmaximize";
        Log.info("WindowService", "Requesting " + actName + " for window: " + win.id);
        root.lastExecutedAction = { action: actName, windowId: win.id, cleanId: clean, targetMaximized: targetMax };

        // Do NOT optimistically mutate windowStates; wait for KWin reconciliation to confirm
        if (root.isLiveKWinSession) {
            const scriptPath = Quickshell.shellDir + "/services/kwin/scripts/kwin-window-action.sh";
            Quickshell.execDetached([scriptPath, actName, win.id]);
            actionReconcileTimer.restart();
        }
        return true;
    }

    function toggleMaximizeWindow(windowId) {
        return setWindowMaximized(windowId, undefined);
    }

    function setWindowFullScreen(windowId, fullScreen) {
        if (!isValidWindowUuid(windowId)) return false;
        const win = findWindowById(windowId);
        if (!win) return false;
        const st = getWindowState(win.id);
        if (!st || !st.fullScreenable) return false;
        const targetFs = (fullScreen !== undefined) ? Boolean(fullScreen) : !st.fullScreen;
        if (st.fullScreen === targetFs) return false;

        const clean = cleanWindowId(win.id);
        Log.info("WindowService", "Requesting fullscreen=" + targetFs + " for window: " + win.id);
        root.lastExecutedAction = { action: "fullscreen", windowId: win.id, cleanId: clean, targetFullScreen: targetFs };

        // Do NOT optimistically mutate windowStates; wait for KWin reconciliation to confirm
        if (root.isLiveKWinSession) {
            const scriptPath = Quickshell.shellDir + "/services/kwin/scripts/kwin-window-action.sh";
            Quickshell.execDetached([scriptPath, "fullscreen", win.id, targetFs ? "true" : "false"]);
            actionReconcileTimer.restart();
        }
        return true;
    }

    function toggleFullScreenWindow(windowId) {
        return setWindowFullScreen(windowId, undefined);
    }

    function setWindowKeepAbove(windowId, keepAbove) {
        if (!isValidWindowUuid(windowId)) return false;
        const win = findWindowById(windowId);
        if (!win) return false;
        const st = getWindowState(win.id);
        if (!st || !st.keepAboveable) return false;
        const targetKa = (keepAbove !== undefined) ? Boolean(keepAbove) : !st.keepAbove;
        if (st.keepAbove === targetKa) return false;

        const clean = cleanWindowId(win.id);
        Log.info("WindowService", "Requesting keepAbove=" + targetKa + " for window: " + win.id);
        root.lastExecutedAction = { action: "keep-above", windowId: win.id, cleanId: clean, targetKeepAbove: targetKa };

        // Do NOT optimistically mutate windowStates; wait for KWin reconciliation to confirm
        if (root.isLiveKWinSession) {
            const scriptPath = Quickshell.shellDir + "/services/kwin/scripts/kwin-window-action.sh";
            Quickshell.execDetached([scriptPath, "keep-above", win.id, targetKa ? "true" : "false"]);
            actionReconcileTimer.restart();
        }
        return true;
    }

    function toggleKeepAboveWindow(windowId) {
        return setWindowKeepAbove(windowId, undefined);
    }

    function moveWindowToOutput(windowId, outputName) {
        if (!isValidWindowUuid(windowId)) return false;
        const win = findWindowById(windowId);
        if (!win) return false;
        const st = getWindowState(win.id);
        if (!st || !st.moveableAcrossScreens) return false;
        const outs = root.availableOutputs || [];
        if (outs.length <= 1) return false;
        if (!isValidOutputName(outputName)) return false;
        const targetOut = outputName.trim();
        const curOut = getWindowOutput(win.id);
        if (curOut && curOut === targetOut) return false;

        const clean = cleanWindowId(win.id);
        Log.info("WindowService", "Requesting move for window " + win.id + " to output " + targetOut);
        root.lastExecutedAction = { action: "move-output", windowId: win.id, cleanId: clean, outputName: targetOut };

        // Do NOT optimistically update windowOutputs; wait for actual KWin output sync to confirm movement
        if (root.isLiveKWinSession) {
            const scriptPath = Quickshell.shellDir + "/services/kwin/scripts/kwin-window-action.sh";
            Quickshell.execDetached([scriptPath, "move-output", win.id, targetOut]);
            actionReconcileTimer.restart();
        }
        return true;
    }

    function moveWindowToDesktop(windowId, desktopId) {
        if (!isValidWindowUuid(windowId)) return false;
        const win = findWindowById(windowId);
        if (!win) return false;
        const st = getWindowState(win.id);
        if (!st) return false;
        const desks = root.availableDesktops || [];
        if (desks.length <= 1) return false;
        if (!isValidDesktopTarget(desktopId)) return false;
        const targetDesk = desktopId.trim();
        if (targetDesk === "all") {
            if (st.onAllDesktops) return false;
        } else {
            if (!st.onAllDesktops && st.desktops.length === 1 && st.desktops[0] === targetDesk) {
                return false;
            }
        }

        const clean = cleanWindowId(win.id);
        Log.info("WindowService", "Requesting move for window " + win.id + " to desktop " + targetDesk);
        root.lastExecutedAction = { action: "move-desktop", windowId: win.id, cleanId: clean, desktopId: targetDesk };

        // Do NOT optimistically update windowStates; wait for KWin reconciliation to confirm desktop change
        if (root.isLiveKWinSession) {
            const scriptPath = Quickshell.shellDir + "/services/kwin/scripts/kwin-window-action.sh";
            Quickshell.execDetached([scriptPath, "move-desktop", win.id, targetDesk]);
            actionReconcileTimer.restart();
        }
        return true;
    }

    function toggleWindow(windowId) {
        if (!isValidWindowUuid(windowId)) return false;
        const win = findWindowById(windowId);
        if (!win) return false;
        Log.info("WindowService", "Toggling window: " + win.id);
        const clean = cleanWindowId(win.id);
        if (root.activeWindowId === clean) {
            root.activeWindowId = "";
        } else {
            root.activeWindowId = clean;
        }
        root.lastExecutedAction = { action: "toggle", windowId: win.id, cleanId: clean };
        if (root.isLiveKWinSession) {
            const scriptPath = Quickshell.shellDir + "/services/kwin/scripts/kwin-toggle-window.sh";
            Quickshell.execDetached([scriptPath, win.id]);
            actionReconcileTimer.restart();
        }
        return true;
    }

    function activateApp(appId) {
        const wins = getWindowsForApp(appId);
        if (wins.length === 1) {
            toggleWindow(wins[0].id);
        } else if (wins.length > 1) {
            cycleAppWindows(appId);
        } else {
            ApplicationService.launchAppId(appId);
        }
    }

    function cycleAppWindows(appId, reverse, screenName) {
        if (!appId) return false;
        const normAppId = normalizeCycleAppKey(appId);
        const wins = getFilteredWindowsForApp(appId, undefined, screenName);
        if (wins.length === 0) {
            if (normAppId) {
                delete root.appCycleIndices[normAppId];
                delete root.appCycleWindowIds[normAppId];
            }
            return false;
        }
        if (wins.length === 1) {
            root.appCycleIndices[normAppId] = 0;
            root.appCycleWindowIds[normAppId] = cleanWindowId(wins[0].id);
            return activateWindow(wins[0].id);
        }

        const isReverse = (reverse === true || reverse === -1 ||
                           reverse === "reverse" || reverse === "backward" ||
                           reverse === "prev" || reverse === "previous");
        const step = isReverse ? -1 : 1;

        let activeIdx = -1;
        if (root.activeWindowId) {
            for (let i = 0; i < wins.length; i++) {
                if (cleanWindowId(wins[i].id) === root.activeWindowId) {
                    activeIdx = i;
                    break;
                }
            }
        }

        let targetIdx = 0;
        if (activeIdx !== -1) {
            targetIdx = (activeIdx + step + wins.length) % wins.length;
        } else {
            const lastWid = root.appCycleWindowIds[normAppId] || "";
            let lastWidIdx = -1;
            if (lastWid) {
                for (let i = 0; i < wins.length; i++) {
                    if (cleanWindowId(wins[i].id) === lastWid) {
                        lastWidIdx = i;
                        break;
                    }
                }
            }

            if (lastWidIdx !== -1) {
                targetIdx = (lastWidIdx + step + wins.length) % wins.length;
            } else if (root.appCycleIndices[normAppId] !== undefined) {
                const rawIdx = Number(root.appCycleIndices[normAppId]);
                if (Number.isFinite(rawIdx)) {
                    const clamped = ((Math.trunc(rawIdx) % wins.length) + wins.length) % wins.length;
                    targetIdx = isReverse
                        ? ((clamped - 1 + wins.length) % wins.length)
                        : clamped;
                } else {
                    targetIdx = isReverse ? (wins.length - 1) : 0;
                }
            } else {
                targetIdx = isReverse ? (wins.length - 1) : 0;
            }
        }

        const targetWin = wins[targetIdx];
        if (!targetWin) return false;

        root.appCycleIndices[normAppId] = targetIdx;
        root.appCycleWindowIds[normAppId] = cleanWindowId(targetWin.id);

        return activateWindow(targetWin.id);
    }

    Component.onCompleted: {
        refreshWindows();
        refreshActiveWindow();
        refreshWindowOutputs();
    }
}
