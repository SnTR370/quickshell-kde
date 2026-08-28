pragma Singleton
import QtQuick
import Quickshell
import "../core"
import "../kwin"

Singleton {
    id: root

    // Config file paths
    readonly property string configDir: Quickshell.env("XDG_CONFIG_HOME") ? (Quickshell.env("XDG_CONFIG_HOME") + "/quickshell-kde") : (Quickshell.env("HOME") + "/.config/quickshell-kde")
    readonly property string barConfigFile: configDir + "/bar_config.json"
    readonly property string dockConfigFile: configDir + "/dock_config.json"

    // Bar state
    property string barPosition: "top"
    property int barHeight: 44
    property var barLeft: ["launcher", "workspaces"]
    property var barCenter: ["clock"]
    property var barRight: ["media", "tray", "network", "battery", "audio", "power"]
    property real barOpacity: 0.92
    property var barMonitors: "all"
    property bool blurEnabled: true
    property bool notificationsEnabled: false

    // Dock state
    property bool dockEnabled: true
    property string dockPosition: "bottom"
    property int dockIconSize: 44
    property bool dockAutoHide: false
    property int dockHideDelay: 350
    property int dockRevealDelay: 120
    property var dockMonitors: "all"
    property var dockPinned: []

    // Window Visibility
    property bool launcherVisible: false
    property bool settingsVisible: false
    property bool mediaPopupVisible: false

    function toggleLauncher() {
        root.launcherVisible = !root.launcherVisible;
        if (root.launcherVisible) {
            root.settingsVisible = false;
            root.mediaPopupVisible = false;
        }
    }

    function toggleSettings() {
        root.settingsVisible = !root.settingsVisible;
        if (root.settingsVisible) {
            root.launcherVisible = false;
            root.mediaPopupVisible = false;
        }
    }

    function toggleMediaPopup() {
        root.mediaPopupVisible = !root.mediaPopupVisible;
        if (root.mediaPopupVisible) {
            root.launcherVisible = false;
            root.settingsVisible = false;
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
            "position": "top",
            "height": 44,
            "left": ["launcher", "workspaces"],
            "center": ["clock"],
            "right": ["media", "tray", "network", "battery", "audio", "power"],
            "opacity": 0.92,
            "monitors": "all",
            "blur": true,
            "notificationsEnabled": false
        })
        onLoadedValue: (parsed, _) => {
            if (parsed.position) root.barPosition = parsed.position;
            if (parsed.height !== undefined) root.barHeight = Math.max(24, Math.min(120, parsed.height));
            if (parsed.left) root.barLeft = parsed.left;
            if (parsed.center) root.barCenter = parsed.center;
            if (parsed.right) root.barRight = parsed.right;
            if (parsed.opacity !== undefined) root.barOpacity = Math.max(0.1, Math.min(1.0, parsed.opacity));
            if (parsed.monitors !== undefined) {
                root.barMonitors = (parsed.monitors === "primary" || parsed.monitors === "default") ? "all" : parsed.monitors;
            }
            if (parsed.blur !== undefined) root.blurEnabled = parsed.blur;
            if (parsed.notificationsEnabled !== undefined) root.notificationsEnabled = parsed.notificationsEnabled;
        }
    }

    JsonStore {
        id: dockStore
        path: root.dockConfigFile
        fallbackPath: Qt.resolvedUrl("../../config/dock_config.json").toString().replace(/^file:\/\//, "")
        defaultValue: ({
            "enabled": true,
            "position": "bottom",
            "iconSize": 44,
            "autoHide": false,
            "hideDelay": 350,
            "revealDelay": 120,
            "monitors": "all",
            "pinned": []
        })
        onLoadedValue: (parsed, _) => {
            if (parsed.enabled !== undefined) root.dockEnabled = parsed.enabled;
            if (parsed.position) root.dockPosition = parsed.position;
            if (parsed.iconSize !== undefined) root.dockIconSize = Math.max(20, Math.min(128, parsed.iconSize));
            if (parsed.autoHide !== undefined) root.dockAutoHide = parsed.autoHide;
            if (parsed.hideDelay !== undefined) root.dockHideDelay = Math.max(50, Math.min(2000, parsed.hideDelay));
            if (parsed.revealDelay !== undefined) root.dockRevealDelay = Math.max(0, Math.min(1000, parsed.revealDelay));
            if (parsed.monitors !== undefined) {
                root.dockMonitors = (parsed.monitors === "primary" || parsed.monitors === "default") ? "all" : parsed.monitors;
            }
            if (parsed.pinned) root.dockPinned = parsed.pinned;
        }
    }

    function saveBarConfig() {
        barStore.save({
            "position": root.barPosition,
            "height": root.barHeight,
            "left": root.barLeft,
            "center": root.barCenter,
            "right": root.barRight,
            "opacity": root.barOpacity,
            "monitors": root.barMonitors,
            "blur": root.blurEnabled,
            "notificationsEnabled": root.notificationsEnabled
        });
    }

    function setBarPosition(pos) {
        root.barPosition = pos;
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
            // Prevent removing the last selected monitor (lockout prevention)
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

    function saveDockConfig() {
        dockStore.save({
            "enabled": root.dockEnabled,
            "position": root.dockPosition,
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

    function setDockPosition(pos) {
        root.dockPosition = pos;
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
            // Prevent removing the last selected monitor (lockout prevention)
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
        return root.dockPinned.indexOf(appId) !== -1;
    }

    function toggleDockPinned(appId) {
        if (!appId) return;
        const current = root.dockPinned ? root.dockPinned.slice() : [];
        const idx = current.indexOf(appId);
        if (idx !== -1) {
            current.splice(idx, 1);
        } else {
            current.push(appId);
        }
        root.dockPinned = current;
        saveDockConfig();
    }
}
