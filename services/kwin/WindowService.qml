pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import "../applications"
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
            root.activeWindowId = root.cleanWindowId(windowId);
        }
    }

    // Refresh window resolution when application scanner finishes
    Connections {
        target: ApplicationService
        function onApplicationsChanged() {
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
        stdout: SplitParser {
            onRead: data => { windowScanner.buf += data; }
        }
        onExited: exitCode => {
            if (exitCode === 0 && windowScanner.buf.length > 0) {
                root.handleScannerOutput(windowScanner.buf);
            }
            windowScanner.buf = "";
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
                    }
                }
            }
            root.inFlightWids = [];
            // Retries happen on subsequent controlled scanner ticks, preventing busy loops
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
        const activeCleanWids = {};
        const uncached = [];
        while ((m = re.exec(text)) !== null) {
            const wid = m[1];
            if (!wid) continue;
            activeWids[wid] = true;
            activeCleanWids[root.cleanWindowId(wid)] = true;
            if (!root.metadataCache[wid]) {
                uncached.push(wid);
            }
        }
        root.latestRunnerWids = activeWids;

        root.parseWindowsOutput(text);

        if (root.activeWindowId && !activeCleanWids[root.activeWindowId]) {
            root.activeWindowId = "";
        }

        // Prune closed windows from cache, retry tracker, and output map
        const cachedKeys = Object.keys(root.metadataCache);
        for (let i = 0; i < cachedKeys.length; i++) {
            const k = cachedKeys[i];
            if (!activeWids[k]) {
                delete root.metadataCache[k];
                delete root.metaRetries[k];
            }
        }
        const retryKeys = Object.keys(root.metaRetries);
        for (let i = 0; i < retryKeys.length; i++) {
            const rk = retryKeys[i];
            if (!activeWids[rk]) {
                delete root.metaRetries[rk];
            }
        }
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

        // Parse successful metadata queries
        const metaRe = /===KWIN_META:([^\t\r\n]*)\t([^\t\r\n]*)\t([^\t\r\n]*)\t([^\t\r\n]*)===/g;
        let m;
        while ((m = metaRe.exec(text)) !== null) {
            const mWid = m[1];
            if (!mWid || !root.isWindowStillActive(mWid)) continue; // Discard closed windows
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
            if (!fWid || !root.isWindowStillActive(fWid)) continue;
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

        if (updated && root.lastScannerRawText.length > 0) {
            root.parseWindowsOutput(root.lastScannerRawText);
        }
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
            if (exitCode === 0 && activeWindowProc.buf.trim().length > 0) {
                const wid = root.cleanWindowId(activeWindowProc.buf.trim());
                if (wid.length > 0 && root.activeWindowId !== wid) {
                    root.activeWindowId = wid;
                }
            }
            activeWindowProc.buf = "";
        }
    }

    // Periodic sync timer for external window changes (KWin fallback)
    Timer {
        id: syncTimer
        interval: 1000
        repeat: true
        running: KWinService.isKWin
        onTriggered: {
            root.refreshWindows();
            root.refreshActiveWindow();
        }
    }

    // Prompt reconciliation timer after user-initiated close/move actions
    Timer {
        id: actionReconcileTimer
        interval: 180
        repeat: false
        onTriggered: {
            root.refreshWindows();
            root.refreshWindowOutputs();
        }
    }

    function refreshActiveWindow() {
        if (!KWinService.isKWin) return;
        if (!activeWindowProc.running) {
            activeWindowProc.buf = "";
            activeWindowProc.running = true;
        }
    }

    function refreshWindows() {
        if (!KWinService.isKWin) return;
        if (!windowScanner.running) {
            windowScanner.buf = "";
            windowScanner.running = true;
        }
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
        const appIdsSet = {};
        const appIdsList = [];

        while ((match = re.exec(text)) !== null) {
            const wid = match[1];
            if (!wid || seenIds[wid]) continue;
            seenIds[wid] = true;

            const title = match[2].replace(/\\"/g, '"');
            const icon = match[3];
            const meta = root.metadataCache[wid] || {};
            const desktopFile = (meta.desktopFile || "").trim();
            const resourceClass = (meta.resourceClass || "").trim();
            const resourceName = (meta.resourceName || "").trim();

            if (!title && !icon && !desktopFile && !resourceClass) continue;

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

        root.windows = list;
        root.windowCount = list.length;
        root.runningAppIds = appIdsList;

        const cycleKeys = Object.keys(root.appCycleIndices || {});
        for (let c = 0; c < cycleKeys.length; c++) {
            const ck = cycleKeys[c];
            if (!root.isAppRunning(ck)) {
                delete root.appCycleIndices[ck];
                delete root.appCycleWindowIds[ck];
            }
        }

        root.windowsUpdated();
    }

    function matchesAppWindow(w, app, appId, targetId, aliases) {
        if (!w) return false;
        const wAppId = (w.appId || "").toLowerCase().replace(/\.desktop$/, "");
        const wIcon = (w.rawIcon || w.icon || "").toLowerCase().replace(/\.desktop$/, "");
        const wDesktop = (w.desktopFile || "").toLowerCase().replace(/\.desktop$/, "");
        const wClass = (w.resourceClass || "").toLowerCase().replace(/\.desktop$/, "");
        if (wAppId === targetId || w.appId === (app ? app.id : appId)) return true;
        if (wDesktop.length > 0 && (wDesktop === targetId || aliases.indexOf(wDesktop) !== -1)) return true;
        if (wClass.length > 0 && (wClass === targetId || aliases.indexOf(wClass) !== -1)) return true;
        if (aliases.indexOf(wAppId) !== -1) return true;
        if (wIcon.length > 0 && wIcon !== "application-x-executable" && aliases.indexOf(wIcon) !== -1) return true;
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
    property var windowOutputs: ({})
    property var lastExecutedAction: null

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

    function parseWindowOutputsJson(jsonText) {
        if (!jsonText) return false;
        try {
            const parsed = JSON.parse(String(jsonText).trim());
            if (Array.isArray(parsed)) {
                const next = {};
                for (let i = 0; i < parsed.length; i++) {
                    const item = parsed[i];
                    if (item && item.id && item.output) {
                        next[root.cleanWindowId(item.id)] = String(item.output).trim();
                    }
                }
                root.windowOutputs = next;
                return true;
            }
        } catch (e) {
            Log.warn("WindowService", "Failed to parse window outputs: " + e);
        }
        return false;
    }

    Process {
        id: outputsSyncProc
        property string buf: ""
        command: [
            "kdotool", "kwinscript", "--inline",
            "var wins = workspace.windowList().filter(w => w.normalWindow).map(w => ({ id: w.internalId.toString(), output: w.output ? w.output.name : '' })); output_result(JSON.stringify(wins));"
        ]
        stdout: SplitParser {
            onRead: data => { outputsSyncProc.buf += data; }
        }
        onExited: exitCode => {
            if (exitCode === 0 && outputsSyncProc.buf.trim().length > 0) {
                root.parseWindowOutputsJson(outputsSyncProc.buf);
            }
            outputsSyncProc.buf = "";
        }
    }

    function refreshWindowOutputs() {
        if (!KWinService.isKWin || root.outputsOverride !== null) return;
        if (root.availableOutputs.length <= 1) return;
        if (!outputsSyncProc.running) {
            outputsSyncProc.buf = "";
            outputsSyncProc.running = true;
        }
    }

    function isValidOutputName(outputName) {
        if (!outputName || typeof outputName !== "string") return false;
        const trimmed = outputName.trim();
        if (!/^[a-zA-Z0-9._-]+$/.test(trimmed)) return false;
        return root.availableOutputs.indexOf(trimmed) !== -1;
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

    function getWindowOutput(windowId) {
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
        const win = findWindowById(windowId);
        if (!win) return [];
        const outs = root.availableOutputs || [];
        if (outs.length <= 1) return [];
        const curOut = getWindowOutput(win.id);
        const targets = [];
        for (let i = 0; i < outs.length; i++) {
            if (!curOut || outs[i] !== curOut) {
                targets.push(outs[i]);
            }
        }
        return targets;
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
        if (KWinService.isKWin && root.outputsOverride === null) {
            Quickshell.execDetached(["qdbus6", "org.kde.KWin", "/WindowsRunner", "org.kde.krunner1.Run", win.id, ""]);
        }
        return true;
    }

    function closeWindow(windowId) {
        if (!isValidWindowUuid(windowId)) return false;
        const win = findWindowById(windowId);
        if (!win) return false;
        const clean = cleanWindowId(win.id);
        Log.info("WindowService", "Requesting graceful close for window: " + win.id);
        root.lastExecutedAction = { action: "close", windowId: win.id, cleanId: clean };

        // Do NOT optimistically remove the window from local state; wait for KWin enumeration to confirm closure
        if (KWinService.isKWin && root.outputsOverride === null) {
            const scriptPath = Quickshell.shellDir + "/services/kwin/scripts/kwin-window-action.sh";
            Quickshell.execDetached([scriptPath, "close", win.id]);
            actionReconcileTimer.restart();
        }
        return true;
    }

    function moveWindowToOutput(windowId, outputName) {
        if (!isValidWindowUuid(windowId)) return false;
        const win = findWindowById(windowId);
        if (!win) return false;
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
        if (KWinService.isKWin && root.outputsOverride === null) {
            const scriptPath = Quickshell.shellDir + "/services/kwin/scripts/kwin-window-action.sh";
            Quickshell.execDetached([scriptPath, "move-output", win.id, targetOut]);
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
        if (KWinService.isKWin && root.outputsOverride === null) {
            const scriptPath = Quickshell.shellDir + "/services/kwin/scripts/kwin-toggle-window.sh";
            Quickshell.execDetached([scriptPath, win.id]);
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

    function cycleAppWindows(appId, reverse) {
        if (!appId) return false;
        const normAppId = normalizeCycleAppKey(appId);
        const wins = getWindowsForApp(appId);
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
