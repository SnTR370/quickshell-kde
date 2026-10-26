pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Services.SystemTray
import "../core"
import "../kwin"
import "../kwin/WindowFilter.js" as WindowFilter

Singleton {
    id: root

    // Config file paths
    readonly property string configDir: Quickshell.env("XDG_CONFIG_HOME") ? (Quickshell.env("XDG_CONFIG_HOME") + "/quickshell-kde") : (Quickshell.env("HOME") + "/.config/quickshell-kde")
    readonly property string barConfigFile: configDir + "/bar_config.json"
    readonly property string dockConfigFile: configDir + "/dock_config.json"

    // --- Bar Surface State ---
    property bool barEnabled: true
    property bool barFloating: true
    property string barEdge: "top"
    property alias barPosition: root.barEdge // Backward compatibility alias
    property int barEdgeOffset: 8
    property bool barReserveSpace: false
    property int barHeight: 30
    property var barLeft: ["launcher", "workspaces"]
    property var barCenter: ["clock"]
    property var barRight: ["media", "tray", "network", "battery", "audio", "brightness", "controlcenter", "power"]
    property real barOpacity: 0.92
    property var barMonitors: "all"
    property bool blurEnabled: true
    property bool notificationsEnabled: false
    property var trayItemPolicies: ({})
    property bool controlCenterMigrated: false

    // --- Dock Surface State ---
    property bool dockEnabled: true
    property bool dockFloating: true
    property string dockEdge: "bottom"
    property alias dockPosition: root.dockEdge // Backward compatibility alias
    property int dockEdgeOffset: 8
    property bool dockReserveSpace: false
    property int dockIconSize: 44
    property bool dockAutoHide: false
    property int dockHideDelay: 350
    property int dockRevealDelay: 120
    property var dockMonitors: "all"
    // Dock window filter: all | desktop | monitor | desktop-and-monitor (invalid -> all)
    property string dockWindowFilter: "all"
    property var dockPinned: ["org.kde.dolphin", "org.kde.konsole", "firefox", "code", "systemsettings"]
    property var canonicalAppIdResolver: null

    // --- Window Visibility State ---
    property bool launcherVisible: false
    property bool settingsVisible: false
    property string launcherScreenName: ""
    property string settingsScreenName: ""

    onSettingsVisibleChanged: {
        if (root.settingsVisible && root.settingsScreenName === "") {
            root.settingsScreenName = root.resolveScreenName();
        } else if (!root.settingsVisible) {
            root.settingsScreenName = "";
        }
    }

    onLauncherVisibleChanged: {
        if (root.launcherVisible && root.launcherScreenName === "") {
            root.launcherScreenName = root.resolveScreenName();
        } else if (!root.launcherVisible) {
            root.launcherScreenName = "";
        }
    }

    Connections {
        target: Quickshell
        function onScreensChanged() {
            root.validateScreenOwnership();
        }
    }

    function validateScreenOwnership() {
        const screens = Quickshell.screens || [];
        if (screens.length === 0) {
            root.settingsVisible = false;
            root.settingsScreenName = "";
            root.launcherVisible = false;
            root.launcherScreenName = "";
            return;
        }

        if (root.settingsVisible && root.settingsScreenName !== "") {
            let found = false;
            for (let i = 0; i < screens.length; i++) {
                if (screens[i].name === root.settingsScreenName) {
                    found = true;
                    break;
                }
            }
            if (!found) {
                root.settingsScreenName = screens[0].name;
            }
        }

        if (root.launcherVisible && root.launcherScreenName !== "") {
            let found = false;
            for (let i = 0; i < screens.length; i++) {
                if (screens[i].name === root.launcherScreenName) {
                    found = true;
                    break;
                }
            }
            if (!found) {
                root.launcherScreenName = screens[0].name;
            }
        }
    }

    function resolveScreenName(screenObjOrName) {
        const screens = Quickshell.screens || [];
        if (screens.length === 0) return "";

        // 1. If screen object passed, verify it exists in Quickshell.screens
        if (typeof screenObjOrName === "object" && screenObjOrName && screenObjOrName.name) {
            for (let i = 0; i < screens.length; i++) {
                if (screens[i].name === screenObjOrName.name) {
                    return screenObjOrName.name;
                }
            }
        }

        // 2. If screen name string passed, verify it exists in Quickshell.screens
        if (typeof screenObjOrName === "string" && screenObjOrName.length > 0) {
            for (let i = 0; i < screens.length; i++) {
                if (screens[i].name === screenObjOrName) {
                    return screenObjOrName;
                }
            }
        }

        // 3. Try KWin active output if it exists in Quickshell.screens
        if (KWinService.activeOutputName && KWinService.activeOutputName.length > 0) {
            for (let i = 0; i < screens.length; i++) {
                if (screens[i].name === KWinService.activeOutputName) {
                    return KWinService.activeOutputName;
                }
            }
        }

        // 4. Safe fallback: exactly the primary/first connected screen
        return screens[0].name;
    }

    function toggleLauncher(screenObjOrName) {
        if (root.launcherVisible) {
            root.launcherVisible = false;
            root.launcherScreenName = "";
        } else {
            root.settingsVisible = false;
            root.launcherScreenName = root.resolveScreenName(screenObjOrName);
            root.launcherVisible = true;
        }
    }

    function toggleSettings(screenObjOrName) {
        if (root.settingsVisible) {
            root.settingsVisible = false;
            root.settingsScreenName = "";
        } else {
            root.launcherVisible = false;
            root.settingsScreenName = root.resolveScreenName(screenObjOrName);
            root.settingsVisible = true;
        }
    }

    function isScreenAllowed(screenObj, filter) {
        if (!screenObj) return false;
        if (!filter || filter === "all") return true;
        if (Array.isArray(filter)) {
            if (filter.length === 0) return true; // Safe fallback: empty list means all screens
            return filter.indexOf(screenObj.name) !== -1;
        }
        if (typeof filter === "string") {
            if (filter === screenObj.name) return true;
            // Legacy migration fallback for old configs containing "primary" or "default"
            if (filter === "primary" || filter === "default") return true;
        }
        return false;
    }

    JsonStore {
        id: barStore
        path: root.barConfigFile
        fallbackPath: Qt.resolvedUrl("../../config/bar_config.json").toString().replace(/^file:\/\//, "")
        defaultValue: ({
            "enabled": true,
            "floating": true,
            "edge": "top",
            "position": "top",
            "edgeOffset": 8,
            "reserveSpace": false,
            "height": 30,
            "left": ["launcher", "workspaces"],
            "center": ["clock"],
            "right": ["media", "tray", "network", "battery", "audio", "brightness", "controlcenter", "power"],
            "opacity": 0.92,
            "monitors": "all",
            "blur": true,
            "notificationsEnabled": false,
            "trayItemPolicies": {},
            "controlCenterMigrated": true
        })
        property var modifiedBeforeLoad: ({})
        property bool saveRequestedBeforeLoad: false
        onLoadedValue: (parsed, _) => {
            if (!parsed || typeof parsed !== "object" || parsed.length !== undefined) return;
            const mod = barStore.modifiedBeforeLoad || {};
            if (typeof parsed.enabled === "boolean" && !mod["enabled"]) root.barEnabled = parsed.enabled;
            if (typeof parsed.floating === "boolean" && !mod["floating"]) root.barFloating = parsed.floating;
            if (!mod["edge"]) {
                const rawEdge = parsed.edge || parsed.position || "";
                if (rawEdge === "top" || rawEdge === "bottom" || rawEdge === "left" || rawEdge === "right") {
                    root.barEdge = rawEdge;
                }
            }
            if (typeof parsed.edgeOffset === "number" && Number.isFinite(parsed.edgeOffset) && !mod["edgeOffset"]) {
                root.barEdgeOffset = Math.max(0, Math.min(64, Math.trunc(parsed.edgeOffset)));
            }
            if (typeof parsed.reserveSpace === "boolean" && !mod["reserveSpace"]) root.barReserveSpace = parsed.reserveSpace;
            if (typeof parsed.height === "number" && Number.isFinite(parsed.height) && !mod["height"]) {
                root.barHeight = Math.max(24, Math.min(120, Math.trunc(parsed.height)));
            }
            if (parsed.left && !mod["left"]) root.barLeft = ModuleRegistry.sanitizeSlotList(parsed.left, root.barLeft);
            if (parsed.center && !mod["center"]) root.barCenter = ModuleRegistry.sanitizeSlotList(parsed.center, root.barCenter);
            if (parsed.right && !mod["right"]) root.barRight = ModuleRegistry.sanitizeSlotList(parsed.right, root.barRight);
            if (parsed.controlCenterMigrated === true) {
                root.controlCenterMigrated = true;
            } else if (!mod["right"]) {
                const hasCC = (root.barLeft.indexOf("controlcenter") !== -1) ||
                              (root.barCenter.indexOf("controlcenter") !== -1) ||
                              (root.barRight.indexOf("controlcenter") !== -1);
                if (!hasCC) {
                    const nextRight = root.barRight.slice();
                    const pIdx = nextRight.indexOf("power");
                    if (pIdx !== -1) {
                        nextRight.splice(pIdx, 0, "controlcenter");
                    } else {
                        nextRight.push("controlcenter");
                    }
                    root.barRight = nextRight;
                }
                root.controlCenterMigrated = true;
            }
            if (typeof parsed.opacity === "number" && Number.isFinite(parsed.opacity) && !mod["opacity"]) {
                root.barOpacity = Math.max(0.1, Math.min(1.0, parsed.opacity));
            }
            if (parsed.monitors !== undefined && !mod["monitors"]) {
                root.barMonitors = (parsed.monitors === "primary" || parsed.monitors === "default") ? "all" : parsed.monitors;
            }
            if (typeof parsed.blur === "boolean" && !mod["blur"]) root.blurEnabled = parsed.blur;
            if (typeof parsed.notificationsEnabled === "boolean" && !mod["notificationsEnabled"]) {
                root.notificationsEnabled = parsed.notificationsEnabled;
            }
            if (parsed.trayItemPolicies && typeof parsed.trayItemPolicies === "object" && parsed.trayItemPolicies.length === undefined && !mod["trayItemPolicies"]) {
                const cleanPolicies = {};
                for (const k in parsed.trayItemPolicies) {
                    const key = String(k || "").trim();
                    if (key.length > 0) {
                        cleanPolicies[key] = root.normalizeTrayPolicy(parsed.trayItemPolicies[k]);
                    }
                }
                root.trayItemPolicies = cleanPolicies;
            }
            barStore.modifiedBeforeLoad = ({});
            if (barStore.saveRequestedBeforeLoad) {
                barStore.saveRequestedBeforeLoad = false;
                root.saveBarConfig();
            }
        }
        onFailed: (phase, _, __) => {
            if (phase === "read" || phase === "parse") {
                barStore.modifiedBeforeLoad = ({});
                if (barStore.saveRequestedBeforeLoad && phase !== "parse") {
                    barStore.saveRequestedBeforeLoad = false;
                    root.saveBarConfig();
                } else {
                    barStore.saveRequestedBeforeLoad = false;
                }
            }
        }
    }

    JsonStore {
        id: dockStore
        path: root.dockConfigFile
        fallbackPath: Qt.resolvedUrl("../../config/dock_config.json").toString().replace(/^file:\/\//, "")
        defaultValue: ({
            "enabled": true,
            "floating": true,
            "edge": "bottom",
            "position": "bottom",
            "edgeOffset": 8,
            "reserveSpace": false,
            "iconSize": 44,
            "autoHide": false,
            "hideDelay": 350,
            "revealDelay": 120,
            "monitors": "all",
            "pinned": ["org.kde.dolphin", "org.kde.konsole", "firefox", "code", "systemsettings"]
        })
        property var modifiedBeforeLoad: ({})
        property bool saveRequestedBeforeLoad: false
        onLoadedValue: (parsed, _) => {
            if (!parsed || typeof parsed !== "object" || parsed.length !== undefined) return;
            const mod = dockStore.modifiedBeforeLoad || {};
            if (typeof parsed.enabled === "boolean" && !mod["enabled"]) root.dockEnabled = parsed.enabled;
            if (typeof parsed.floating === "boolean" && !mod["floating"]) root.dockFloating = parsed.floating;
            if (!mod["edge"]) {
                const rawEdge = parsed.edge || parsed.position || "";
                if (rawEdge === "top" || rawEdge === "bottom" || rawEdge === "left" || rawEdge === "right") {
                    root.dockEdge = rawEdge;
                }
            }
            if (typeof parsed.edgeOffset === "number" && Number.isFinite(parsed.edgeOffset) && !mod["edgeOffset"]) {
                root.dockEdgeOffset = Math.max(0, Math.min(64, Math.trunc(parsed.edgeOffset)));
            }
            if (typeof parsed.reserveSpace === "boolean" && !mod["reserveSpace"]) root.dockReserveSpace = parsed.reserveSpace;
            if (typeof parsed.iconSize === "number" && Number.isFinite(parsed.iconSize) && !mod["iconSize"]) {
                root.dockIconSize = Math.max(20, Math.min(128, Math.trunc(parsed.iconSize)));
            }
            if (typeof parsed.autoHide === "boolean" && !mod["autoHide"]) root.dockAutoHide = parsed.autoHide;
            if (typeof parsed.hideDelay === "number" && Number.isFinite(parsed.hideDelay) && !mod["hideDelay"]) {
                root.dockHideDelay = Math.max(50, Math.min(2000, Math.trunc(parsed.hideDelay)));
            }
            if (typeof parsed.revealDelay === "number" && Number.isFinite(parsed.revealDelay) && !mod["revealDelay"]) {
                root.dockRevealDelay = Math.max(0, Math.min(1000, Math.trunc(parsed.revealDelay)));
            }
            if (parsed.monitors !== undefined && !mod["monitors"]) {
                root.dockMonitors = (parsed.monitors === "primary" || parsed.monitors === "default") ? "all" : parsed.monitors;
            }
            if (parsed.windowFilter !== undefined && !mod["windowFilter"]) {
                root.dockWindowFilter = WindowFilter.normalizeMode(parsed.windowFilter);
            }
            if (parsed.pinned && typeof parsed.pinned === "object" && parsed.pinned.length !== undefined && !mod["pinned"]) {
                root.dockPinned = root.sanitizeDockPinned(parsed.pinned);
            }
            dockStore.modifiedBeforeLoad = ({});
            if (dockStore.saveRequestedBeforeLoad) {
                dockStore.saveRequestedBeforeLoad = false;
                root.saveDockConfig();
            }
        }
        onFailed: (phase, _, __) => {
            if (phase === "read" || phase === "parse") {
                dockStore.modifiedBeforeLoad = ({});
                if (dockStore.saveRequestedBeforeLoad && phase !== "parse") {
                    dockStore.saveRequestedBeforeLoad = false;
                    root.saveDockConfig();
                } else {
                    dockStore.saveRequestedBeforeLoad = false;
                }
            }
        }
    }

    function _markBarModified(key) {
        if (!barStore.loaded && key) {
            barStore.modifiedBeforeLoad[key] = true;
        }
    }

    function _markDockModified(key) {
        if (!dockStore.loaded && key) {
            dockStore.modifiedBeforeLoad[key] = true;
        }
    }

    function reloadBarConfig() {
        return barStore.load();
    }

    function reloadDockConfig() {
        return dockStore.load();
    }

    // --- Bar Operations ---
    function saveBarConfig() {
        if (!barStore.loaded) {
            barStore.saveRequestedBeforeLoad = true;
            return;
        }
        barStore.save({
            "enabled": root.barEnabled,
            "floating": root.barFloating,
            "edge": root.barEdge,
            "position": root.barEdge,
            "edgeOffset": root.barEdgeOffset,
            "reserveSpace": root.barReserveSpace,
            "height": root.barHeight,
            "left": root.barLeft,
            "center": root.barCenter,
            "right": root.barRight,
            "opacity": root.barOpacity,
            "monitors": root.barMonitors,
            "blur": root.blurEnabled,
            "notificationsEnabled": root.notificationsEnabled,
            "trayItemPolicies": root.trayItemPolicies || {},
            "controlCenterMigrated": root.controlCenterMigrated
        });
    }

    function normalizeTrayPolicy(policy) {
        const p = String(policy || "").trim().toLowerCase();
        if (p === "always" || p === "visible" || p === "always_visible" || p === "always visible") return "always";
        if (p === "hidden" || p === "hide") return "hidden";
        return "auto";
    }

    function getTrayBaseId(itemOrId) {
        if (!itemOrId) return "";
        const raw = (typeof itemOrId === "object") ? String(itemOrId.id || "").trim() : String(itemOrId).trim();
        if (!raw) return "";
        const stripped = raw.replace(/_status_icon_\d+$/, "");
        return stripped.length > 0 ? stripped : raw;
    }

    function isGenericTrayPrefix(prefix) {
        if (!prefix) return false;
        const lower = String(prefix).toLowerCase();
        return (lower === "chrome" || lower === "chromium" || lower === "electron" ||
                lower === "status_icon" || lower === "app" || lower === "java" ||
                lower === "python" || lower === "python3");
    }

    function hasTrayPrefixCollision(prefix, itemsList) {
        if (!prefix) return false;
        if (isGenericTrayPrefix(prefix)) return true;
        const list = (itemsList !== undefined && itemsList !== null)
            ? itemsList
            : ((typeof SystemTray !== "undefined" && SystemTray.items) ? SystemTray.items.values : []);
        let matches = 0;
        const prefixTag = prefix + "_status_icon_";
        for (let i = 0; i < list.length; i++) {
            const it = list[i];
            if (!it) continue;
            const rawId = String(it.id || "").trim();
            if (rawId === prefix || rawId.indexOf(prefixTag) === 0) {
                matches++;
                if (matches > 1) return true;
            }
        }
        const policies = root.trayItemPolicies || {};
        for (const k in policies) {
            if (k.indexOf(prefixTag) === 0) {
                return true;
            }
        }
        return false;
    }

    function isLegacyTrayKeyCovered(savedKey, itemsList) {
        if (!savedKey || isGenericTrayPrefix(savedKey)) return false;
        const prefixTag = savedKey + "_status_icon_";
        const list = (itemsList !== undefined && itemsList !== null)
            ? itemsList
            : ((typeof SystemTray !== "undefined" && SystemTray.items) ? SystemTray.items.values : []);
        for (let i = 0; i < list.length; i++) {
            const it = list[i];
            if (!it) continue;
            const rawId = String(it.id || "").trim();
            if (rawId === savedKey || rawId.indexOf(prefixTag) === 0) {
                return true;
            }
        }
        const policies = root.trayItemPolicies || {};
        for (const otherKey in policies) {
            if (otherKey.indexOf(prefixTag) === 0) {
                return true;
            }
        }
        return false;
    }

    function getTrayItemId(itemOrId, itemsList) {
        if (!itemOrId) return "";
        const raw = (typeof itemOrId === "object") ? String(itemOrId.id || "").trim() : String(itemOrId).trim();
        if (!raw) return "";
        const policies = root.trayItemPolicies || {};
        if (policies[raw] !== undefined) return raw;
        const stripped = getTrayBaseId(raw);
        if (!stripped || stripped === raw) return raw;
        if (hasTrayPrefixCollision(stripped, itemsList)) return raw;
        return stripped;
    }

    function getTrayItemPolicy(itemOrId, itemsList) {
        if (!itemOrId) return "auto";
        const policies = root.trayItemPolicies || {};
        const raw = (typeof itemOrId === "object") ? String(itemOrId.id || "").trim() : String(itemOrId).trim();
        if (raw && policies[raw] !== undefined) {
            return normalizeTrayPolicy(policies[raw]);
        }
        const key = getTrayItemId(itemOrId, itemsList);
        if (key && policies[key] !== undefined) {
            return normalizeTrayPolicy(policies[key]);
        }
        const baseKey = getTrayBaseId(raw);
        if (baseKey && baseKey !== raw && !isGenericTrayPrefix(baseKey) && policies[baseKey] !== undefined) {
            return normalizeTrayPolicy(policies[baseKey]);
        }
        return "auto";
    }

    function setTrayItemPolicy(itemOrId, policy, itemsList) {
        const key = getTrayItemId(itemOrId, itemsList);
        if (!key) return;
        const validPolicy = normalizeTrayPolicy(policy);
        const next = {};
        const current = root.trayItemPolicies || {};
        for (const k in current) {
            next[k] = current[k];
        }
        const raw = (typeof itemOrId === "object" && itemOrId) ? String(itemOrId.id || "").trim() : String(itemOrId || "").trim();
        if (raw && raw !== key && next[raw] !== undefined && !hasTrayPrefixCollision(key, itemsList)) {
            delete next[raw];
        }
        next[key] = validPolicy;
        root._markBarModified("trayItemPolicies");
        root.trayItemPolicies = next;
        saveBarConfig();
    }

    function setBarEnabled(enabled) {
        root._markBarModified("enabled");
        root.barEnabled = enabled;
        saveBarConfig();
    }

    function setBarFloating(floating) {
        root._markBarModified("floating");
        root.barFloating = floating;
        saveBarConfig();
    }

    function setBarEdge(edge) {
        if (edge === "top" || edge === "bottom" || edge === "left" || edge === "right") {
            root._markBarModified("edge");
            root.barEdge = edge;
            saveBarConfig();
        }
    }

    function setBarPosition(pos) {
        setBarEdge(pos);
    }

    function setBarEdgeOffset(offset) {
        root._markBarModified("edgeOffset");
        root.barEdgeOffset = Math.max(0, Math.min(64, offset));
        saveBarConfig();
    }

    function setBarReserveSpace(reserve) {
        root._markBarModified("reserveSpace");
        root.barReserveSpace = reserve;
        saveBarConfig();
    }

    function setBarHeight(h) {
        root._markBarModified("height");
        root.barHeight = Math.max(24, Math.min(120, h));
        saveBarConfig();
    }

    function setBarOpacity(op) {
        root._markBarModified("opacity");
        root.barOpacity = Math.max(0.1, Math.min(1.0, op));
        saveBarConfig();
    }

    function setBarMonitors(m) {
        root._markBarModified("monitors");
        if (!m || m === "primary" || m === "default" || (Array.isArray(m) && m.length === 0)) {
            root.barMonitors = "all";
        } else {
            root.barMonitors = m;
        }
        saveBarConfig();
    }

    function toggleBarMonitor(screenName) {
        if (!screenName) return;
        const screens = Quickshell.screens || [];
        let currentList = [];
        if (root.barMonitors === "all") {
            for (let i = 0; i < screens.length; i++) {
                currentList.push(screens[i].name);
            }
        } else if (Array.isArray(root.barMonitors)) {
            currentList = root.barMonitors.slice();
        } else if (typeof root.barMonitors === "string") {
            currentList = [root.barMonitors];
        }

        const idx = currentList.indexOf(screenName);
        if (idx !== -1) {
            if (currentList.length <= 1) {
                root.setBarMonitors("all");
                return;
            }
            currentList.splice(idx, 1);
        } else {
            currentList.push(screenName);
        }

        if (currentList.length >= screens.length && screens.length > 0) {
            root.setBarMonitors("all");
        } else {
            root.setBarMonitors(currentList);
        }
    }

    function setBlurEnabled(b) {
        root._markBarModified("blur");
        root.blurEnabled = b;
        saveBarConfig();
    }

    function setNotificationsEnabled(n) {
        root._markBarModified("notificationsEnabled");
        root.notificationsEnabled = n;
        saveBarConfig();
    }

    // --- Dock Operations ---
    function normalizeDockAppId(appId) {
        if (!appId || typeof appId !== "string") return "";
        const norm = appId.trim().replace(/\.desktop$/i, "");
        if (norm.length <= 1 || !/^[a-zA-Z0-9._-]+$/.test(norm)) return "";
        const lower = norm.toLowerCase();
        if (lower === "env" || lower === "sh" || lower === "bash" ||
            lower === "flatpak" || lower === "snap" || lower === "xdg-open" ||
            lower === "gio" || lower === "gtk-launch" || lower === "electron" ||
            lower === "application-x-executable" || lower.indexOf("window-") === 0) {
            return "";
        }
        return norm;
    }

    function resolveCanonicalDockAppKey(appId) {
        const norm = normalizeDockAppId(appId).toLowerCase();
        if (!norm) return "";
        if (typeof root.canonicalAppIdResolver === "function") {
            const resolved = root.canonicalAppIdResolver(norm);
            if (resolved && typeof resolved === "string" && resolved.length > 0) {
                return resolved.trim().toLowerCase().replace(/\.desktop$/i, "");
            }
        }
        return norm;
    }

    function dockAppIdsMatch(idA, idB) {
        const normA = normalizeDockAppId(idA).toLowerCase();
        const normB = normalizeDockAppId(idB).toLowerCase();
        if (!normA || !normB) return false;
        if (normA === normB) return true;
        const canonA = resolveCanonicalDockAppKey(normA);
        const canonB = resolveCanonicalDockAppKey(normB);
        return canonA.length > 0 && canonA === canonB;
    }

    function sanitizeDockPinned(list) {
        if (!list || typeof list === "string" || list.length === undefined) return [];
        const clean = [];
        const seen = {};
        for (let i = 0; i < list.length; i++) {
            const norm = normalizeDockAppId(list[i]);
            if (!norm) continue;
            const key = norm.toLowerCase();
            const canonKey = resolveCanonicalDockAppKey(norm);
            if (!seen[key] && (!canonKey || !seen[canonKey])) {
                seen[key] = true;
                if (canonKey) seen[canonKey] = true;
                clean.push(norm);
            }
        }
        return clean;
    }

    function findDockPinnedIndex(appId, list) {
        const norm = normalizeDockAppId(appId).toLowerCase();
        if (!norm) return -1;
        const arr = (list !== undefined && list !== null) ? list : (root.dockPinned || []);
        if (!arr || typeof arr === "string" || arr.length === undefined) return -1;
        for (let i = 0; i < arr.length; i++) {
            if (normalizeDockAppId(arr[i]).toLowerCase() === norm) {
                return i;
            }
        }
        const canon = resolveCanonicalDockAppKey(norm);
        if (canon) {
            for (let i = 0; i < arr.length; i++) {
                if (resolveCanonicalDockAppKey(arr[i]) === canon) {
                    return i;
                }
            }
        }
        return -1;
    }

    function saveDockConfig() {
        root._markDockModified("pinned");
        root.dockPinned = sanitizeDockPinned(root.dockPinned);
        if (!dockStore.loaded) {
            dockStore.saveRequestedBeforeLoad = true;
            return;
        }
        dockStore.save({
            "enabled": root.dockEnabled,
            "floating": root.dockFloating,
            "edge": root.dockEdge,
            "position": root.dockEdge,
            "edgeOffset": root.dockEdgeOffset,
            "reserveSpace": root.dockReserveSpace,
            "iconSize": root.dockIconSize,
            "autoHide": root.dockAutoHide,
            "hideDelay": root.dockHideDelay,
            "revealDelay": root.dockRevealDelay,
            "monitors": root.dockMonitors,
            "windowFilter": root.dockWindowFilter,
            "pinned": root.dockPinned
        });
    }

    function setDockEnabled(enabled) {
        root._markDockModified("enabled");
        root.dockEnabled = enabled;
        saveDockConfig();
    }

    function setDockFloating(floating) {
        root._markDockModified("floating");
        root.dockFloating = floating;
        saveDockConfig();
    }

    function setDockEdge(edge) {
        if (edge === "top" || edge === "bottom" || edge === "left" || edge === "right") {
            root._markDockModified("edge");
            root.dockEdge = edge;
            saveDockConfig();
        }
    }

    function setDockPosition(pos) {
        setDockEdge(pos);
    }

    function setDockEdgeOffset(offset) {
        root._markDockModified("edgeOffset");
        root.dockEdgeOffset = Math.max(0, Math.min(64, offset));
        saveDockConfig();
    }

    function setDockReserveSpace(reserve) {
        root._markDockModified("reserveSpace");
        root.dockReserveSpace = reserve;
        saveDockConfig();
    }

    function setDockIconSize(size) {
        root._markDockModified("iconSize");
        root.dockIconSize = Math.max(20, Math.min(128, size));
        saveDockConfig();
    }

    function setDockAutoHide(autoHide) {
        root._markDockModified("autoHide");
        root.dockAutoHide = autoHide;
        saveDockConfig();
    }

    function setDockHideDelay(delay) {
        root._markDockModified("hideDelay");
        root.dockHideDelay = Math.max(50, Math.min(2000, delay));
        saveDockConfig();
    }

    function setDockRevealDelay(delay) {
        root._markDockModified("revealDelay");
        root.dockRevealDelay = Math.max(0, Math.min(1000, delay));
        saveDockConfig();
    }

    function setDockWindowFilter(mode) {
        const norm = WindowFilter.normalizeMode(mode);
        if (norm === root.dockWindowFilter) return;
        root._markDockModified("windowFilter");
        root.dockWindowFilter = norm;
        saveDockConfig();
    }

    function setDockMonitors(m) {
        root._markDockModified("monitors");
        if (!m || m === "primary" || m === "default" || (Array.isArray(m) && m.length === 0)) {
            root.dockMonitors = "all";
        } else {
            root.dockMonitors = m;
        }
        saveDockConfig();
    }

    function toggleDockMonitor(screenName) {
        if (!screenName) return;
        const screens = Quickshell.screens || [];
        let currentList = [];
        if (root.dockMonitors === "all") {
            for (let i = 0; i < screens.length; i++) {
                currentList.push(screens[i].name);
            }
        } else if (Array.isArray(root.dockMonitors)) {
            currentList = root.dockMonitors.slice();
        } else if (typeof root.dockMonitors === "string") {
            currentList = [root.dockMonitors];
        }

        const idx = currentList.indexOf(screenName);
        if (idx !== -1) {
            if (currentList.length <= 1) {
                root.setDockMonitors("all");
                return;
            }
            currentList.splice(idx, 1);
        } else {
            currentList.push(screenName);
        }

        if (currentList.length >= screens.length && screens.length > 0) {
            root.setDockMonitors("all");
        } else {
            root.setDockMonitors(currentList);
        }
    }

    function isDockPinned(appId) {
        if (!appId || !root.dockPinned) return false;
        return findDockPinnedIndex(appId, root.dockPinned) !== -1;
    }

    function insertDockPinnedAt(appId, rawIndex) {
        const norm = normalizeDockAppId(appId);
        if (!norm) return false;
        const current = sanitizeDockPinned(root.dockPinned);
        if (findDockPinnedIndex(norm, current) !== -1) return false;
        if (typeof rawIndex !== "number" || !Number.isInteger(rawIndex) ||
            rawIndex < 0 || rawIndex > current.length) {
            return false;
        }
        current.splice(rawIndex, 0, norm);
        root._markDockModified("pinned");
        root.dockPinned = current;
        saveDockConfig();
        return true;
    }

    function toggleDockPinned(appId) {
        const norm = normalizeDockAppId(appId);
        if (!norm) return false;
        const current = sanitizeDockPinned(root.dockPinned);
        const idx = findDockPinnedIndex(norm, current);
        if (idx !== -1) {
            current.splice(idx, 1);
        } else {
            current.push(norm);
        }
        root._markDockModified("pinned");
        root.dockPinned = current;
        saveDockConfig();
        return true;
    }

    function resolveMoveStep(direction) {
        if (direction === -1 || direction === "left" || direction === "up" ||
            direction === "backward" || direction === "prev" || direction === "previous") {
            return -1;
        }
        if (direction === 1 || direction === "right" || direction === "down" ||
            direction === "forward" || direction === "next") {
            return 1;
        }
        return 0;
    }

    function canMoveDockPinned(appId, direction) {
        const step = resolveMoveStep(direction);
        if (step === 0) return false;
        const current = sanitizeDockPinned(root.dockPinned);
        const idx = findDockPinnedIndex(appId, current);
        if (idx === -1) return false;
        const targetIdx = idx + step;
        return targetIdx >= 0 && targetIdx < current.length;
    }

    function reorderDockPinned(fromIndex, toIndex) {
        if (typeof fromIndex !== "number" || typeof toIndex !== "number" ||
            !Number.isInteger(fromIndex) || !Number.isInteger(toIndex)) {
            return false;
        }
        const current = sanitizeDockPinned(root.dockPinned);
        if (fromIndex < 0 || fromIndex >= current.length ||
            toIndex < 0 || toIndex >= current.length ||
            fromIndex === toIndex) {
            return false;
        }
        const moved = current.splice(fromIndex, 1)[0];
        current.splice(toIndex, 0, moved);
        root._markDockModified("pinned");
        root.dockPinned = current;
        saveDockConfig();
        return true;
    }

    function reorderDockPinnedByAppId(fromAppId, toAppId) {
        const current = sanitizeDockPinned(root.dockPinned);
        const fromIdx = findDockPinnedIndex(fromAppId, current);
        const toIdx = findDockPinnedIndex(toAppId, current);
        if (fromIdx === -1 || toIdx === -1 || fromIdx === toIdx) {
            return false;
        }
        return reorderDockPinned(fromIdx, toIdx);
    }

    function moveDockPinned(appId, direction) {
        const step = resolveMoveStep(direction);
        if (step === 0) return false;
        const current = sanitizeDockPinned(root.dockPinned);
        const fromIdx = findDockPinnedIndex(appId, current);
        if (fromIdx === -1) return false;
        const toIdx = fromIdx + step;
        if (toIdx < 0 || toIdx >= current.length) return false;
        return reorderDockPinned(fromIdx, toIdx);
    }

    function moveDockPinnedLeft(appId) {
        return moveDockPinned(appId, "left");
    }

    function moveDockPinnedRight(appId) {
        return moveDockPinned(appId, "right");
    }
}
