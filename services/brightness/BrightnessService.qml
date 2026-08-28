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

    signal osdPulse()

    // Query brightness from KDE ScreenBrightness D-Bus service
    Process {
        id: brightnessReader
        command: ["qdbus6", "org.kde.ScreenBrightness", "/org/kde/ScreenBrightness/display1", "org.kde.ScreenBrightness.Display.Brightness"]
        property string buf: ""
        stdout: SplitParser {
            onRead: data => { brightnessReader.buf += data; }
        }
        onExited: exitCode => {
            if (exitCode === 0 && brightnessReader.buf.trim().length > 0) {
                const val = parseInt(brightnessReader.buf.trim(), 10);
                if (!isNaN(val)) {
                    // Max is 10000 on KDE ScreenBrightness
                    const ratio = Math.max(0.0, Math.min(1.0, val / 10000.0));
                    if (Math.abs(root.brightness - ratio) > 0.01) {
                        root.brightness = ratio;
                        root.osdPulse();
                    }
                    root.supported = true;
                }
            } else {
                // Fallback to display0 or sysfs
                sysfsReader.running = true;
            }
            brightnessReader.buf = "";
        }
    }

    // Fallback sysfs reader
    Process {
        id: sysfsReader
        command: ["cat", "/sys/class/backlight/intel_backlight/brightness"]
        property string buf: ""
        stdout: SplitParser {
            onRead: data => { sysfsReader.buf += data; }
        }
        onExited: exitCode => {
            if (exitCode === 0 && sysfsReader.buf.trim().length > 0) {
                const val = parseInt(sysfsReader.buf.trim(), 10);
                if (!isNaN(val)) {
                    // Check max
                    root.brightness = Math.max(0.0, Math.min(1.0, val / 100000.0));
                    root.supported = true;
                }
            } else {
                root.supported = false;
            }
            sysfsReader.buf = "";
        }
    }

    function refresh() {
        if (!brightnessReader.running) {
            brightnessReader.buf = "";
            brightnessReader.running = true;
        }
    }

    function setBrightness(ratio) {
        const clamped = Math.max(0.0, Math.min(1.0, ratio));
        root.brightness = clamped;
        root.osdPulse();
        // Adjust via KDE ScreenBrightness D-Bus
        Quickshell.execDetached(["qdbus6", "org.kde.ScreenBrightness", "/org/kde/ScreenBrightness", "org.kde.ScreenBrightness.AdjustBrightnessRatio", (clamped - root.brightness).toString(), "0"]);
    }

    function increaseBrightness(step) {
        const delta = step || 0.05;
        const target = Math.min(1.0, root.brightness + delta);
        root.brightness = target;
        root.osdPulse();
        Quickshell.execDetached(["qdbus6", "org.kde.ScreenBrightness", "/org/kde/ScreenBrightness", "org.kde.ScreenBrightness.AdjustBrightnessRatio", delta.toString(), "0"]);
    }

    function decreaseBrightness(step) {
        const delta = step || 0.05;
        const target = Math.max(0.0, root.brightness - delta);
        root.brightness = target;
        root.osdPulse();
        Quickshell.execDetached(["qdbus6", "org.kde.ScreenBrightness", "/org/kde/ScreenBrightness", "org.kde.ScreenBrightness.AdjustBrightnessRatio", (-delta).toString(), "0"]);
    }

    Component.onCompleted: {
        refresh();
    }
}
