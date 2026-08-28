pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import "../core"
import "../core/Log.js" as Log
import "."

Singleton {
    id: root

    readonly property string homeDir: Quickshell.env("HOME") || ""
    readonly property string configDir: (Quickshell.env("XDG_CONFIG_HOME") || (homeDir + "/.config")) + "/quickshell-kde"
    readonly property string themeConfigFile: configDir + "/theme_config.json"

    property var availableThemes: [
        { id: "breeze-dark", name: "Breeze Dark" },
        { id: "catppuccin-mocha", name: "Catppuccin Mocha" },
        { id: "nord", name: "Nord" },
        { id: "tokyo-night", name: "Tokyo Night" }
    ]

    JsonStore {
        id: themeConfigStore
        path: root.themeConfigFile
        fallbackPath: Qt.resolvedUrl("../../config/theme_config.json").toString().replace(/^file:\/\//, "")
        defaultValue: ({ "activeTheme": "breeze-dark" })
        onLoadedValue: (parsed, _) => {
            if (parsed && parsed.activeTheme) {
                root.selectTheme(parsed.activeTheme);
            }
        }
    }

    function selectTheme(themeId) {
        // Load theme file safely using resolved path
        const themePath = Qt.resolvedUrl("../../themes/" + themeId + ".json").toString().replace(/^file:\/\//, "");
        themeReader.command = ["cat", themePath];
        themeReader.targetThemeId = themeId;
        themeReader.buf = "";
        themeReader.running = true;
    }

    Process {
        id: themeReader
        property string targetThemeId: ""
        property string buf: ""
        stdout: SplitParser {
            onRead: data => { themeReader.buf += data; }
        }
        onExited: exitCode => {
            if (exitCode === 0 && themeReader.buf.trim().length > 0) {
                try {
                    const themeData = JSON.parse(themeReader.buf);
                    Theme.applyTheme(themeData);
                    Log.info("ThemeService", "Applied theme: " + themeReader.targetThemeId);
                } catch (e) {
                    Log.error("ThemeService", "Failed to parse theme json: " + e);
                }
            }
            themeReader.buf = "";
        }
    }

    function saveThemeSelection(themeId) {
        selectTheme(themeId);
        themeConfigStore.save({ "activeTheme": themeId });
    }

    Component.onCompleted: {
        selectTheme("breeze-dark");
    }
}
