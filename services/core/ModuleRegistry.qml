pragma Singleton
import QtQuick
import Quickshell

Singleton {
    id: root

    // Central registry of all supported desktop modules
    readonly property var registeredModules: [
        {
            id: "launcher",
            name: "Application Launcher",
            icon: "start-here-kde",
            description: "Search and launch desktop applications",
            defaultSlot: "left"
        },
        {
            id: "workspaces",
            name: "Virtual Desktops",
            icon: "preferences-desktop-workspaces",
            description: "KWin virtual desktop indicator and switcher",
            defaultSlot: "left"
        },
        {
            id: "clock",
            name: "Clock & Date",
            icon: "preferences-system-time",
            description: "Real-time clock display with date and calendar settings",
            defaultSlot: "center"
        },
        {
            id: "media",
            name: "Media Player",
            icon: "media-playback-start",
            description: "Active MPRIS media playback controls and metadata",
            defaultSlot: "right"
        },
        {
            id: "tray",
            name: "System Tray",
            icon: "system-run",
            description: "Freedesktop StatusNotifierItem system tray icons",
            defaultSlot: "right"
        },
        {
            id: "network",
            name: "Network",
            icon: "network-wireless-connected-100",
            description: "Ethernet and Wi-Fi connection indicator",
            defaultSlot: "right"
        },
        {
            id: "battery",
            name: "Battery & Power",
            icon: "battery-100",
            description: "UPower battery percentage and AC charging state",
            defaultSlot: "right"
        },
        {
            id: "audio",
            name: "Audio Control",
            icon: "audio-volume-high",
            description: "PipeWire volume display, scroll adjuster, and mute toggle",
            defaultSlot: "right"
        },
        {
            id: "brightness",
            name: "Display Brightness",
            icon: "display-brightness-high",
            description: "Display backlight level indicator and per-display adjuster",
            defaultSlot: "right"
        },
        {
            id: "power",
            name: "Power Menu",
            icon: "system-shutdown",
            description: "Session management (lock, logout, restart, shut down)",
            defaultSlot: "right"
        }
    ]

    function getModule(moduleId) {
        if (!moduleId) return null;
        for (let i = 0; i < root.registeredModules.length; i++) {
            if (root.registeredModules[i].id === moduleId) {
                return root.registeredModules[i];
            }
        }
        return null;
    }

    function isValidModule(moduleId) {
        return root.getModule(moduleId) !== null;
    }

    function getAvailableModuleIds() {
        const ids = [];
        for (let i = 0; i < root.registeredModules.length; i++) {
            ids.push(root.registeredModules[i].id);
        }
        return ids;
    }

    function sanitizeSlotList(slotArray, fallbackList) {
        if (!Array.isArray(slotArray)) return fallbackList || [];
        const result = [];
        for (let i = 0; i < slotArray.length; i++) {
            const modId = slotArray[i];
            if (typeof modId === "string" && root.isValidModule(modId)) {
                if (result.indexOf(modId) === -1) {
                    result.push(modId);
                }
            }
        }
        return result;
    }
}
