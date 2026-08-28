pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import "../core/Log.js" as Log

Singleton {
    id: root

    // Compositor detection
    readonly property string xdgDesktop: Quickshell.env("XDG_CURRENT_DESKTOP") || ""
    readonly property string kdeSession: Quickshell.env("KDE_FULL_SESSION") || ""
    readonly property bool isKWin: xdgDesktop.toLowerCase().indexOf("kde") !== -1 || kdeSession === "true"
    readonly property bool isWayland: (Quickshell.env("WAYLAND_DISPLAY") !== "") || (Quickshell.env("XDG_SESSION_TYPE") === "wayland")

    // Outputs / Monitors (Dynamic discovery, never hardcoded)
    property string activeOutputName: ""
    readonly property var screens: Quickshell.screens
    property int screenCount: Quickshell.screens ? Quickshell.screens.length : 1

    // Virtual Desktops
    property var desktops: []
    property string currentDesktopId: ""
    property int currentDesktopIndex: 0
    property int desktopCount: 1

    // Windows & Toplevels
    property var runningWindows: []
    property string activeWindowTitle: ""
    property string activeWindowAppId: ""

    // Desktop mode
    property bool showingDesktop: false

    // Signals for UI reactivity
    signal desktopChanged(int index, string id)
    signal desktopsUpdated()
    signal activeOutputChanged(string outputName)

    function refreshActiveOutput() {
        if (!root.isKWin || activeOutputProc.running) return;
        activeOutputProc.buf = "";
        activeOutputProc.running = true;
    }

    Process {
        id: activeOutputProc
        command: ["qdbus6", "org.kde.KWin", "/KWin", "org.kde.KWin.activeOutputName"]
        property string buf: ""
        stdout: SplitParser {
            onRead: data => { activeOutputProc.buf += data; }
        }
        onExited: exitCode => {
            if (exitCode === 0 && activeOutputProc.buf.trim().length > 0) {
                const name = activeOutputProc.buf.trim();
                if (root.activeOutputName !== name) {
                    root.activeOutputName = name;
                    root.activeOutputChanged(name);
                }
            }
            activeOutputProc.buf = "";
        }
    }

    // --- Virtual Desktops Implementation ---
    function refreshDesktops() {
        if (!root.isKWin) return;
        if (!desktopsListProc.running) {
            desktopsListProc.buf = "";
            desktopsListProc.running = true;
        }
        if (!currentDesktopProc.running) {
            currentDesktopProc.buf = "";
            currentDesktopProc.running = true;
        }
    }

    Process {
        id: currentDesktopProc
        command: ["qdbus6", "org.kde.KWin", "/VirtualDesktopManager", "org.kde.KWin.VirtualDesktopManager.current"]
        property string buf: ""
        stdout: SplitParser {
            onRead: data => { currentDesktopProc.buf += data; }
        }
        onExited: exitCode => {
            if (exitCode === 0) {
                const curId = currentDesktopProc.buf.trim();
                if (curId.length > 0 && curId !== root.currentDesktopId) {
                    root.currentDesktopId = curId;
                    root.updateActiveDesktopState();
                }
            }
            currentDesktopProc.buf = "";
        }
    }

    Process {
        id: desktopsListProc
        command: ["qdbus6", "--literal", "org.kde.KWin", "/VirtualDesktopManager", "org.kde.KWin.VirtualDesktopManager.desktops"]
        property string buf: ""
        stdout: SplitParser {
            onRead: data => { desktopsListProc.buf += data; }
        }
        onExited: exitCode => {
            if (exitCode === 0 && desktopsListProc.buf.trim().length > 0) {
                root.parseDesktopsLiteral(desktopsListProc.buf);
            }
            desktopsListProc.buf = "";
        }
    }

    function parseDesktopsLiteral(raw) {
        // Raw matches: [Variant: [Argument: a(uss) {[Argument: (uss) 0, "guid-1", "Desktop 1"], ...}]]
        // or a(iss) signatures depending on KWin version
        try {
            const list = [];
            const regex = /\[Argument:\s*\([ui]ss\)\s*(\d+),\s*"([^"]+)",\s*"([^"]+)"\]/g;
            let match;
            while ((match = regex.exec(raw)) !== null) {
                const idx = parseInt(match[1]);
                const id = match[2];
                const name = match[3];
                list.push({
                    index: idx,
                    id: id,
                    name: name,
                    active: (id === root.currentDesktopId)
                });
            }

            if (list.length === 0) {
                // Fallback for simple count
                for (let i = 0; i < Math.max(1, root.desktopCount); i++) {
                    list.push({
                        index: i,
                        id: "desktop-" + (i + 1),
                        name: "Desktop " + (i + 1),
                        active: (i === root.currentDesktopIndex)
                    });
                }
            }

            root.desktops = list;
            root.desktopCount = list.length;
            root.updateActiveDesktopState();
            root.desktopsUpdated();
        } catch (e) {
            Log.warn("KWinService", "Error parsing desktops DBus literal: " + e);
        }
    }

    function updateActiveDesktopState() {
        let foundIndex = 0;
        const updated = [];
        for (let i = 0; i < root.desktops.length; i++) {
            const d = root.desktops[i];
            const isActive = (d.id === root.currentDesktopId) || (root.currentDesktopId === "" && i === 0);
            if (isActive) foundIndex = d.index !== undefined ? d.index : i;
            updated.push({
                index: d.index !== undefined ? d.index : i,
                id: d.id,
                name: d.name,
                active: isActive
            });
        }
        root.desktops = updated;
        root.currentDesktopIndex = foundIndex;
        root.desktopChanged(foundIndex, root.currentDesktopId);
    }

    function setCurrentDesktop(idOrIndex) {
        if (!root.isKWin) return;
        if (typeof idOrIndex === "number") {
            Quickshell.execDetached(["qdbus6", "org.kde.KWin", "/KWin", "org.kde.KWin.setCurrentDesktop", String(idOrIndex + 1)]);
        } else if (typeof idOrIndex === "string") {
            Quickshell.execDetached(["qdbus6", "org.kde.KWin", "/VirtualDesktopManager", "org.kde.KWin.VirtualDesktopManager.current", idOrIndex]);
            root.currentDesktopId = idOrIndex;
            root.updateActiveDesktopState();
        }
        refreshDesktops();
    }

    function nextDesktop() {
        if (!root.isKWin) return;
        Quickshell.execDetached(["qdbus6", "org.kde.KWin", "/KWin", "org.kde.KWin.nextDesktop"]);
        desktopRefreshTimer.restart();
    }

    function previousDesktop() {
        if (!root.isKWin) return;
        Quickshell.execDetached(["qdbus6", "org.kde.KWin", "/KWin", "org.kde.KWin.previousDesktop"]);
        desktopRefreshTimer.restart();
    }

    function createDesktop(name) {
        if (!root.isKWin) return;
        const nextPos = root.desktops.length;
        Quickshell.execDetached(["qdbus6", "org.kde.KWin", "/VirtualDesktopManager", "org.kde.KWin.VirtualDesktopManager.createDesktop", String(nextPos), name || ("Desktop " + (nextPos + 1))]);
        desktopRefreshTimer.restart();
    }

    function toggleShowDesktop() {
        if (!root.isKWin) return;
        root.showingDesktop = !root.showingDesktop;
        Quickshell.execDetached(["qdbus6", "org.kde.KWin", "/KWin", "org.kde.KWin.showDesktop", root.showingDesktop ? "true" : "false"]);
    }

    function openKdeSettings(moduleName) {
        if (moduleName && moduleName.length > 0) {
            Quickshell.execDetached(["kcmshell6", moduleName]);
        } else {
            Quickshell.execDetached(["systemsettings"]);
        }
    }

    function lockSession() {
        Quickshell.execDetached(["loginctl", "lock-session"]);
    }

    // Debounce timer for immediate user-invoked desktop transitions
    Timer {
        id: desktopRefreshTimer
        interval: 150
        repeat: false
        onTriggered: root.refreshDesktops()
    }

    // Documented Polling:
    // A lightweight 3000ms periodic refresh timer is maintained as an event fallback
    // to synchronize virtual desktop changes triggered externally (e.g. KWin global shortcuts,
    // edge gestures, or trackpad multi-finger swipes) that do not route through Quickshell.
    Timer {
        interval: 3000
        running: root.isKWin
        repeat: true
        onTriggered: {
            root.refreshDesktops();
            root.refreshActiveOutput();
        }
    }

    Component.onCompleted: {
        Log.info("KWinService", "Initialized KWin Adapter (Wayland: " + root.isWayland + ", Detected: " + root.isKWin + ")");
        if (root.isKWin) {
            root.refreshDesktops();
            root.refreshActiveOutput();
        }
    }
}
