import QtQuick
import QtQuick.Layouts
import "../../services"
import "../../components"

Surface {
    id: root

    implicitHeight: 34
    implicitWidth: layout.implicitWidth + 12
    radius: Theme.radiusSmall
    color: netMouse.containsMouse ? Theme.hover : Theme.alpha(Theme.surfaceVariant, 0.6)

    readonly property string iconName: {
        if (!NetworkService.connected) return "network-disconnect";
        if (NetworkService.connectionType === "ethernet") return "network-wired";
        return "network-wireless";
    }

    readonly property string tooltipText: {
        if (!NetworkService.connected) return "Network: Disconnected";
        if (NetworkService.connectionType === "ethernet") return "Wired Connection (" + (NetworkService.activeDeviceName || "Ethernet") + ")";
        let text = "Wi-Fi: " + (NetworkService.ssid || "Connected");
        if (NetworkService.signalStrength >= 0) {
            text += " (" + NetworkService.signalStrength + "%)";
        }
        return text;
    }

    RowLayout {
        id: layout
        anchors.centerIn: parent
        spacing: 6

        SvgIcon {
            icon: root.iconName
            size: 16
            color: NetworkService.connected ? Theme.primary : Theme.error
        }

        Text {
            text: NetworkService.connected ? (NetworkService.connectionType === "ethernet" ? "Wired" : (NetworkService.ssid || "Connected")) : "Offline"
            color: Theme.foreground
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeSmall
            elide: Text.ElideRight
            Layout.maximumWidth: 100
        }
    }

    Tooltip {
        text: root.tooltipText
        show: netMouse.containsMouse
    }

    MouseArea {
        id: netMouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: NetworkService.openNetworkSettings()
    }
}
