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

    // The theme id is substituted into a file path under themes/ and read
    // by a process; only a strict id charset is accepted (no separators,
    // no traversal, no absolute paths). theme_config.json is user-writable,
    // so this must not be trusted blindly.
    function isValidThemeId(themeId) {
        if (typeof themeId !== "string") return false;
        const id = themeId.trim();
        if (id.length === 0 || id.length > 64) return false;
        if (!/^[a-zA-Z0-9][a-zA-Z0-9._-]*$/.test(id)) return false;
        return id.indexOf("..") === -1;
    }

    function selectTheme(themeId) {
        if (!isValidThemeId(themeId)) {
            Log.warn("ThemeService", "Rejected invalid theme id: " + themeId);
            return;
        }
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
        if (!isValidThemeId(themeId)) {
            Log.warn("ThemeService", "Refused to save invalid theme id: " + themeId);
            return;
        }
        selectTheme(themeId);
        themeConfigStore.save({ "activeTheme": themeId });
    }

    Component.onCompleted: {
        selectTheme("breeze-dark");
    }
}
