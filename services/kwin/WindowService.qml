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
    property var activeWindow: null
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

    // ToplevelManager connection if Wayland toplevels protocol is active
    Connections {
        target: ToplevelManager
        function onActiveToplevelChanged() {
            if (ToplevelManager.activeToplevel) {
                const active = {
                    id: ToplevelManager.activeToplevel.appId,
                    title: ToplevelManager.activeToplevel.title,
                    icon: ToplevelManager.activeToplevel.appId,
                    appId: ToplevelManager.activeToplevel.appId,
                    appName: ToplevelManager.activeToplevel.title,
                    activated: true
                };
                root.activeWindow = active;
            }
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

    // Periodic sync timer for external window changes
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

            const winObj = {
                id: wid,
                title: title,
                icon: icon,
                appId: resolvedAppId,
                appName: resolvedName,
                activated: false
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
        if (!appId || !root.runningAppIds) return false;
        const lower = appId.toLowerCase().replace(/\.desktop$/, "");
        for (let i = 0; i < root.runningAppIds.length; i++) {
            const r = root.runningAppIds[i].toLowerCase().replace(/\.desktop$/, "");
            if (r === lower) return true;
        }
        return false;
    }

    function isAppActive(appId) {
        if (!root.activeWindow || !appId) return false;
        const lower = appId.toLowerCase().replace(/\.desktop$/, "");
        const activeLower = (root.activeWindow.appId || "").toLowerCase().replace(/\.desktop$/, "");
        return lower === activeLower;
    }

    function getWindowsForApp(appId) {
        if (!appId || !root.windows) return [];
        const lower = appId.toLowerCase().replace(/\.desktop$/, "");
        const result = [];
        for (let i = 0; i < root.windows.length; i++) {
            const w = root.windows[i];
            const wLower = (w.appId || "").toLowerCase().replace(/\.desktop$/, "");
            if (wLower === lower) {
                result.push(w);
            }
        }
        return result;
    }

    function activateWindow(windowId) {
        if (!windowId) return;
        Log.info("WindowService", "Activating window: " + windowId);
        Quickshell.execDetached(["qdbus6", "org.kde.KWin", "/WindowsRunner", "org.kde.krunner1.Run", windowId, ""]);
        // Update local activeWindow
        for (let i = 0; i < root.windows.length; i++) {
            if (root.windows[i].id === windowId) {
                root.activeWindow = root.windows[i];
                break;
            }
        }
    }

    function activateApp(appId) {
        const wins = getWindowsForApp(appId);
        if (wins.length > 0) {
            activateWindow(wins[0].id);
        } else {
            ApplicationService.launchAppId(appId);
        }
    }

    function closeWindow(windowId) {
        if (!windowId) return;
        Log.info("WindowService", "Closing window: " + windowId);
        activateWindow(windowId);
        KWinService.triggerGlobalShortcut("Window Close");
        refreshWindows();
    }

    Component.onCompleted: {
        refreshWindows();
    }
}
