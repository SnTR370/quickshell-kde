pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import "../core/Log.js" as Log

Singleton {
    id: root

    property real brightness: 1.0
    property int percentage: Math.round(brightness * 100)
    property bool supported: true
    property var displayPaths: []
    property int maxBrightness: 10000
    property string activeDisplayPath: ""

    signal osdPulse()

    // 1. Discover active displays from KDE ScreenBrightness
    Process {
        id: displayDiscoverer
        command: ["qdbus6", "org.kde.ScreenBrightness", "/org/kde/ScreenBrightness", "org.kde.ScreenBrightness.DisplaysDBusNames"]
        property string buf: ""
        stdout: SplitParser {
            onRead: data => { displayDiscoverer.buf += data; }
        }
        onExited: exitCode => {
            if (exitCode === 0 && displayDiscoverer.buf.trim().length > 0) {
                const names = displayDiscoverer.buf.trim().split("\n").map(s => s.trim()).filter(s => s.length > 0);
                root.displayPaths = names;
                if (names.length > 0) {
                    root.activeDisplayPath = "/org/kde/ScreenBrightness/" + names[0];
                    displayPropsReader.command = ["qdbus6", "org.kde.ScreenBrightness", root.activeDisplayPath, "org.kde.ScreenBrightness.Display.MaxBrightness"];
                    displayPropsReader.running = true;
                }
                root.supported = true;
            } else {
                sysfsDiscoverer.running = true;
            }
            displayDiscoverer.buf = "";
        }
    }

    // 2. Read MaxBrightness for active display
    Process {
        id: displayPropsReader
        property string buf: ""
        stdout: SplitParser {
            onRead: data => { displayPropsReader.buf += data; }
        }
        onExited: exitCode => {
            if (exitCode === 0 && displayPropsReader.buf.trim().length > 0) {
                const maxVal = parseInt(displayPropsReader.buf.trim(), 10);
                if (!isNaN(maxVal) && maxVal > 0) {
                    root.maxBrightness = maxVal;
                }
            }
            displayPropsReader.buf = "";
            currentBrightnessReader.command = ["qdbus6", "org.kde.ScreenBrightness", root.activeDisplayPath, "org.kde.ScreenBrightness.Display.Brightness"];
            currentBrightnessReader.running = true;
        }
    }

    // 3. Read initial current Brightness
    Process {
        id: currentBrightnessReader
        property string buf: ""
        stdout: SplitParser {
            onRead: data => { currentBrightnessReader.buf += data; }
        }
        onExited: exitCode => {
            if (exitCode === 0 && currentBrightnessReader.buf.trim().length > 0) {
                const curVal = parseInt(currentBrightnessReader.buf.trim(), 10);
                if (!isNaN(curVal) && root.maxBrightness > 0) {
                    root.brightness = Math.max(0.0, Math.min(1.0, curVal / root.maxBrightness));
                }
            }
            currentBrightnessReader.buf = "";
        }
    }

    // 4. Real-time event-driven listener for brightness changes (hardware keys / Plasma UI)
    Process {
        id: dbusSignalListener
        command: ["dbus-monitor", "type='signal',interface='org.kde.ScreenBrightness',member='BrightnessChanged'"]
        running: true
        stdout: SplitParser {
            onRead: line => {
                // Line format: int32 <value>
                const match = line.match(/int32\s+(\d+)/);
                if (match && match[1]) {
                    const newVal = parseInt(match[1], 10);
                    if (!isNaN(newVal) && root.maxBrightness > 0) {
                        const ratio = Math.max(0.0, Math.min(1.0, newVal / root.maxBrightness));
                        if (Math.abs(root.brightness - ratio) > 0.005) {
                            root.brightness = ratio;
                            root.osdPulse();
                        }
                    }
                }
            }
        }
    }

    // 5. Sysfs dynamic fallback if D-Bus service is unavailable
    Process {
        id: sysfsDiscoverer
        command: ["sh", "-c", "for d in /sys/class/backlight/*; do if [ -d \"$d\" ]; then cur=$(cat \"$d/actual_brightness\" 2>/dev/null); max=$(cat \"$d/max_brightness\" 2>/dev/null); echo \"$cur:$max\"; break; fi; done"]
        property string buf: ""
        stdout: SplitParser {
            onRead: data => { sysfsDiscoverer.buf += data; }
        }
        onExited: exitCode => {
            if (exitCode === 0 && sysfsDiscoverer.buf.trim().length > 0) {
                const parts = sysfsDiscoverer.buf.trim().split(":");
                if (parts.length === 2) {
                    const cur = parseInt(parts[0], 10);
                    const max = parseInt(parts[1], 10);
                    if (!isNaN(cur) && !isNaN(max) && max > 0) {
                        root.maxBrightness = max;
                        root.brightness = Math.max(0.0, Math.min(1.0, cur / max));
                        root.supported = true;
                    }
                }
            } else {
                root.supported = false;
            }
            sysfsDiscoverer.buf = "";
        }
    }

    function refresh() {
        if (!displayDiscoverer.running) {
            displayDiscoverer.buf = "";
            displayDiscoverer.running = true;
        }
    }

    function setBrightness(ratio) {
        const clamped = Math.max(0.0, Math.min(1.0, ratio));
        const delta = clamped - root.brightness;
        root.brightness = clamped;
        root.osdPulse();

        if (root.displayPaths.length > 0) {
            // Adjust ratio across KDE displays
            Quickshell.execDetached(["qdbus6", "org.kde.ScreenBrightness", "/org/kde/ScreenBrightness", "org.kde.ScreenBrightness.AdjustBrightnessRatio", delta.toString(), "0"]);
        }
    }

    function increaseBrightness(step) {
        const delta = step || 0.05;
        const target = Math.min(1.0, root.brightness + delta);
        const actualDelta = target - root.brightness;
        root.brightness = target;
        root.osdPulse();
        Quickshell.execDetached(["qdbus6", "org.kde.ScreenBrightness", "/org/kde/ScreenBrightness", "org.kde.ScreenBrightness.AdjustBrightnessRatio", actualDelta.toString(), "0"]);
    }

    function decreaseBrightness(step) {
        const delta = step || 0.05;
        const target = Math.max(0.0, root.brightness - delta);
        const actualDelta = target - root.brightness;
        root.brightness = target;
        root.osdPulse();
        Quickshell.execDetached(["qdbus6", "org.kde.ScreenBrightness", "/org/kde/ScreenBrightness", "org.kde.ScreenBrightness.AdjustBrightnessRatio", actualDelta.toString(), "0"]);
    }

    Component.onCompleted: {
        refresh();
    }
}
