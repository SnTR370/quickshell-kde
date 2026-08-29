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

    property var aliasMap: ({})

    function rebuildAliasMap() {
        const map = {};
        if (!root.applications) return;

        // Pass 1: Primary identifiers (ID, StartupWMClass, Clean Name, Icon)
        for (let i = 0; i < root.applications.length; i++) {
            const app = root.applications[i];
            if (!app) continue;
            if (app.id) {
                const cleanId = app.id.toLowerCase().replace(/\.desktop$/, "");
                map[cleanId] = app;
                map[app.id.toLowerCase()] = app;
                if (cleanId.indexOf("appimagekit_") === 0) {
                    const cleanAppImage = cleanId.replace(/^appimagekit_[0-9a-f]+-/, "");
                    map[cleanAppImage] = app;
                }
            }
            if (app.startupWMClass) {
                map[app.startupWMClass.toLowerCase()] = app;
            }
            if (app.name) {
                const cleanName = app.name.replace(/\s*\([^)]*\)/g, "").trim().toLowerCase();
                if (cleanName.length > 1) {
                    map[cleanName] = app;
                }
            }
            if (app.icon) {
                const cleanIcon = app.icon.toLowerCase().replace(/\.desktop$/, "");
                map[cleanIcon] = app;
            }
        }

        // Pass 2: Secondary / generic fallback aliases (exec binary, generic categories)
        for (let i = 0; i < root.applications.length; i++) {
            const app = root.applications[i];
            if (!app) continue;
            if (app.execBinary) {
                const eb = app.execBinary.toLowerCase();
                if (!map[eb]) {
                    map[eb] = app;
                }
            }
            if (app.aliases && Array.isArray(app.aliases)) {
                for (let a = 0; a < app.aliases.length; a++) {
                    const alias = app.aliases[a].toLowerCase();
                    if (!map[alias]) {
                        map[alias] = app;
                    }
                }
            }
        }
        root.aliasMap = map;
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
                    root.rebuildAliasMap();
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
        const needle = String(appId).trim().toLowerCase();
        const cleanNeedle = needle.replace(/\.desktop$/, "");

        // 1. Direct aliasMap index lookup (O(1))
        if (root.aliasMap) {
            if (root.aliasMap[needle]) return root.aliasMap[needle];
            if (root.aliasMap[cleanNeedle]) return root.aliasMap[cleanNeedle];
        }

        // 2. Linear scan of applications
        for (let i = 0; i < root.applications.length; i++) {
            const app = root.applications[i];
            const aid = app.id.toLowerCase();
            const aClean = aid.replace(/\.desktop$/, "");
            if (aid === needle || aClean === cleanNeedle) return app;
            if (app.startupWMClass && app.startupWMClass.toLowerCase() === cleanNeedle) return app;
            if (app.execBinary && app.execBinary.toLowerCase() === cleanNeedle) return app;
            if (app.aliases && app.aliases.indexOf(cleanNeedle) !== -1) return app;
        }
        return null;
    }

    function findAppByTitleOrIcon(title, iconName) {
        if (!root.applications || root.applications.length === 0) return null;
        const lowerTitle = (title || "").trim().toLowerCase();
        const lowerIcon = (iconName || "").trim().toLowerCase();

        // 1. Check icon name first
        if (lowerIcon.length > 0) {
            const appByIcon = getAppById(lowerIcon);
            if (appByIcon) return appByIcon;
        }

        // 2. Check title separators (common in Wayland / X11 window titles)
        if (lowerTitle.length > 0) {
            // Split title by common suffixes / separators: " — ", " - ", " : ", " | "
            const segments = lowerTitle.split(/\s+[—–\-:|]\s+/);
            // Iterate from end to beginning (apps usually suffix their name, e.g. "quickshell-kde : agy — Konsole")
            for (let s = segments.length - 1; s >= 0; s--) {
                const seg = segments[s].trim();
                if (seg.length > 1) {
                    const matchedApp = getAppById(seg);
                    if (matchedApp) return matchedApp;
                }
            }

            // Direct substring / name match
            for (let i = 0; i < root.applications.length; i++) {
                const a = root.applications[i];
                const cleanName = (a.name || "").replace(/\s*\([^)]*\)/g, "").trim().toLowerCase();
                if (cleanName.length > 2 && lowerTitle.indexOf(cleanName) !== -1) {
                    return a;
                }
                if (a.startupWMClass && a.startupWMClass.length > 2 && lowerTitle.indexOf(a.startupWMClass.toLowerCase()) !== -1) {
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
