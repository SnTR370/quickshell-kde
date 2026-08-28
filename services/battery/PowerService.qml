pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Services.UPower
import Quickshell.Io
import "../core/Log.js" as Log

Singleton {
    id: root

    // Search UPower devices for battery
    readonly property var batteryDevice: {
        if (UPower.displayDevice && UPower.displayDevice.isPresent) {
            return UPower.displayDevice;
        }
        if (UPower.devices) {
            for (let i = 0; i < UPower.devices.values.length; i++) {
                const dev = UPower.devices.values[i];
                if (dev && (dev.type === UPowerDeviceType.Battery || (dev.nativePath && dev.nativePath.indexOf("BAT") !== -1))) {
                    return dev;
                }
            }
        }
        return null;
    }

    property bool isPresent: batteryDevice ? batteryDevice.isPresent : fallbackPresent
    property real percentage: batteryDevice ? batteryDevice.percentage : fallbackPercentage
    property bool isCharging: batteryDevice ? (batteryDevice.state === UPowerDeviceState.Charging) : fallbackCharging
    property bool isPluggedIn: batteryDevice ? (batteryDevice.state === UPowerDeviceState.Charging || batteryDevice.state === UPowerDeviceState.FullyCharged) : fallbackCharging
    property int state: batteryDevice ? batteryDevice.state : 0

    // Sysfs fallback properties
    property bool fallbackPresent: false
    property real fallbackPercentage: 100
    property bool fallbackCharging: false

    function refreshFallback() {
        if (!batteryDevice) {
            sysfsProc.buf = "";
            sysfsProc.running = true;
        }
    }

    Process {
        id: sysfsProc
        command: ["sh", "-c", "cat /sys/class/power_supply/BAT*/capacity 2>/dev/null | head -1; cat /sys/class/power_supply/BAT*/status 2>/dev/null | head -1"]
        property string buf: ""
        stdout: SplitParser {
            onRead: data => { sysfsProc.buf += data + "\n"; }
        }
        onExited: exitCode => {
            if (exitCode === 0 && sysfsProc.buf.trim().length > 0) {
                const lines = sysfsProc.buf.trim().split("\n");
                if (lines.length >= 1 && lines[0].trim().length > 0) {
                    const cap = parseInt(lines[0].trim());
                    if (!isNaN(cap)) {
                        root.fallbackPresent = true;
                        root.fallbackPercentage = cap / 100.0;
                    }
                }
                if (lines.length >= 2) {
                    const status = lines[1].trim().toLowerCase();
                    root.fallbackCharging = (status === "charging" || status === "full");
                }
            }
            sysfsProc.buf = "";
        }
    }

    Timer {
        interval: 10000
        running: true
        repeat: true
        onTriggered: root.refreshFallback()
    }

    Component.onCompleted: {
        root.refreshFallback();
    }
}
