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
            if (exitCode === 0 && metaProc.buf.length > 0) {
                root.parseMetaOutput(metaProc.buf);
            }
            metaProc.buf = "";
        }
    }

    function handleScannerOutput(text) {
        root.parseWindowsOutput(text);

        // Check for any window UUIDs missing from metadataCache
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

        // Prune closed windows from cache
        const cachedKeys = Object.keys(root.metadataCache);
        for (let i = 0; i < cachedKeys.length; i++) {
            const k = cachedKeys[i];
            if (!activeWids[k]) {
                delete root.metadataCache[k];
            }
        }

        // Fetch metadata for new windows only
        if (uncached.length > 0 && !metaProc.running) {
            root.queryNewWindowMetadata(uncached);
        }
    }

    function queryNewWindowMetadata(wids) {
        if (!wids || wids.length === 0) return;
        const script = "for wid in \"$@\"; do " +
            "uuid=\"${wid#0_}\"; " +
            "info=$(qdbus6 org.kde.KWin /KWin org.kde.KWin.getWindowInfo \"$uuid\" 2>/dev/null); " +
            "df=\"\"; rc=\"\"; rn=\"\"; " +
            "while IFS= read -r line; do " +
            "case \"$line\" in " +
            "desktopFile:*) df=\"${line#desktopFile: }\" ;; " +
            "resourceClass:*) rc=\"${line#resourceClass: }\" ;; " +
            "resourceName:*) rn=\"${line#resourceName: }\" ;; " +
            "esac; " +
            "done <<EOF\n$info\nEOF\n" +
            "printf \"===KWIN_META:%s\\t%s\\t%s\\t%s===\\n\" \"$wid\" \"$df\" \"$rc\" \"$rn\"; " +
            "done";
        metaProc.buf = "";
        metaProc.command = ["sh", "-c", script, "--"].concat(wids);
        metaProc.running = true;
    }

    function parseMetaOutput(text) {
        if (!text) return;
        const metaRe = /===KWIN_META:([^\t\r\n]*)\t([^\t\r\n]*)\t([^\t\r\n]*)\t([^\t\r\n]*)===/g;
        let m;
        let updated = false;
        while ((m = metaRe.exec(text)) !== null) {
            const mWid = m[1];
            if (mWid) {
                root.metadataCache[mWid] = {
                    desktopFile: (m[2] || "").trim(),
                    resourceClass: (m[3] || "").trim(),
                    resourceName: (m[4] || "").trim()
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

    function activateWindow(windowId) {
        if (!windowId) return;
        Log.info("WindowService", "Activating window: " + windowId);
        root.activeWindowId = cleanWindowId(windowId);
        Quickshell.execDetached(["qdbus6", "org.kde.KWin", "/WindowsRunner", "org.kde.krunner1.Run", windowId, ""]);
    }

    function toggleWindow(windowId) {
        if (!windowId) return;
        Log.info("WindowService", "Toggling window: " + windowId);
        const clean = cleanWindowId(windowId);
        if (root.activeWindowId === clean) {
            root.activeWindowId = "";
        } else {
            root.activeWindowId = clean;
        }
        const scriptPath = Quickshell.shellDir + "/services/kwin/scripts/kwin-toggle-window.sh";
        Quickshell.execDetached([scriptPath, windowId]);
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

    function cycleAppWindows(appId) {
        const wins = getWindowsForApp(appId);
        if (wins.length === 0) {
            ApplicationService.launchAppId(appId);
            return;
        }
        if (wins.length === 1) {
            activateWindow(wins[0].id);
            return;
        }

        const normAppId = appId.toLowerCase().replace(/\.desktop$/, "");
        const curIdx = (root.appCycleIndices[normAppId] !== undefined) ? root.appCycleIndices[normAppId] : 0;
        const validIdx = curIdx % wins.length;
        const targetWin = wins[validIdx];

        // Advance to next window index for next click
        root.appCycleIndices[normAppId] = (validIdx + 1) % wins.length;

        activateWindow(targetWin.id);
    }

    Component.onCompleted: {
        refreshWindows();
        refreshActiveWindow();
    }
}
