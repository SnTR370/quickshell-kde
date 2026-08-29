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
    }

    // Refresh window resolution when application scanner finishes
    Connections {
        target: ApplicationService
        function onApplicationsChanged() {
            root.refreshWindows();
        }
    }

    // Process to query open windows from KWin
    Process {
        id: windowScanner
        command: ["qdbus6", "--literal", "org.kde.KWin", "/WindowsRunner", "org.kde.krunner1.Match", ""]
        property string buf: ""
        stdout: SplitParser {
            onRead: data => { windowScanner.buf += data; }
        }
        onExited: exitCode => {
            if (exitCode === 0 && windowScanner.buf.length > 0) {
                root.parseWindowsOutput(windowScanner.buf);
            }
            windowScanner.buf = "";
        }
    }

    // Periodic sync timer for external window changes (KWin fallback)
    Timer {
        id: syncTimer
        interval: 2500
        repeat: true
        running: KWinService.isKWin
        onTriggered: {
            root.refreshWindows();
        }
    }

    function refreshWindows() {
        if (!KWinService.isKWin) return;
        if (!windowScanner.running) {
            windowScanner.buf = "";
            windowScanner.running = true;
        }
    }

    function parseWindowsOutput(text) {
        if (!text) return;
        const re = /\[Argument: \(sssida\{sv\}\) "([^"]+)", "([^"]+)", "([^"]+)"/g;
        let match;
        const list = [];
        const seenIds = {};
        const appIdsSet = {};
        const appIdsList = [];

        while ((match = re.exec(text)) !== null) {
            const wid = match[1];
            if (seenIds[wid]) continue;
            seenIds[wid] = true;

            const title = match[2];
            const icon = match[3];
            const app = ApplicationService.findAppByTitleOrIcon(title, icon);
            const resolvedAppId = app ? app.id : icon;
            const resolvedName = app ? app.name : title;
            const resolvedIcon = app ? app.icon : icon;

            const winObj = {
                id: wid,
                title: title,
                icon: resolvedIcon || icon,
                rawIcon: icon,
                appId: resolvedAppId,
                appName: resolvedName,
                app: app
            };

            list.push(winObj);

            if (!appIdsSet[resolvedAppId]) {
                appIdsSet[resolvedAppId] = true;
                appIdsList.push(resolvedAppId);
            }
        }

        root.windows = list;
        root.windowCount = list.length;
        root.runningAppIds = appIdsList;
        root.windowsUpdated();
    }

    function isAppRunning(appId) {
        if (!appId || !root.windows || root.windows.length === 0) return false;
        const app = ApplicationService.getAppById(appId);
        const targetId = app ? app.id.toLowerCase() : String(appId).toLowerCase().replace(/\.desktop$/, "");
        const aliases = app && app.aliases ? app.aliases : [targetId];

        for (let i = 0; i < root.windows.length; i++) {
            const w = root.windows[i];
            const wAppId = (w.appId || "").toLowerCase().replace(/\.desktop$/, "");
            const wIcon = (w.rawIcon || w.icon || "").toLowerCase().replace(/\.desktop$/, "");
            if (wAppId === targetId || w.appId === (app ? app.id : appId)) return true;
            if (aliases.indexOf(wAppId) !== -1 || aliases.indexOf(wIcon) !== -1) return true;
        }
        return false;
    }

    function getWindowsForApp(appId) {
        if (!appId || !root.windows || root.windows.length === 0) return [];
        const app = ApplicationService.getAppById(appId);
        const targetId = app ? app.id.toLowerCase() : String(appId).toLowerCase().replace(/\.desktop$/, "");
        const aliases = app && app.aliases ? app.aliases : [targetId];
        const result = [];

        for (let i = 0; i < root.windows.length; i++) {
            const w = root.windows[i];
            const wAppId = (w.appId || "").toLowerCase().replace(/\.desktop$/, "");
            const wIcon = (w.rawIcon || w.icon || "").toLowerCase().replace(/\.desktop$/, "");
            if (wAppId === targetId || w.appId === (app ? app.id : appId) || aliases.indexOf(wAppId) !== -1 || aliases.indexOf(wIcon) !== -1) {
                result.push(w);
            }
        }
        return result;
    }

    property var appCycleIndices: ({})

    function activateWindow(windowId) {
        if (!windowId) return;
        Log.info("WindowService", "Activating window: " + windowId);
        Quickshell.execDetached(["qdbus6", "org.kde.KWin", "/WindowsRunner", "org.kde.krunner1.Run", windowId, ""]);
    }

    function activateApp(appId) {
        const wins = getWindowsForApp(appId);
        if (wins.length === 1) {
            activateWindow(wins[0].id);
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
    }
}
