pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import "../config"
import "../core/Log.js" as Log

Singleton {
    id: root

    property var applications: []
    readonly property var pinnedApps: ConfigService.dockPinned
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
        const scriptPath = Qt.resolvedUrl("scan_apps.py").toString().replace(/^file:\/\//, "");
        scanProc.command = ["python3", scriptPath];
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

    function findAppByTitleOrIcon(title, iconName) {
        if (!root.applications || root.applications.length === 0) return null;
        const lowerTitle = (title || "").toLowerCase();
        const lowerIcon = (iconName || "").toLowerCase();

        // 1. Direct icon or ID match
        if (lowerIcon.length > 0) {
            for (let i = 0; i < root.applications.length; i++) {
                const a = root.applications[i];
                if (a.icon && a.icon.toLowerCase() === lowerIcon) return a;
                if (a.id.toLowerCase() === lowerIcon || a.id.toLowerCase() === lowerIcon + ".desktop") return a;
            }
        }

        // 2. Title suffix or containment match (e.g. "quickshell-kde : agy — Konsole" -> "Konsole")
        if (lowerTitle.length > 0) {
            // First check exact suffix match after " — " or " - "
            for (let i = 0; i < root.applications.length; i++) {
                const a = root.applications[i];
                const lowerName = (a.name || "").toLowerCase();
                if (lowerName.length > 2 && lowerTitle.indexOf(lowerName) !== -1) {
                    return a;
                }
            }
        }

        return null;
    }

    function parseExecArguments(execStr) {
        if (!execStr || execStr.trim().length === 0) return [];
        // Strip freedesktop field codes (%f, %F, %u, %U, %d, %D, %n, %N, %i, %c, %k, %v, %m)
        const sanitized = execStr.replace(/%[a-zA-Z]/g, "").trim();
        const args = [];
        let current = "";
        let inQuote = false;
        let quoteChar = "";

        for (let i = 0; i < sanitized.length; i++) {
            const ch = sanitized[i];
            if ((ch === '"' || ch === "'") && !inQuote) {
                inQuote = true;
                quoteChar = ch;
            } else if (ch === quoteChar && inQuote) {
                inQuote = false;
                quoteChar = "";
            } else if (ch === ' ' && !inQuote) {
                if (current.length > 0) {
                    args.push(current);
                    current = "";
                }
            } else {
                current += ch;
            }
        }
        if (current.length > 0) {
            args.push(current);
        }
        return args;
    }

    function launch(app) {
        if (!app) return;
        Log.info("ApplicationService", "Launching app: " + (app.name || app.id));
        if (app.desktopFile && app.desktopFile.length > 0) {
            Quickshell.execDetached(["gio", "launch", app.desktopFile]);
        } else if (app.id && app.id.length > 0) {
            Quickshell.execDetached(["gtk-launch", app.id]);
        } else if (app.exec && app.exec.length > 0) {
            const args = parseExecArguments(app.exec);
            if (args.length > 0) {
                Quickshell.execDetached(args);
            }
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
        return ConfigService.isDockPinned(appId);
    }

    function togglePin(appId) {
        ConfigService.toggleDockPinned(appId);
    }

    Component.onCompleted: {
        scanApplications();
    }
}
