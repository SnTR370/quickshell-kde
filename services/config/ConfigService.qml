pragma Singleton
import QtQuick
import Quickshell
import "../core"
import "../core/Log.js" as Log

Singleton {
    id: root

    readonly property string homeDir: Quickshell.env("HOME") || ""
    readonly property string userConfigDir: (Quickshell.env("XDG_CONFIG_HOME") || (homeDir + "/.config")) + "/quickshell-kde"
    readonly property string barConfigFile: userConfigDir + "/bar_config.json"
    readonly property string dockConfigFile: userConfigDir + "/dock_config.json"

    // Bar properties
    property string barPosition: "top"
    property real barHeight: 44
    property var barLeft: ["launcher", "workspaces"]
    property var barCenter: ["clock"]
    property var barRight: ["media", "tray", "network", "battery", "audio", "power"]
    property real barOpacity: 0.92

    // Dock properties
    property bool dockEnabled: true
    property string dockPosition: "bottom"
    property real dockIconSize: 44
    property var dockPinned: []

    // Notifications configuration (opt-in; false by default to prevent conflict with Plasma notification daemon)
    property bool notificationsEnabled: false

    // UI Overlay States
    property bool launcherVisible: false
    property bool settingsVisible: false
    property bool mediaPopupVisible: false

    function toggleLauncher() {
        root.launcherVisible = !root.launcherVisible;
    }

    function toggleSettings() {
        root.settingsVisible = !root.settingsVisible;
    }

    function toggleMediaPopup() {
        root.mediaPopupVisible = !root.mediaPopupVisible;
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
            "notificationsEnabled": false
        })
        onLoadedValue: (parsed, _) => {
            if (parsed.position) root.barPosition = parsed.position;
            if (parsed.height !== undefined) root.barHeight = parsed.height;
            if (parsed.left) root.barLeft = parsed.left;
            if (parsed.center) root.barCenter = parsed.center;
            if (parsed.right) root.barRight = parsed.right;
            if (parsed.opacity !== undefined) root.barOpacity = parsed.opacity;
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
            "pinned": []
        })
        onLoadedValue: (parsed, _) => {
            if (parsed.enabled !== undefined) root.dockEnabled = parsed.enabled;
            if (parsed.position) root.dockPosition = parsed.position;
            if (parsed.iconSize !== undefined) root.dockIconSize = parsed.iconSize;
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
            "notificationsEnabled": root.notificationsEnabled
        });
    }

    function setBarPosition(pos) {
        root.barPosition = pos;
        saveBarConfig();
    }

    function setBarHeight(h) {
        root.barHeight = h;
        saveBarConfig();
    }

    function setBarOpacity(op) {
        root.barOpacity = op;
        saveBarConfig();
    }

    function setNotificationsEnabled(enabled) {
        root.notificationsEnabled = enabled;
        saveBarConfig();
    }

    function saveDockConfig() {
        dockStore.save({
            "enabled": root.dockEnabled,
            "position": root.dockPosition,
            "iconSize": root.dockIconSize,
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
        root.dockIconSize = size;
        saveDockConfig();
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
