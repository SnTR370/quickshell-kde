pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import "../config"
import "../core/Log.js" as Log
import "FileDrop.js" as FileDrop
import "../config/DockStacks.js" as DockStacks

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
        const seenCanon = {};
        for (let i = 0; i < raw.length; i++) {
            const id = raw[i];
            const app = id ? root.getAppById(id) : null;
            if (app !== null) {
                const canon = (app.id || String(id)).toLowerCase().replace(/\.desktop$/, "");
                if (!seenCanon[canon]) {
                    seenCanon[canon] = true;
                    valid.push(id);
                }
            }
        }
        return valid;
    }

    // DOCK-011: merged pinned-row model — pinned applications interleaved
    // with stack markers ("stack:<id>"), in ConfigService.dockPinned order.
    // App entries carry the RAW pinned id (resolvePinnedKey compatibility);
    // stack entries carry the live ConfigService stack object. Pure ordering
    // logic lives in DockStacks.buildDockEntries (node-tested).
    readonly property var dockEntries: {
        const raw = ConfigService.dockPinned || [];
        const stacks = ConfigService.dockStacks || [];
        const _apps = root.applications;
        const _map = root.aliasMap;
        return DockStacks.buildDockEntries(raw, stacks, function(id) {
            return root.getAppById(id);
        });
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
        if (scanProc.running) {
            scanProc.scanPending = true;
            return false;
        }
        scanProc.scanPending = false;
        root.loading = true;
        scanProc.buf = "";
        const scriptPath = Qt.resolvedUrl("scan_apps.py").toString().replace(/^file:\/\//, "");
        scanProc.command = ["python3", scriptPath];
        scanProc.running = true;
        return true;
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
                a === "flatpak" || a === "snap" || a === "xdg-open" ||
                a === "gio" || a === "gtk-launch" || a === "electron" ||
                a.indexOf("@@") === 0 || a === "application-x-executable");
    }

    function resolveCanonicalAppId(appId) {
        if (!appId || typeof appId !== "string") return "";
        const norm = ConfigService.normalizeDockAppId(appId);
        if (!norm || isIgnoredAlias(norm)) return "";
        if (root.applications && root.applications.length > 0) {
            const app = root.getAppById(norm);
            if (app && app.id) {
                return ConfigService.normalizeDockAppId(app.id).toLowerCase();
            }
        }
        return norm.toLowerCase();
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

        // Pass 3: Reverse-DNS basename of canonical ID and Exec binary
        for (let i = 0; i < root.applications.length; i++) {
            const app = root.applications[i];
            if (!app) continue;
            if (app.id) {
                const cleanId = app.id.toLowerCase().replace(/\.desktop$/, "");
                const dotParts = cleanId.split(".");
                if (dotParts.length > 1) {
                    const lastPart = dotParts[dotParts.length - 1];
                    if (!isIgnoredAlias(lastPart) && !map[lastPart]) {
                        map[lastPart] = app;
                    }
                }
            }
            if (app.execBinary) {
                const eb = app.execBinary.toLowerCase();
                if (!isIgnoredAlias(eb) && !map[eb]) {
                    map[eb] = app;
                }
            }
        }

        // Pass 4: Clean Name and Icon
        for (let i = 0; i < root.applications.length; i++) {
            const app = root.applications[i];
            if (!app) continue;
            if (app.name) {
                const cleanName = app.name.replace(/\s*\([^)]*\)/g, "").trim().toLowerCase();
                if (!isIgnoredAlias(cleanName) && !map[cleanName]) {
                    map[cleanName] = app;
                }
            }
            if (app.icon) {
                const cleanIcon = app.icon.toLowerCase().replace(/\.desktop$/, "");
                if (!isIgnoredAlias(cleanIcon) && !map[cleanIcon]) {
                    map[cleanIcon] = app;
                }
            }
        }

        // Pass 5: Secondary aliases
        for (let i = 0; i < root.applications.length; i++) {
            const app = root.applications[i];
            if (!app || !app.aliases || !Array.isArray(app.aliases)) continue;
            for (let a = 0; a < app.aliases.length; a++) {
                const alias = app.aliases[a].toLowerCase();
                if (!isIgnoredAlias(alias) && !map[alias]) {
                    map[alias] = app;
                }
            }
        }
        root.aliasMap = map;

        if (typeof ConfigService.canonicalAppIdResolver !== "function") {
            ConfigService.canonicalAppIdResolver = function(rawId) {
                return root.resolveCanonicalAppId(rawId);
            };
        }
        if (root.applications.length > 0 && ConfigService.dockPinned && ConfigService.dockPinned.length > 1) {
            const deduped = ConfigService.sanitizeDockPinned(ConfigService.dockPinned);
            if (deduped.length !== ConfigService.dockPinned.length) {
                ConfigService.dockPinned = deduped;
            }
        }
    }

    Process {
        id: scanProc
        property string buf: ""
        property bool scanPending: false
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
            if (scanProc.scanPending) {
                scanProc.scanPending = false;
                root.scanApplications();
            }
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

        if (root.applications.length > 0 && (!root.aliasMap || Object.keys(root.aliasMap).length === 0)) {
            root.rebuildAliasMap();
        }

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
            if (app.execBinary && app.execBinary.toLowerCase() === cleanNeedle) return app;
            if (app.icon && app.icon.toLowerCase().replace(/\.desktop$/, "") === cleanNeedle) return app;
            if (app.aliases && app.aliases.indexOf(cleanNeedle) !== -1) return app;
        }
        return null;
    }

    function findAppByTitleOrIcon(_title, iconName, desktopFile, resourceClass, resourceName) {
        if (!root.applications || root.applications.length === 0) return null;

        // Window titles are content, never application identity.
        // Resolve strictly from KWin metadata: desktopFile -> resourceClass -> resourceName.
        // Only fall back to iconName when KWin metadata is absent/empty so an unknown app
        // with explicit metadata never hijacks an unrelated app via a shared generic icon.
        const metaCandidates = [desktopFile, resourceClass, resourceName];
        let hadValidMeta = false;
        for (let i = 0; i < metaCandidates.length; i++) {
            const raw = String(metaCandidates[i] || "").trim().toLowerCase();
            if (!raw || isIgnoredAlias(raw)) continue;
            hadValidMeta = true;
            const matched = getAppById(raw);
            if (matched) return matched;
        }
        if (hadValidMeta) return null;

        const rawIcon = String(iconName || "").trim().toLowerCase();
        if (rawIcon && !isIgnoredAlias(rawIcon)) {
            return getAppById(rawIcon);
        }

        return null;
    }

    property bool launchDryRun: false
    property var lastLaunchedCommand: null

    function parseExecArguments(execStr, iconName, appName, desktopFile) {
        if (!execStr || typeof execStr !== "string" || execStr.trim().length === 0) return [];
        const raw = execStr.trim();
        const rawTokens = [];
        let current = "";
        let inQuote = false;
        let quoteChar = "";
        let hadQuotedEmpty = false;

        for (let i = 0; i < raw.length; i++) {
            const ch = raw[i];
            if (ch === "\\" && i + 1 < raw.length && quoteChar !== "'") {
                current += raw[i + 1];
                i += 1;
                continue;
            }
            if ((ch === '"' || ch === "'") && !inQuote) {
                inQuote = true;
                quoteChar = ch;
                if (i + 1 < raw.length && raw[i + 1] === ch && current.length === 0) {
                    hadQuotedEmpty = true;
                }
            } else if (ch === quoteChar && inQuote) {
                inQuote = false;
                quoteChar = "";
            } else if ((ch === ' ' || ch === '\t') && !inQuote) {
                if (current.length > 0 || hadQuotedEmpty) {
                    rawTokens.push(current);
                    current = "";
                    hadQuotedEmpty = false;
                }
            } else {
                current += ch;
            }
        }
        if (inQuote) {
            // Reject unbalanced quotes
            return [];
        }
        if (current.length > 0 || hadQuotedEmpty) {
            rawTokens.push(current);
        }

        const args = [];
        const pctPlaceholder = "\u0000LITERAL_PCT\u0000";
        for (let t = 0; t < rawTokens.length; t++) {
            const tok = rawTokens[t];
            if (tok === "%i") {
                if (iconName && String(iconName).trim().length > 0) {
                    args.push("--icon");
                    args.push(String(iconName).trim());
                }
                continue;
            }
            if (tok === "%f" || tok === "%F" || tok === "%u" || tok === "%U" ||
                tok === "%d" || tok === "%D" || tok === "%n" || tok === "%N" ||
                tok === "%v" || tok === "%m") {
                continue;
            }
            if (tok === "%c") {
                if (appName && String(appName).trim().length > 0) {
                    args.push(String(appName).trim());
                }
                continue;
            }
            if (tok === "%k") {
                if (desktopFile && String(desktopFile).trim().length > 0) {
                    args.push(String(desktopFile).trim());
                }
                continue;
            }
            let cleaned = tok.replace(/%%/g, pctPlaceholder);
            cleaned = cleaned.replace(/%c/g, appName ? String(appName) : "");
            cleaned = cleaned.replace(/%k/g, desktopFile ? String(desktopFile) : "");
            cleaned = cleaned.replace(/%[a-zA-Z]/g, "");
            cleaned = cleaned.replace(new RegExp(pctPlaceholder, "g"), "%");
            if (cleaned.length > 0) {
                args.push(cleaned);
            }
        }

        while (args.length > 0 && /^[A-Za-z_][A-Za-z0-9_]*=/.test(args[0])) {
            args.shift();
        }
        if (args.length === 0 || args[0].trim().length === 0) return [];
        return args;
    }

    function getAppActions(appIdOrApp) {
        if (!appIdOrApp) return [];
        const app = (typeof appIdOrApp === "object" && appIdOrApp !== null)
            ? appIdOrApp
            : root.getAppById(String(appIdOrApp));
        if (!app || !app.actions || !Array.isArray(app.actions)) return [];
        const valid = [];
        const seen = {};
        for (let i = 0; i < app.actions.length; i++) {
            const act = app.actions[i];
            if (!act || typeof act !== "object") continue;
            const id = String(act.id || "").trim();
            const name = String(act.name || "").trim();
            if (!id || !name || !/^[A-Za-z0-9._-]+$/.test(id) || seen[id]) continue;
            const icon = String(act.icon || "").trim();
            let args = [];
            if (Array.isArray(act.execArgs) && act.execArgs.length > 0) {
                for (let a = 0; a < act.execArgs.length; a++) {
                    const tok = String(act.execArgs[a] !== undefined ? act.execArgs[a] : "");
                    if (a === 0 && tok.trim().length === 0) {
                        args = [];
                        break;
                    }
                    args.push(tok);
                }
            }
            if (args.length === 0 && act.exec && typeof act.exec === "string") {
                args = root.parseExecArguments(act.exec, icon || app.icon || "", name, app.desktopFile || "");
            }
            if (args.length === 0) continue;
            seen[id] = true;
            valid.push({
                id: id,
                name: name,
                icon: icon,
                exec: String(act.exec || args.join(" ")),
                execArgs: args
            });
        }
        return valid;
    }

    function launchAppAction(appIdOrApp, actionIdOrAction) {
        if (!appIdOrApp || !actionIdOrAction) return false;
        const app = (typeof appIdOrApp === "object" && appIdOrApp !== null && appIdOrApp.id)
            ? appIdOrApp
            : root.getAppById(String(appIdOrApp));
        if (!app) return false;
        const targetId = (typeof actionIdOrAction === "object" && actionIdOrAction !== null)
            ? String(actionIdOrAction.id || "").trim()
            : String(actionIdOrAction).trim();
        if (!targetId) return false;

        const actions = root.getAppActions(app);
        let matched = null;
        for (let i = 0; i < actions.length; i++) {
            if (actions[i].id === targetId) {
                matched = actions[i];
                break;
            }
        }
        if (!matched || !matched.execArgs || matched.execArgs.length === 0) return false;

        Log.info("ApplicationService", "Launching quick action '" + matched.id + "' for app: " + (app.name || app.id));
        root.lastLaunchedCommand = {
            type: "action",
            appId: app.id,
            actionId: matched.id,
            name: matched.name,
            args: matched.execArgs.slice()
        };
        if (!root.launchDryRun) {
            Quickshell.execDetached(matched.execArgs);
        }
        return true;
    }

    function launch(app) {
        if (!app) return false;
        Log.info("ApplicationService", "Launching app: " + (app.name || app.id));
        if (app.desktopFile && app.desktopFile.length > 0) {
            const cmd = ["gio", "launch", app.desktopFile];
            root.lastLaunchedCommand = { type: "app", appId: app.id || "", args: cmd };
            if (!root.launchDryRun) {
                Quickshell.execDetached(cmd);
            }
            return true;
        } else if (app.id && app.id.length > 0 && (!app.exec || app.exec.length === 0)) {
            const cmd = ["gtk-launch", app.id];
            root.lastLaunchedCommand = { type: "app", appId: app.id, args: cmd };
            if (!root.launchDryRun) {
                Quickshell.execDetached(cmd);
            }
            return true;
        } else if (app.exec && app.exec.length > 0) {
            const args = (Array.isArray(app.execArgs) && app.execArgs.length > 0)
                ? app.execArgs.slice()
                : parseExecArguments(app.exec, app.icon || "", app.name || "", app.desktopFile || "");
            if (args.length > 0) {
                root.lastLaunchedCommand = { type: "app", appId: app.id || "", args: args };
                if (!root.launchDryRun) {
                    Quickshell.execDetached(args);
                }
                return true;
            }
        } else if (app.id && app.id.length > 0) {
            const cmd = ["gtk-launch", app.id];
            root.lastLaunchedCommand = { type: "app", appId: app.id, args: cmd };
            if (!root.launchDryRun) {
                Quickshell.execDetached(cmd);
            }
            return true;
        }
        return false;
    }

    function launchAppId(appId) {
        if (!appId || typeof appId !== "string") return false;
        const app = getAppById(appId);
        if (app) {
            return launch(app);
        } else {
            const cmd = ["gtk-launch", appId];
            root.lastLaunchedCommand = { type: "app", appId: appId, args: cmd };
            if (!root.launchDryRun) {
                Quickshell.execDetached(cmd);
            }
            return true;
        }
    }

    // DOCK-010: open local files with a specific application (external file
    // drops onto dock icons). URI filtering and mechanism choice live in
    // FileDrop.js (pure, node-tested); this stays the single execution point
    // so the launch obeys the same argv/execDetached conventions as launch().
    // Multi-file drops open in ONE invocation. Dry-run aware for tests.
    function launchFiles(app, paths) {
        if (!app || !Array.isArray(paths) || paths.length === 0) return false;
        let tokenized = [];
        if (Array.isArray(app.execArgs) && app.execArgs.length > 0) {
            tokenized = app.execArgs;
        } else if (app.exec && String(app.exec).trim().length > 0) {
            tokenized = parseExecArguments(app.exec, app.icon || "", app.name || "", app.desktopFile || "");
        }
        const cmd = FileDrop.buildLaunchCommand(app, paths, tokenized);
        if (!cmd) return false;
        Log.info("ApplicationService", "Opening " + paths.length + " file(s) with app: " + (app.name || app.id));
        root.lastLaunchedCommand = { type: "files", appId: app.id || "", args: cmd };
        if (!root.launchDryRun) {
            Quickshell.execDetached(cmd);
        }
        return true;
    }

    // DOCK-011: open files/folders with the user's default associations
    // (freedesktop standard via gio; the repo already prefers gio launch in
    // launch()). Used by folder stacks: directory rows in the popup and the
    // "open in file manager" action. Argv array only; dry-run aware.
    function openPaths(paths) {
        if (!paths || paths.length === undefined || paths.length === 0) return false;
        const clean = [];
        for (let i = 0; i < paths.length; i++) {
            const p = String(paths[i] === undefined || paths[i] === null ? "" : paths[i]).trim();
            if (p.length > 0) clean.push(p);
        }
        if (clean.length === 0) return false;
        const cmd = ["gio", "open"].concat(clean);
        Log.info("ApplicationService", "Opening " + clean.length + " path(s) with default apps");
        root.lastLaunchedCommand = { type: "open", appId: "", args: cmd };
        if (!root.launchDryRun) {
            Quickshell.execDetached(cmd);
        }
        return true;
    }

    function resolvePinnedKey(appId) {
        if (!appId || typeof appId !== "string") return "";
        const norm = ConfigService.normalizeDockAppId(appId);
        if (!norm) return "";
        const raw = ConfigService.dockPinned || [];
        const directIdx = ConfigService.findDockPinnedIndex(norm, raw);
        if (directIdx !== -1) {
            return raw[directIdx];
        }
        if (root.applications && root.applications.length > 0) {
            const app = root.getAppById(norm);
            if (app) {
                for (let i = 0; i < raw.length; i++) {
                    const pinnedApp = root.getAppById(raw[i]);
                    if (pinnedApp && pinnedApp.id === app.id) {
                        return raw[i];
                    }
                }
            }
        }
        return norm;
    }

    function isPinned(appId) {
        const key = resolvePinnedKey(appId);
        return ConfigService.isDockPinned(key);
    }

    function togglePin(appId) {
        if (!appId || typeof appId !== "string") return false;
        const norm = ConfigService.normalizeDockAppId(appId);
        if (!norm || isIgnoredAlias(norm)) return false;
        const key = resolvePinnedKey(norm);
        if (!key) return false;
        if (ConfigService.isDockPinned(key)) {
            return ConfigService.toggleDockPinned(key);
        }
        if (root.applications && root.applications.length > 0) {
            const app = root.getAppById(key);
            if (!app) return false;
            const canonKey = ConfigService.normalizeDockAppId(app.id || key);
            return ConfigService.toggleDockPinned(canonKey || key);
        }
        return ConfigService.toggleDockPinned(key);
    }

    function pinAppAt(appId, targetIndex) {
        if (!appId || typeof appId !== "string") return false;
        const norm = ConfigService.normalizeDockAppId(appId);
        if (!norm || isIgnoredAlias(norm)) return false;
        if (isPinned(appId)) return false;
        if (!getAppById(appId)) return false;

        const visibleBefore = (root.applications && root.applications.length > 0)
            ? root.pinnedApps.slice()
            : ConfigService.sanitizeDockPinned(ConfigService.dockPinned);
        if (targetIndex !== undefined && targetIndex !== null) {
            if (typeof targetIndex !== "number" || !Number.isInteger(targetIndex) ||
                targetIndex < 0 || targetIndex > visibleBefore.length) {
                return false;
            }
        }

        const rawBefore = ConfigService.sanitizeDockPinned(ConfigService.dockPinned);
        if (!togglePin(appId)) return false;
        if (typeof targetIndex === "number" && Number.isInteger(targetIndex)) {
            const newIdx = getPinnedIndex(appId);
            if (newIdx < 0) {
                ConfigService.dockPinned = rawBefore;
                ConfigService.saveDockConfig();
                return false;
            }
            const clamped = Math.max(0, Math.min(newIdx, targetIndex));
            if (newIdx > 0 && clamped !== newIdx) {
                reorderPinnedApps(newIdx, clamped);
            }
            if (getPinnedIndex(appId) !== clamped) {
                ConfigService.dockPinned = rawBefore;
                ConfigService.saveDockConfig();
                return false;
            }
        }
        return isPinned(appId);
    }

    function getPinnedIndex(appId) {
        const key = resolvePinnedKey(appId);
        if (!key) return -1;
        const list = (root.applications && root.applications.length > 0)
            ? root.pinnedApps
            : (ConfigService.dockPinned || []);
        return ConfigService.findDockPinnedIndex(key, list);
    }

    function canMovePinned(appId, direction) {
        const step = ConfigService.resolveMoveStep(direction);
        if (step === 0) return false;
        const list = (root.applications && root.applications.length > 0)
            ? root.pinnedApps
            : (ConfigService.dockPinned || []);
        const idx = getPinnedIndex(appId);
        if (idx === -1) return false;
        const targetIdx = idx + step;
        return targetIdx >= 0 && targetIdx < list.length;
    }

    function movePinnedApp(appId, direction) {
        const step = ConfigService.resolveMoveStep(direction);
        if (step === 0) return false;
        const key = resolvePinnedKey(appId);
        if (!key || !ConfigService.isDockPinned(key)) return false;

        if (root.applications && root.applications.length > 0) {
            const visible = root.pinnedApps;
            const visIdx = ConfigService.findDockPinnedIndex(key, visible);
            if (visIdx === -1) return false;
            const targetVisIdx = visIdx + step;
            if (targetVisIdx < 0 || targetVisIdx >= visible.length) return false;
            return ConfigService.reorderDockPinnedByAppId(key, visible[targetVisIdx]);
        }
        return ConfigService.moveDockPinned(key, step);
    }

    function movePinnedLeft(appId) {
        return movePinnedApp(appId, "left");
    }

    function movePinnedRight(appId) {
        return movePinnedApp(appId, "right");
    }

    function reorderPinnedApps(fromIndexOrAppId, toIndexOrAppId) {
        if (typeof fromIndexOrAppId === "number" && typeof toIndexOrAppId === "number") {
            if (!Number.isInteger(fromIndexOrAppId) || !Number.isInteger(toIndexOrAppId)) return false;
            if (root.applications && root.applications.length > 0) {
                const visible = root.pinnedApps;
                if (fromIndexOrAppId < 0 || fromIndexOrAppId >= visible.length ||
                    toIndexOrAppId < 0 || toIndexOrAppId >= visible.length ||
                    fromIndexOrAppId === toIndexOrAppId) {
                    return false;
                }
                return ConfigService.reorderDockPinnedByAppId(visible[fromIndexOrAppId], visible[toIndexOrAppId]);
            }
            return ConfigService.reorderDockPinned(fromIndexOrAppId, toIndexOrAppId);
        }
        if (typeof fromIndexOrAppId === "string" && typeof toIndexOrAppId === "string") {
            const fromKey = resolvePinnedKey(fromIndexOrAppId);
            const toKey = resolvePinnedKey(toIndexOrAppId);
            if (!fromKey || !toKey) return false;
            if (root.applications && root.applications.length > 0) {
                const visible = root.pinnedApps;
                const fromVisIdx = ConfigService.findDockPinnedIndex(fromKey, visible);
                const toVisIdx = ConfigService.findDockPinnedIndex(toKey, visible);
                if (fromVisIdx === -1 || toVisIdx === -1 || fromVisIdx === toVisIdx) {
                    return false;
                }
            }
            return ConfigService.reorderDockPinnedByAppId(fromKey, toKey);
        }
        return false;
    }

    Component.onCompleted: {
        ConfigService.canonicalAppIdResolver = function(rawId) {
            return root.resolveCanonicalAppId(rawId);
        };
        scanApplications();
    }
}
