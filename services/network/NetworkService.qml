pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import "../core/Log.js" as Log

Singleton {
    id: root

    property bool connected: true
    property string connectionType: "wifi" // "wifi" | "ethernet" | "disconnected"
    property string ssid: ""
    property int signalStrength: 80
    property string ipAddress: ""

    function refresh() {
        if (!nmProc.running) {
            nmProc.buf = "";
            nmProc.running = true;
        }
    }

    Process {
        id: nmProc
        command: ["sh", "-c", "nmcli -t -f TYPE,STATE,DEVICE,CONNECTION d status 2>/dev/null || true"]
        property string buf: ""
        stdout: SplitParser {
            onRead: data => { nmProc.buf += data + "\n"; }
        }
        onExited: exitCode => {
            if (exitCode === 0 && nmProc.buf.trim().length > 0) {
                const lines = nmProc.buf.trim().split("\n");
                let isConn = false;
                let cType = "disconnected";
                let activeSsid = "";

                for (let i = 0; i < lines.length; i++) {
                    const parts = lines[i].split(":");
                    if (parts.length >= 4) {
                        const type = parts[0];
                        const state = parts[1];
                        const connName = parts[3];

                        if (state === "connected") {
                            isConn = true;
                            if (type === "ethernet") {
                                cType = "ethernet";
                                activeSsid = connName || "Wired Connection";
                                break; // Prioritize ethernet
                            } else if (type === "wifi") {
                                cType = "wifi";
                                activeSsid = connName || "Wireless Network";
                            }
                        }
                    }
                }

                root.connected = isConn;
                root.connectionType = isConn ? cType : "disconnected";
                root.ssid = activeSsid;
            }
            nmProc.buf = "";
        }
    }

    function openNetworkSettings() {
        Quickshell.execDetached(["kcmshell6", "kcm_networkmanagement"]);
    }

    Timer {
        interval: 10000
        running: true
        repeat: true
        onTriggered: root.refresh()
    }

    Component.onCompleted: {
        root.refresh();
    }
}
