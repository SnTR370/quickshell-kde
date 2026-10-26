pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Services.SystemTray
import "../core"
import "../kwin"

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
    property var dockPinned: []

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
            "height": 44,
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
        onLoadedValue: (parsed, _) => {
            if (parsed.enabled !== undefined) root.barEnabled = parsed.enabled;
            if (parsed.floating !== undefined) root.barFloating = parsed.floating;
            if (parsed.edge) root.barEdge = parsed.edge;
            else if (parsed.position) root.barEdge = parsed.position;
            if (parsed.edgeOffset !== undefined) root.barEdgeOffset = Math.max(0, Math.min(64, parsed.edgeOffset));
            if (parsed.reserveSpace !== undefined) root.barReserveSpace = parsed.reserveSpace;
            if (parsed.height !== undefined) root.barHeight = Math.max(24, Math.min(120, parsed.height));
            if (parsed.left) root.barLeft = ModuleRegistry.sanitizeSlotList(parsed.left, root.barLeft);
            if (parsed.center) root.barCenter = ModuleRegistry.sanitizeSlotList(parsed.center, root.barCenter);
            if (parsed.right) root.barRight = ModuleRegistry.sanitizeSlotList(parsed.right, root.barRight);
            if (parsed.controlCenterMigrated === true) {
                root.controlCenterMigrated = true;
            } else {
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
            if (parsed.opacity !== undefined) root.barOpacity = Math.max(0.1, Math.min(1.0, parsed.opacity));
            if (parsed.monitors !== undefined) {
                root.barMonitors = (parsed.monitors === "primary" || parsed.monitors === "default") ? "all" : parsed.monitors;
            }
            if (parsed.blur !== undefined) root.blurEnabled = parsed.blur;
            if (parsed.notificationsEnabled !== undefined) root.notificationsEnabled = parsed.notificationsEnabled;
            if (parsed.trayItemPolicies && typeof parsed.trayItemPolicies === "object" && !Array.isArray(parsed.trayItemPolicies)) {
                const cleanPolicies = {};
                for (const k in parsed.trayItemPolicies) {
                    const key = String(k || "").trim();
                    if (key.length > 0) {
                        cleanPolicies[key] = root.normalizeTrayPolicy(parsed.trayItemPolicies[k]);
                    }
                }
                root.trayItemPolicies = cleanPolicies;
            }
        }
        property bool saveInFlight: false
        property bool savePending: false
        onSavedValue: {
            barStore.saveInFlight = false;
            if (barStore.savePending) {
                barStore.savePending = false;
                root.saveBarConfig();
            }
        }
        onFailed: (phase, _, __) => {
            if (phase === "write" || phase === "serialize") {
                barStore.saveInFlight = false;
                if (barStore.savePending) {
                    barStore.savePending = false;
                    root.saveBarConfig();
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
            "pinned": []
        })
        onLoadedValue: (parsed, _) => {
            if (parsed.enabled !== undefined) root.dockEnabled = parsed.enabled;
            if (parsed.floating !== undefined) root.dockFloating = parsed.floating;
            if (parsed.edge) root.dockEdge = parsed.edge;
            else if (parsed.position) root.dockEdge = parsed.position;
            if (parsed.edgeOffset !== undefined) root.dockEdgeOffset = Math.max(0, Math.min(64, parsed.edgeOffset));
            if (parsed.reserveSpace !== undefined) root.dockReserveSpace = parsed.reserveSpace;
            if (parsed.iconSize !== undefined) root.dockIconSize = Math.max(20, Math.min(128, parsed.iconSize));
            if (parsed.autoHide !== undefined) root.dockAutoHide = parsed.autoHide;
            if (parsed.hideDelay !== undefined) root.dockHideDelay = Math.max(50, Math.min(2000, parsed.hideDelay));
            if (parsed.revealDelay !== undefined) root.dockRevealDelay = Math.max(0, Math.min(1000, parsed.revealDelay));
            if (parsed.monitors !== undefined) {
                root.dockMonitors = (parsed.monitors === "primary" || parsed.monitors === "default") ? "all" : parsed.monitors;
            }
            if (parsed.pinned) root.dockPinned = root.sanitizeDockPinned(parsed.pinned);
        }
        property bool saveInFlight: false
        property bool savePending: false
        onSavedValue: {
            dockStore.saveInFlight = false;
            if (dockStore.savePending) {
                dockStore.savePending = false;
                root.saveDockConfig();
            }
        }
        onFailed: (phase, _, __) => {
            if (phase === "write" || phase === "serialize") {
                dockStore.saveInFlight = false;
                if (dockStore.savePending) {
                    dockStore.savePending = false;
                    root.saveDockConfig();
                }
            }
        }
    }

    // --- Bar Operations ---
    function saveBarConfig() {
        if (barStore.saveInFlight) {
            barStore.savePending = true;
            return;
        }
        barStore.saveInFlight = true;
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
        root.trayItemPolicies = next;
        saveBarConfig();
    }

    function setBarEnabled(enabled) {
        root.barEnabled = enabled;
        saveBarConfig();
    }

    function setBarFloating(floating) {
        root.barFloating = floating;
        saveBarConfig();
    }

    function setBarEdge(edge) {
        if (edge === "top" || edge === "bottom" || edge === "left" || edge === "right") {
            root.barEdge = edge;
            saveBarConfig();
        }
    }

    function setBarPosition(pos) {
        setBarEdge(pos);
    }

    function setBarEdgeOffset(offset) {
        root.barEdgeOffset = Math.max(0, Math.min(64, offset));
        saveBarConfig();
    }

    function setBarReserveSpace(reserve) {
        root.barReserveSpace = reserve;
        saveBarConfig();
    }

    function setBarHeight(h) {
        root.barHeight = Math.max(24, Math.min(120, h));
        saveBarConfig();
    }

    function setBarOpacity(op) {
        root.barOpacity = Math.max(0.1, Math.min(1.0, op));
        saveBarConfig();
    }

    function setBarMonitors(m) {
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
        root.blurEnabled = b;
        saveBarConfig();
    }

    function setNotificationsEnabled(n) {
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
            lower === "application-x-executable" || lower.indexOf("window-") === 0) {
            return "";
        }
        return norm;
    }

    function dockAppIdsMatch(idA, idB) {
        const normA = normalizeDockAppId(idA).toLowerCase();
        const normB = normalizeDockAppId(idB).toLowerCase();
        return normA.length > 0 && normA === normB;
    }

    function sanitizeDockPinned(list) {
        if (!list || typeof list === "string" || list.length === undefined) return [];
        const clean = [];
        const seen = {};
        for (let i = 0; i < list.length; i++) {
            const norm = normalizeDockAppId(list[i]);
            if (!norm) continue;
            const key = norm.toLowerCase();
            if (!seen[key]) {
                seen[key] = true;
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
        return -1;
    }

    function saveDockConfig() {
        root.dockPinned = sanitizeDockPinned(root.dockPinned);
        if (dockStore.saveInFlight) {
            dockStore.savePending = true;
            return;
        }
        dockStore.saveInFlight = true;
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
            "pinned": root.dockPinned
        });
    }

    function setDockEnabled(enabled) {
        root.dockEnabled = enabled;
        saveDockConfig();
    }

    function setDockFloating(floating) {
        root.dockFloating = floating;
        saveDockConfig();
    }

    function setDockEdge(edge) {
        if (edge === "top" || edge === "bottom" || edge === "left" || edge === "right") {
            root.dockEdge = edge;
            saveDockConfig();
        }
    }

    function setDockPosition(pos) {
        setDockEdge(pos);
    }

    function setDockEdgeOffset(offset) {
        root.dockEdgeOffset = Math.max(0, Math.min(64, offset));
        saveDockConfig();
    }

    function setDockReserveSpace(reserve) {
        root.dockReserveSpace = reserve;
        saveDockConfig();
    }

    function setDockIconSize(size) {
        root.dockIconSize = Math.max(20, Math.min(128, size));
        saveDockConfig();
    }

    function setDockAutoHide(autoHide) {
        root.dockAutoHide = autoHide;
        saveDockConfig();
    }

    function setDockHideDelay(delay) {
        root.dockHideDelay = Math.max(50, Math.min(2000, delay));
        saveDockConfig();
    }

    function setDockRevealDelay(delay) {
        root.dockRevealDelay = Math.max(0, Math.min(1000, delay));
        saveDockConfig();
    }

    function setDockMonitors(m) {
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
