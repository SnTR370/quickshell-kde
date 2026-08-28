pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import "../core/Log.js" as Log

Singleton {
    id: root

    property var applications: []
    property var pinnedApps: [
        "org.kde.dolphin",
        "org.kde.konsole",
        "firefox",
        "chromium",
        "code",
        "org.kde.kate",
        "systemsettings"
    ]
    property bool loading: true

    readonly property var categories: [
        { id: "all", name: "All", icon: "applications-all" },
        { id: "internet", name: "Internet", icon: "applications-internet", tag: "Network" },
        { id: "multimedia", name: "Media", icon: "applications-multimedia", tag: "AudioVideo" },
        { id: "development", name: "Development", icon: "applications-development", tag: "Development" },
        { id: "graphics", name: "Graphics", icon: "applications-graphics", tag: "Graphics" },
        { id: "office", name: "Office", icon: "applications-office", tag: "Office" },
        { id: "system", name: "System", icon: "applications-system", tag: "System" },
        { id: "settings", name: "Settings", icon: "preferences-system", tag: "Settings" },
        { id: "utility", name: "Utilities", icon: "applications-utilities", tag: "Utility" }
    ]

    function scanApplications() {
        root.loading = true;
        scanProc.buf = "";
        scanProc.command = ["python3", Quickshell.env("PWD") + "/services/applications/scan_apps.py"];
        scanProc.running = true;
    }

    Process {
        id: scanProc
        property string buf: ""
        stdout: SplitParser {
            onRead: data => { scanProc.buf += data; }
        }
        onExited: exitCode => {
            if (exitCode === 0 && scanProc.buf.trim().length > 0) {
                try {
                    root.applications = JSON.parse(scanProc.buf);
                    Log.info("ApplicationService", "Loaded " + root.applications.length + " applications");
                } catch (e) {
                    Log.error("ApplicationService", "Failed to parse application list: " + e);
                }
            } else {
                Log.warn("ApplicationService", "Scan process exited with code " + exitCode);
            }
            root.loading = false;
            scanProc.buf = "";
        }
    }

    function search(query, categoryId) {
        if (!root.applications || root.applications.length === 0) return [];
        const q = (query || "").trim().toLowerCase();
        let targetCategory = "";

        if (categoryId && categoryId !== "all") {
            for (let i = 0; i < root.categories.length; i++) {
                if (root.categories[i].id === categoryId) {
                    targetCategory = root.categories[i].tag || root.categories[i].name;
                    break;
                }
            }
        }

        const results = [];
        for (let i = 0; i < root.applications.length; i++) {
            const app = root.applications[i];
            
            // Category filter
            if (targetCategory && targetCategory.length > 0) {
                const cats = app.categories || [];
                let matchCat = false;
                for (let c = 0; c < cats.length; c++) {
                    if (cats[c].toLowerCase().indexOf(targetCategory.toLowerCase()) !== -1) {
                        matchCat = true;
                        break;
                    }
                }
                if (!matchCat) continue;
            }

            // Query filter
            if (q.length > 0) {
                const name = (app.name || "").toLowerCase();
                const gname = (app.genericName || "").toLowerCase();
                const comm = (app.comment || "").toLowerCase();
                const exec = (app.exec || "").toLowerCase();
                const appId = (app.id || "").toLowerCase();

                let matchQuery = name.indexOf(q) !== -1 || gname.indexOf(q) !== -1 || comm.indexOf(q) !== -1 || exec.indexOf(q) !== -1 || appId.indexOf(q) !== -1;
                
                if (!matchQuery && app.keywords) {
                    for (let k = 0; k < app.keywords.length; k++) {
                        if (app.keywords[k].toLowerCase().indexOf(q) !== -1) {
                            matchQuery = true;
                            break;
                        }
                    }
                }
                if (!matchQuery) continue;
            }

            results.push(app);
        }
        return results;
    }

    function getAppById(appId) {
        if (!appId || !root.applications) return null;
        const needle = appId.toLowerCase();
        for (let i = 0; i < root.applications.length; i++) {
            const app = root.applications[i];
            if (app.id.toLowerCase() === needle || app.id.toLowerCase() === needle + ".desktop") {
                return app;
            }
        }
        return null;
    }

    function launch(app) {
        if (!app) return;
        Log.info("ApplicationService", "Launching app: " + app.name);
        if (app.desktopFile && app.desktopFile.length > 0) {
            Quickshell.execDetached(["gio", "launch", app.desktopFile]);
        } else if (app.exec && app.exec.length > 0) {
            Quickshell.execDetached(["sh", "-c", app.exec + " &"]);
        }
    }

    function launchAppId(appId) {
        const app = getAppById(appId);
        if (app) {
            launch(app);
        } else {
            Quickshell.execDetached(["gtk-launch", appId]);
        }
    }

    function isPinned(appId) {
        return root.pinnedApps.indexOf(appId) !== -1;
    }

    function togglePin(appId) {
        const idx = root.pinnedApps.indexOf(appId);
        const next = root.pinnedApps.slice();
        if (idx !== -1) {
            next.splice(idx, 1);
        } else {
            next.push(appId);
        }
        root.pinnedApps = next;
    }

    Component.onCompleted: {
        scanApplications();
    }
}
