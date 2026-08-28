pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Networking
import "../core/Log.js" as Log

Singleton {
    id: root

    readonly property var devices: (Networking.devices && Networking.devices.values) ? Networking.devices.values : []
    readonly property int connectivity: Networking.connectivity
    readonly property bool wifiEnabled: Networking.wifiEnabled

    // Active connected device discovery via declarative property bindings
    readonly property var activeWired: {
        for (let i = 0; i < devices.length; i++) {
            const dev = devices[i];
            if (dev && dev.type === DeviceType.Wired && dev.connected) return dev;
        }
        return null;
    }

    readonly property var activeWifi: {
        for (let i = 0; i < devices.length; i++) {
            const dev = devices[i];
            if (dev && dev.type === DeviceType.Wifi && dev.connected) return dev;
        }
        return null;
    }

    readonly property var activeWifiNetwork: {
        if (!activeWifi || !activeWifi.networks || !activeWifi.networks.values) return null;
        const nets = activeWifi.networks.values;
        for (let j = 0; j < nets.length; j++) {
            if (nets[j] && nets[j].connected) return nets[j];
        }
        return null;
    }

    // Reactive status properties
    readonly property bool connected: activeWired !== null || activeWifi !== null
    readonly property string connectionType: activeWired !== null ? "ethernet" : (activeWifi !== null ? "wifi" : (devices.length > 0 ? "disconnected" : "unknown"))
    readonly property string activeDeviceName: activeWired ? (activeWired.name || "Wired") : (activeWifi ? (activeWifi.name || "Wi-Fi") : "")
    readonly property string hardwareAddress: activeWired ? (activeWired.address || "") : (activeWifi ? (activeWifi.address || "") : "")
    readonly property string ssid: activeWifiNetwork ? (activeWifiNetwork.name || "") : (activeWifi ? "Wi-Fi" : "")
    readonly property int signalStrength: (activeWifiNetwork && activeWifiNetwork.signalStrength !== undefined && activeWifiNetwork.signalStrength >= 0) ? Math.round(activeWifiNetwork.signalStrength * 100) : -1

    function openNetworkSettings() {
        Quickshell.execDetached(["kcmshell6", "kcm_networkmanagement"]);
    }
}
