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
    property bool dockAutoHide: false
    property var dockPinned: ["org.kde.dolphin", "org.kde.konsole", "firefox", "code", "systemsettings"]

    // Launcher UI State
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
        defaultValue: ({
            "position": "top",
            "height": 44,
            "monitors": "all",
            "left": ["launcher", "workspaces"],
            "center": ["clock"],
            "right": ["media", "tray", "network", "battery", "audio", "power"]
        })
        onLoadedValue: (parsed, _) => {
            if (parsed.position) root.barPosition = parsed.position;
            if (parsed.height) root.barHeight = parsed.height;
            if (parsed.left) root.barLeft = parsed.left;
            if (parsed.center) root.barCenter = parsed.center;
            if (parsed.right) root.barRight = parsed.right;
        }
    }

    JsonStore {
        id: dockStore
        path: root.dockConfigFile
        defaultValue: ({
            "enabled": true,
            "position": "bottom",
            "iconSize": 44,
            "autoHide": false,
            "pinned": ["org.kde.dolphin", "org.kde.konsole", "firefox", "code", "systemsettings"]
        })
        onLoadedValue: (parsed, _) => {
            if (parsed.enabled !== undefined) root.dockEnabled = parsed.enabled;
            if (parsed.position) root.dockPosition = parsed.position;
            if (parsed.iconSize) root.dockIconSize = parsed.iconSize;
            if (parsed.autoHide !== undefined) root.dockAutoHide = parsed.autoHide;
            if (parsed.pinned) root.dockPinned = parsed.pinned;
        }
    }

    function setBarPosition(pos) {
        root.barPosition = pos;
        barStore.save({
            "position": pos,
            "height": root.barHeight,
            "left": root.barLeft,
            "center": root.barCenter,
            "right": root.barRight
        });
    }
}
