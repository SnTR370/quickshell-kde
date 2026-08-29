pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import "../core/Log.js" as Log

Singleton {
    id: root

    property real brightness: 1.0
    property int percentage: Math.round(brightness * 100)
    property var displays: []
    property var controlledDisplay: null
    property string controlledDisplayName: controlledDisplay ? (controlledDisplay.label || controlledDisplay.dbusName) : ""
    property var lastChangedDisplay: null

    property bool controllable: controlledDisplay !== null && controlledDisplay.maxBrightness > 0
    property bool sysfsReadable: false
    property bool supported: controllable || sysfsReadable
    property bool isReadOnly: sysfsReadable && !controllable

    signal osdPulse()

    // 1. Discover all displays and their exact properties from KDE ScreenBrightness
    Process {
        id: displayDiscoverer
        command: ["python3", Qt.resolvedUrl("discover_displays.py").toString().replace(/^file:\/\//, "")]
        running: true
        property string buf: ""
        stdout: SplitParser {
            onRead: data => { displayDiscoverer.buf += data; }
        }
        onExited: exitCode => {
            if (exitCode === 0 && displayDiscoverer.buf.trim().length > 0) {
                try {
                    const parsed = JSON.parse(displayDiscoverer.buf.trim());
                    if (Array.isArray(parsed) && parsed.length > 0) {
                        root.displays = parsed;
                        root.selectControlledDisplay();
                        Log.info("BrightnessService", "Discovered " + parsed.length + " displays: controlled=" + (root.controlledDisplay ? root.controlledDisplay.label : "none"));
                        displayDiscoverer.buf = "";
                        return;
                    }
                } catch (e) {
                    Log.warn("BrightnessService", "Failed to parse displays JSON: " + e);
                }
            }
            displayDiscoverer.buf = "";
            sysfsDiscoverer.running = true;
        }
    }

    function selectControlledDisplay() {
        if (!root.displays || root.displays.length === 0) {
            root.controlledDisplay = null;
            root.lastChangedDisplay = null;
            return;
        }

        // Policy: Prefer internal display (laptop panel), otherwise first valid display
        let selected = null;
        for (let i = 0; i < root.displays.length; i++) {
            if (root.displays[i].isInternal && root.displays[i].maxBrightness > 0) {
                selected = root.displays[i];
                break;
            }
        }
        if (!selected) {
            for (let i = 0; i < root.displays.length; i++) {
                if (root.displays[i].maxBrightness > 0) {
                    selected = root.displays[i];
                    break;
                }
            }
        }

        root.controlledDisplay = selected;
        if (selected && selected.maxBrightness > 0) {
            const ratio = Math.max(0.0, Math.min(1.0, selected.brightness / selected.maxBrightness));
            root.brightness = ratio;
            root.lastChangedDisplay = {
                dbusName: selected.dbusName,
                path: selected.path,
                label: selected.label,
                isInternal: selected.isInternal,
                brightness: selected.brightness,
                maxBrightness: selected.maxBrightness,
                ratio: ratio
            };
        }
    }

    // 2. Real-time event-driven listener for brightness changes & hotplug
    Process {
        id: dbusSignalListener
        command: ["dbus-monitor", "type='signal',interface='org.kde.ScreenBrightness'"]
        running: true
        property string signalBuf: ""
        stdout: SplitParser {
            onRead: data => {
                dbusSignalListener.signalBuf += data + "\n";

                // Parse and consume BrightnessChanged signals
                const bcRe = /member=BrightnessChanged\s+string\s+"([^"]+)"\s+int32\s+(\d+)/;
                let match;
                while ((match = bcRe.exec(dbusSignalListener.signalBuf)) !== null) {
                    const dName = match[1];
                    const bVal = parseInt(match[2], 10);
                    root.handleBrightnessChanged(dName, bVal);
                    // Slice consumed portion up to end of match
                    dbusSignalListener.signalBuf = dbusSignalListener.signalBuf.substring(match.index + match[0].length);
                }

                // Check for display hotplug signals
                if (dbusSignalListener.signalBuf.indexOf("member=DisplayAdded") !== -1 || dbusSignalListener.signalBuf.indexOf("member=DisplayRemoved") !== -1) {
                    dbusSignalListener.signalBuf = "";
                    root.refresh();
                }

                // Prevent unbounded buffer growth
                if (dbusSignalListener.signalBuf.length > 2048) {
                    dbusSignalListener.signalBuf = dbusSignalListener.signalBuf.slice(-512);
                }
            }
        }
    }

    property var lastSentAction: ({ dbusName: "", targetVal: -1, timestamp: 0 })

    function handleBrightnessChanged(displayDbusName, newBrightness) {
        if (!root.displays) return;

        let matched = null;
        for (let i = 0; i < root.displays.length; i++) {
            if (root.displays[i].dbusName === displayDbusName) {
                root.displays[i].brightness = newBrightness;
                matched = root.displays[i];
                break;
            }
        }

        if (matched && matched.maxBrightness > 0) {
            const ratio = Math.max(0.0, Math.min(1.0, newBrightness / matched.maxBrightness));
            root.lastChangedDisplay = {
                dbusName: matched.dbusName,
                path: matched.path,
                label: matched.label,
                isInternal: matched.isInternal,
                brightness: newBrightness,
                maxBrightness: matched.maxBrightness,
                ratio: ratio
            };

            if (root.controlledDisplay && root.controlledDisplay.dbusName === displayDbusName) {
                root.brightness = ratio;
            }

            // Suppress duplicate OSD pulse if this D-Bus signal is an echo of our own user action
            const now = Date.now();
            const isEcho = (root.lastSentAction.dbusName === displayDbusName &&
                            Math.abs(root.lastSentAction.targetVal - newBrightness) <= 1 &&
                            (now - root.lastSentAction.timestamp) < 1200);

            if (!isEcho) {
                root.osdPulse();
            }
        }
    }

    // 3. Sysfs dynamic read-only fallback if D-Bus service is unavailable
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
                        const ratio = Math.max(0.0, Math.min(1.0, cur / max));
                        root.brightness = ratio;
                        root.sysfsReadable = true;
                        root.lastChangedDisplay = {
                            dbusName: "sysfs",
                            label: "Internal Display",
                            isInternal: true,
                            brightness: cur,
                            maxBrightness: max,
                            ratio: ratio
                        };
                    }
                }
            } else {
                root.sysfsReadable = false;
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

    function setBrightnessForDisplay(dbusName, ratio) {
        if (!root.displays || root.displays.length === 0 || !dbusName) return;

        // Strict display lookup: Never fall back to another/controlled display if dbusName is unknown or stale
        let targetDisp = null;
        for (let i = 0; i < root.displays.length; i++) {
            if (root.displays[i].dbusName === dbusName || root.displays[i].path === dbusName) {
                targetDisp = root.displays[i];
                break;
            }
        }
        if (!targetDisp || targetDisp.maxBrightness <= 0) return;

        const clamped = Math.max(0.0, Math.min(1.0, ratio));
        const targetVal = Math.round(clamped * targetDisp.maxBrightness);
        targetDisp.brightness = targetVal;

        root.lastSentAction = {
            dbusName: targetDisp.dbusName,
            targetVal: targetVal,
            timestamp: Date.now()
        };

        root.lastChangedDisplay = {
            dbusName: targetDisp.dbusName,
            path: targetDisp.path,
            label: targetDisp.label,
            isInternal: targetDisp.isInternal,
            brightness: targetVal,
            maxBrightness: targetDisp.maxBrightness,
            ratio: clamped
        };

        if (root.controlledDisplay && root.controlledDisplay.dbusName === targetDisp.dbusName) {
            root.brightness = clamped;
        }

        root.osdPulse();
        Quickshell.execDetached(["qdbus6", "org.kde.ScreenBrightness", targetDisp.path, "org.kde.ScreenBrightness.Display.SetBrightness", targetVal.toString(), "0"]);
    }

    function setBrightness(ratio) {
        if (root.controlledDisplay) {
            setBrightnessForDisplay(root.controlledDisplay.dbusName, ratio);
        }
    }

    function increaseBrightness(step, dbusName) {
        const delta = step || 0.05;
        if (dbusName) {
            for (let i = 0; i < root.displays.length; i++) {
                if (root.displays[i].dbusName === dbusName) {
                    const curRatio = root.displays[i].brightness / root.displays[i].maxBrightness;
                    setBrightnessForDisplay(dbusName, curRatio + delta);
                    return;
                }
            }
            // If explicit dbusName provided but not found, NO-OP
            return;
        }
        if (root.controlledDisplay) {
            setBrightnessForDisplay(root.controlledDisplay.dbusName, root.brightness + delta);
        }
    }

    function decreaseBrightness(step, dbusName) {
        const delta = step || 0.05;
        if (dbusName) {
            for (let i = 0; i < root.displays.length; i++) {
                if (root.displays[i].dbusName === dbusName) {
                    const curRatio = root.displays[i].brightness / root.displays[i].maxBrightness;
                    setBrightnessForDisplay(dbusName, curRatio - delta);
                    return;
                }
            }
            // If explicit dbusName provided but not found, NO-OP
            return;
        }
        if (root.controlledDisplay) {
            setBrightnessForDisplay(root.controlledDisplay.dbusName, root.brightness - delta);
        }
    }

    Component.onCompleted: {
        refresh();
    }
}
