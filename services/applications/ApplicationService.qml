pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import "../config"
import "../core/Log.js" as Log

Singleton {
    id: root

    property var applications: []
    onApplicationsChanged: {
        root.rebuildAliasMap();
    }

    readonly property var pinnedApps: {
        const raw = ConfigService.dockPinned || [];
        const _map = root.aliasMap;
        if (!root.applications || root.applications.length === 0) {
            return [];
        }
        const valid = [];
        for (let i = 0; i < raw.length; i++) {
            const id = raw[i];
            if (id && root.getAppById(id) !== null) {
                valid.push(id);
            }
        }
        return valid;
    }
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

    function cleanAppName(name) {
        if (!name) return "";
        let clean = String(name);
        if (clean.indexOf("appimagekit_") === 0) {
            clean = clean.replace(/^appimagekit_[0-9a-f]+-/, "");
        }
        clean = clean.replace(/\.desktop$/, "");
        clean = clean.replace(/\s*\([vV]?[0-9][0-9a-zA-Z\.\-_+]*\)$/, "");
        return clean.trim();
    }

    property var aliasMap: ({})

    function isIgnoredAlias(alias) {
        if (!alias) return true;
        const a = String(alias).trim().toLowerCase();
        return (a.length <= 1 || a === "env" || a === "sh" || a === "bash" ||
                a.indexOf("@@") === 0 || a === "application-x-executable");
    }

    function rebuildAliasMap() {
        const map = {};
        if (!root.applications) return;

        // Pass 1: Canonical desktop file IDs (highest priority, never overwritten by aliases)
        for (let i = 0; i < root.applications.length; i++) {
            const app = root.applications[i];
            if (!app || !app.id) continue;
            const cleanId = app.id.toLowerCase().replace(/\.desktop$/, "");
            map[cleanId] = app;
            map[app.id.toLowerCase()] = app;
            if (cleanId.indexOf("appimagekit_") === 0) {
                const cleanAppImage = cleanId.replace(/^appimagekit_[0-9a-f]+-/, "");
                if (!isIgnoredAlias(cleanAppImage) && !map[cleanAppImage]) {
                    map[cleanAppImage] = app;
                }
            }
        }

        // Pass 2: Explicit StartupWMClass from desktop entries
        for (let i = 0; i < root.applications.length; i++) {
            const app = root.applications[i];
            if (!app || !app.startupWMClass) continue;
            const wm = app.startupWMClass.trim().toLowerCase();
            if (!isIgnoredAlias(wm) && !map[wm]) {
                map[wm] = app;
            }
        }

        // Pass 3: Icon, Exec binary, clean Name, and secondary aliases
        for (let i = 0; i < root.applications.length; i++) {
            const app = root.applications[i];
            if (!app) continue;
            if (app.icon) {
                const cleanIcon = app.icon.toLowerCase().replace(/\.desktop$/, "");
                if (!isIgnoredAlias(cleanIcon) && !map[cleanIcon]) {
                    map[cleanIcon] = app;
                }
            }
            if (app.execBinary) {
                const eb = app.execBinary.toLowerCase();
                if (!isIgnoredAlias(eb) && !map[eb]) {
                    map[eb] = app;
                }
            }
            if (app.name) {
                const cleanName = app.name.replace(/\s*\([^)]*\)/g, "").trim().toLowerCase();
                if (!isIgnoredAlias(cleanName) && !map[cleanName]) {
                    map[cleanName] = app;
                }
            }
            if (app.aliases && Array.isArray(app.aliases)) {
                for (let a = 0; a < app.aliases.length; a++) {
                    const alias = app.aliases[a].toLowerCase();
                    if (!isIgnoredAlias(alias) && !map[alias]) {
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
        if (isIgnoredAlias(cleanNeedle)) return null;

        // 1. Direct aliasMap index lookup (O(1))
        if (root.aliasMap) {
            if (root.aliasMap[needle]) return root.aliasMap[needle];
            if (root.aliasMap[cleanNeedle]) return root.aliasMap[cleanNeedle];
        }

        // 2. Priority linear scan (ID -> StartupWMClass -> ExecBinary/Aliases)
        for (let i = 0; i < root.applications.length; i++) {
            const app = root.applications[i];
            if (!app || !app.id) continue;
            const aid = app.id.toLowerCase();
            const aClean = aid.replace(/\.desktop$/, "");
            if (aid === needle || aClean === cleanNeedle) return app;
        }
        for (let i = 0; i < root.applications.length; i++) {
            const app = root.applications[i];
            if (!app || !app.startupWMClass) continue;
            if (app.startupWMClass.trim().toLowerCase() === cleanNeedle) return app;
        }
        for (let i = 0; i < root.applications.length; i++) {
            const app = root.applications[i];
            if (!app) continue;
            if (app.icon && app.icon.toLowerCase().replace(/\.desktop$/, "") === cleanNeedle) return app;
            if (app.execBinary && app.execBinary.toLowerCase() === cleanNeedle) return app;
            if (app.aliases && app.aliases.indexOf(cleanNeedle) !== -1) return app;
        }
        return null;
    }

    function findAppByTitleOrIcon(_title, iconName, desktopFile, resourceClass, resourceName) {
        if (!root.applications || root.applications.length === 0) return null;

        // Window titles are content, never application identity.
        // Resolve strictly from KWin metadata: desktopFile -> resourceClass -> resourceName -> iconName
        const candidates = [desktopFile, resourceClass, resourceName, iconName];
        for (let i = 0; i < candidates.length; i++) {
            const raw = String(candidates[i] || "").trim().toLowerCase();
            if (!raw || isIgnoredAlias(raw)) continue;
            const matched = getAppById(raw);
            if (matched) return matched;
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
