pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Networking
import "../core/Log.js" as Log

Singleton {
    id: root

    property bool connected: false
    property string connectionType: "unknown" // "wifi" | "ethernet" | "disconnected" | "unknown"
    property string ssid: ""
    property int signalStrength: -1 // -1 when unknown or wired; 0-100 for wifi
    property string ipAddress: ""
    property string activeDeviceName: ""
    readonly property bool wifiEnabled: Networking.wifiEnabled

    function updateNetworkState() {
        if (!Networking.devices || !Networking.devices.values) {
            root.connected = false;
            root.connectionType = "unknown";
            root.ssid = "";
            root.signalStrength = -1;
            root.activeDeviceName = "";
            return;
        }

        const devList = Networking.devices.values;
        let wiredDev = null;
        let wifiDev = null;

        for (let i = 0; i < devList.length; i++) {
            const dev = devList[i];
            if (!dev) continue;
            if (dev.type === DeviceType.Wired && dev.connected) {
                wiredDev = dev;
                break; // Prioritize wired connection
            } else if (dev.type === DeviceType.Wifi && dev.connected && !wifiDev) {
                wifiDev = dev;
            }
        }

        if (wiredDev) {
            root.connected = true;
            root.connectionType = "ethernet";
            root.ssid = "";
            root.signalStrength = -1;
            root.activeDeviceName = wiredDev.name || "Wired";
            root.ipAddress = wiredDev.address || "";
        } else if (wifiDev) {
            root.connected = true;
            root.connectionType = "wifi";
            root.activeDeviceName = wifiDev.name || "Wi-Fi";
            root.ipAddress = wifiDev.address || "";

            let activeSsid = "";
            let sig = -1;
            if (wifiDev.networks && wifiDev.networks.values) {
                for (let j = 0; j < wifiDev.networks.values.length; j++) {
                    const net = wifiDev.networks.values[j];
                    if (net && net.connected) {
                        activeSsid = net.name || "";
                        if (net.signalStrength !== undefined && net.signalStrength >= 0) {
                            sig = Math.round(net.signalStrength * 100);
                        }
                        break;
                    }
                }
            }

            root.ssid = activeSsid || "Wi-Fi";
            root.signalStrength = sig;
        } else if (devList.length > 0) {
            root.connected = false;
            root.connectionType = "disconnected";
            root.ssid = "";
            root.signalStrength = -1;
            root.activeDeviceName = "";
            root.ipAddress = "";
        } else {
            root.connected = false;
            root.connectionType = "unknown";
            root.ssid = "";
            root.signalStrength = -1;
            root.activeDeviceName = "";
            root.ipAddress = "";
        }
    }

    // Reactive watcher on device changes
    Timer {
        id: syncTimer
        interval: 1000
        repeat: true
        running: true
        onTriggered: root.updateNetworkState()
    }

    function openNetworkSettings() {
        Quickshell.execDetached(["kcmshell6", "kcm_networkmanagement"]);
    }

    Component.onCompleted: {
        root.updateNetworkState();
    }
}
